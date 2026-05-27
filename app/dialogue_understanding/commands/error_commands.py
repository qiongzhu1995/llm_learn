"""
错误相关命令

用于处理系统错误和异常情况的命令。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any,Optional,TYPE_CHECKING

from app.dialogue_understanding.commands.base import Command,register_command
from app.shared.config import settings

if TYPE_CHECKING:
    from app.core.tracker import DialogueStateTracker

@register_command
@dataclass
class ErrorCommand(Command):
    """错误命令。
    
    用于处理系统错误和异常情况的命令。
    """
    error_type: str = "unknown_error"
    message: str = None

    @classmethod
    def command_name(cls) -> str:
        """命令名称"""
        return "error"
    
    @classmethod
    def from_dict(cls,data:dict[str,Any]) -> "ErrorCommand":
        """从字典创建命令对象"""
        return ErrorCommand(
            error_type=data.get("error_type","unknown_error"),
            message=data.get("message"),
        )
    def run(self,tracker:"DialogueStateTracker",flows:Optional[Any] = None) -> list[dict[str,Any]]:
        """执行错误命令。记录报错事件"""
        return [{
            "event":"error_occurred",
            "error_type":self.error_type,
            "message":self.message,
            "degradation_reason":settings.degradation.INTERNAL_ERROR,
            "timestamp":None,
        }]
    
    def to_dsl(self) -> str:
        """将命令对象转换为DSL文本"""
        if self.message:
            return f"error({self.error_type},{self.message})"
        return f"error({self.error_type})"
    
    @classmethod
    def regex_pattern(cls) -> str:
        return r"""^error\(['"]?([^'"]+)['"]?(?:,\s*['"]?([^'"]+)['"]?)?\)$"""
    
    @classmethod
    def _from_regex_match(cls,match:re.Match) -> Optional["ErrorCommand"]:
        """从正则匹配结果创建命令对象"""
        error_type = match.group(1) 
        message = match.group(2) 
        return ErrorCommand(
            error_type = error_type.strip() if error_type else "unknown_error",
            message = message.strip() if message else None,
        )

@register_command
@dataclass
class InternalErrorCommand(Command):
    """内部错误命令。
    
    当系统遇到内部错误（如LLM调用失败、超时等）时生成此命令。
    
    Attributes:
        exception_type: 异常类型名
        exception_message: 异常消息
    """
    exception_type: str = "InternalError"
    exception_message: Optional[str] = None

    @classmethod
    def command_name(cls) -> str:
        """命令名称"""
        return "internal_error"
    
    @classmethod
    def from_dict(cls,data:dict[str,Any]) -> "InternalErrorCommand":
        """从字典创建命令对象"""
        return InternalErrorCommand(
            exception_type=data.get("exception_type","InternalError"),
            exception_message=data.get("exception_message"),
        )

    def run(self,tracker:"DialogueStateTracker",flows:Optional[Any] = None) -> list[dict[str,Any]]:
        """执行内部错误命令。记录异常事件"""
        return [{
            "event":"internal_error_occurred",
            "exception_type":self.exception_type,
            "exception_message":self.exception_message,
            "degradation_reason":settings.degradation.INTERNAL_ERROR,
            "timestamp":None,
        }]
    
    def to_dsl(self) -> str:
        """将命令对象转换为DSL文本"""
        if self.exception_message:
            return f"internal_error({self.exception_type},{self.exception_message})"
        return f"internal_error({self.exception_type})"

@register_command
@dataclass
class ParseErrorCommand(Command):
    """解析错误命令。"""
    raw_text: str = None
    error_message: Optional[str] = None

    @classmethod
    def command_name(cls) -> str:
        """命令名称"""
        return "parse_error"
    
    @classmethod
    def from_dict(cls,data:dict[str,Any]) -> "ParseErrorCommand":
        """从字典创建命令对象"""
        return ParseErrorCommand(
            raw_text=data.get("raw_text"),
            error_message=data.get("error_message"),
        )

    def run(self,tracker:"DialogueStateTracker",flows:Optional[Any] = None) -> list[dict[str,Any]]:
        """执行解析错误命令。记录解析错误事件"""
        return [{
            "event":"parse_error_occurred",
            "raw_text":self.raw_text,
            "error_message":self.error_message,
            "degradation_reason":settings.degradation.PARSE_ERROR,
            "timestamp":None,
        }]
    
    def to_dsl(self) -> str:
        """将命令对象转换为DSL文本"""
        return f"parse_error({self.raw_text})"

__all__ = [
    "ErrorCommand",
    "InternalErrorCommand",
    "ParseErrorCommand",
]