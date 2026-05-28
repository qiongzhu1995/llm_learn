"""
命令解析器

负责解析LLM输出的文本，将其转换为命令对象。
"""

from __future__ import annotations

import re
from typing import Optional,Any,TYPE_CHECKING
from dataclasses import dataclass,field

from app.shared.logger import logger
if TYPE_CHECKING:
    from app.dialogue_understanding.commands.base import Command,get_all_command_classes,parse_command_from_text


@dataclass
class ParserResult:
    """命令解析结果"""
    commands:list["Command"] = field(default_factory=list) # 解析出的命令列表
    errors:list[tuple(str,str)] = field(default_factory=list) # 解析错误列表
    raw_lines:list[str] = field(default_factory=list) # 原始文本行列表

    @property
    def success(self) -> bool:
        """判断命令解析是否成功"""
        return len(self.commands) > 0 and not self.errors
    
    @property
    def has_errors(self) -> bool:
        """判断是否存在解析错误"""
        return len(self.errors) > 0
    
class CommandParser:
    """命令解析器。
    
    负责将LLM输出的文本解析为命令对象列表。
    
    支持的命令格式：
    1. DSL格式: start flow booking, set slot name "John"
    2. 函数格式: StartFlow(booking), SetSlot(name, "John")
    """
    def __init__(self) -> None:
        self._command_classes = get_all_command_classes()

    def parse(self,text:str) -> ParserResult:
        """解析文本中的命令"""
        result = ParserResult()

        # 准备文本
        text = self._clean_text(text)

        # 按行分割
        lines = self._split_lines(text)
        result.raw_lines = lines

        # 解析每行命令
        for line in lines:
            line = line.strip()
            if not line:
                continue

            try:
                command = self._parse_line(line)
                if command:
                    result.commands.append(command)
                else:
                    # 无法识别的行
                    result.errors.append((line,"无法识别的命令"))
            
            except Exception as e:
                # 解析错误
                result.errors.append((line,str(e)))
                logger.error(f"解析命令失败: {e}")

        return result
    
    def parse_single(self,text:str) -> Optional["Command"]:
        """解析单个命令"""

        result = self.parse(text)
        return result.commands[0] if result.commands else None

    def _clean_text(self,text:str) -> str:
        """清理文本 移除markdown代码块标记等"""

        #  移除markdown代码块
        text = re.sub(r'```[\w]*\n?', '', text)

        # 移除开头的反引号
        text = re.sub(r'`([^`]+)`', r'\1', text)

        # 移除开头的编号
        lines = []
        for line in text.split('\n'):
            # 移除列表标记
            line = re.sub(r'^\s*[-*•]\s*', '', line)
            # 移除编号
            line = re.sub(r'^\s*\d+\.\s*', '', line)
            lines.append(line)
        text = '\n'.join(lines)
        return text
    
    def _split_lines(self,text:str) -> list[str]:
        """按行分割文本"""
        lines = text.split('\n')

        result = []
        for line in lines:
            if ';' in line:
                result.extend(line.split(';'))
            else:
                result.append(line)
        return [l.strip() for l in result if l.strip()]

    def _parse_line(self,line:str) -> Optional["Command"]:
        """解析单行命令"""
        line = line.strip()
        # 尝试使用注册的命令类解析
        command = parse_command_from_text(line)
        if command:
            return command
        
        # 尝试诸葛命令类的模式匹配
        for command_name,command_class in self._command_classes.items():
            try:
                pattern = command_class.regex_pattern()
                if pattern:
                    match = re.match(pattern,line,re.IGNORECASE)
                    if match:
                        return command_class._from_regex_match(match)
            except Exception as e:
                logger.error(f"解析命令失败: {e}")
                continue
        return None
    
    def validate_command(self,commands:list[Command]) -> list[Command]:
        """验证命令列表 过滤掉无效的命令"""

        return [command for command in commands if self._is_valid_command(command)]
    
    def _is_valid_command(self,command:Command) -> bool:
        """验证命令是否有效"""
        if command is None:
            return False
        
        try:
            # startflowCommand 
            if hasattr(command,"flow") and not command.flow:
                return False
            # setslotcommand 需要name字段
            if hasattr(command,"name") and not command.name:
                return False
            return True
        except Exception as e:
            logger.error(f"验证命令失败: {e}")
            return False
        return True

# 创建默认解析器实例
default_parser = CommandParser()

def parse_commands(text:str) -> list[Command]:
    """解析文本中的命令"""
    return default_parser.parse(text).commands

def parse_single_command(text:str) -> Optional[Command]:
    """解析单个命令"""
    return default_parser.parse_single(text)

__all__ = ["parse_commands","parse_single_command","default_parser","CommandParser","ParserResult"]

        



    