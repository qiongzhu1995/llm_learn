"""
槽位相关命令

包含槽位设置等命令。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any,Optional,TYPE_CHECKING

from app.dialogue_understanding.commands.base import Command,register_command
from app.shared.logger import logger

if TYPE_CHECKING:
    from app.core.tracker import DialogueStateTracker

def clean_extracted_value(value:str) -> Any:
    """清理从DSL中提取的值。
    
    处理引号、空格，以及特殊值（null, true, false, 数字）。
    
    Args:
        value: 原始字符串值
        
    Returns:
        清理后的值
    """
    if value is None:
        return None
    
    # 去除空格
    value = value.strip()

    # 取出引号
    if (value.startswith('"') and value.endswith('"')) or \
       (value.startswith("'") and value.endswith("'")):
        value = value[1:-1]
    
    # 处理特殊值
    value_lower = value.lower()
    if value_lower == "null" or value_lower == "none":
        return None
    
    if value_lower == "true":
        return True
    elif value_lower == "false":
        return False
    
    # 尝试转换为数字
    try:
        if "." in value:
            return float(value)
        else:
            return int(value)
    except ValueError:
        pass

    return value
    
@register_command
@dataclass
class SetSlotCommand(Command):
    """设置槽位命令。
       用于设置对话状态中的槽位值。LLM识别到用户提供的信息后，会生成此命令来记录信息。

    Attributes:
        name: 槽位名称
        value: 槽位值
        extractor: 提取器类型（llm, nlu, form等）
    """
    name: str
    value: Any
    extractor: str = "llm"

    @classmethod
    def command_name(cls) -> str:
        """命令名称"""
        return "set_slot"
    
    @classmethod
    def from_dict(cls,data:dict[str,Any]) -> "SetSlotCommand":
        """从字典创建命令对象"""
        try:
            return SetSlotCommand(
                name=data.get("name"),
                value=data.get("value"),
                extractor=data.get("extractor", "llm")
            )
        except KeyError as e:
            raise ValueError(f"缺少必需的键: {e}") from e
        
    
    def run(self,tracker:"DialogueStateTracker",flows:Optional[Any] = None) -> list[dict[str,Any]]:
        """执行设置槽位命令。在tracker上设置槽位值"""
        # 获取槽位对象以检查类型
        slot_obj = tracker.slots.get(self.name)
        value_to_set = self.value

        # 如果槽位是text类型,将值转换为字符串
        if slot_obj and hasattr(slot_obj,"value_type") :
            if slot_obj.value_type == "text" and value_to_set is not None:
                value_to_set = str(value_to_set)
        
        # 设置槽位值
        try:
            tracker.set_slot(self.name,value_to_set)
            return [{
                "event":"slot_set",
                "name":self.name,
                "value":value_to_set,
                "extractor":self.extractor,
                "timestamp":None,
            }]
        except Exception as e:
            logger.error(f"设置槽位失败: {e}")
            return []
        
    def to_dsl(self) -> str:
        """将命令对象转换为DSL文本"""
        # 根据值类型是否添加引号
        if isinstance(self.value,str):
            return f'set slot {self.name} "{self.value}" '
        elif self.value is None:
            return f'set slot {self.name} null'
        else:
            return f'set slot {self.name} {self.value}'
    
    @classmethod
    def regex_pattern(cls) -> str:
        return r"""(?:set\s+slot\s+['"`]?([a-zA-Z_][a-zA-Z0-9_-]*)['"`]?\s+['"`]?(.+?)['"`]?$|SetSlot\(['"]?([a-zA-Z_][a-zA-Z0-9_-]*)['"]?,\s*['"]?(.*)['"]?\))"""
    
    @classmethod
    def _from_regex_match(cls,match:re.Match) -> Optional["SetSlotCommand"]:
        """从正则匹配创建命令对象"""
        name = match.group(1) or match.group(2)
        value = match.group(3) or match.group(4)

        if name:
            return SetSlotCommand(name=name.strip(),value = clean_extracted_value(value.strip()) if value else None)
        return None
    
    def __hash__(self) -> int:
        """计算命令对象的哈希值"""
        return hash((self.name,self.value))
    
    def __eq__(self,other:Any) -> bool:
        """判断命令对象是否相等"""
        if not isinstance(other,SetSlotCommand):
            return False
        return self.name == other.name and str(self.value).lower() == str(other.value).lower()

@register_command
@dataclass
class ResetSlotCommand(Command):
    """重置槽位命令。将槽位值设置为初始值
    
    Attributes:
        name: 槽位名称
    """
    name: str
    
    @classmethod
    def command_name(cls) -> str:
        """命令名称"""
        return "reset_slot"

    @classmethod
    def from_dict(cls,data:dict[str,Any]) -> "ResetSlotCommand":
        """从字典创建命令对象"""
        try:
            return ResetSlotCommand(name=data.get("name"))
        except KeyError as e:
            raise ValueError(f"缺少必需的键: {e}") from e
        
    def run(self,tracker:"DialogueStateTracker",flows:Optional[Any] = None) -> list[dict[str,Any]]:
        """执行重置槽位命令。在tracker上重置槽位值"""
        # 获取槽位对象以检查类型
        slot_obj = tracker.slots.get(self.name)
        if slot_obj:
            slot_obj.reset()
            return [{
                "event":"slot_reset",
                "name":self.name,
                "timestamp":None,
            }]
        return []
    
    def to_dsl(self) -> str:
        """将命令对象转换为DSL文本"""
        return f'reset slot {self.name}'
    
    @classmethod
    def regex_pattern(cls) -> str:
        return r"""(?:reset\s+slot\s+['"`]?([a-zA-Z_][a-zA-Z0-9_-]*)['"`]?$|ResetSlot\(['"]?([a-zA-Z_][a-zA-Z0-9_-]*)['"]?\))"""
    
    @classmethod
    def _from_regex_match(cls,match:re.Match) -> Optional["ResetSlotCommand"]:
        """从正则匹配创建命令对象"""
        name = match.group(1) 
        if name:
            return ResetSlotCommand(name=name.strip())
        return None
    
__all__ = ["SetSlotCommand", "ResetSlotCommand","clean_extracted_value"]