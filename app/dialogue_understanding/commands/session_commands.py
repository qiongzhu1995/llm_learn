"""
会话相关命令

包含会话管理、澄清、人工转接等命令。
"""

from __future__ import annotations

import re
from dataclasses import dataclass,field
from typing import Any,Optional,TYPE_CHECKING

from app.dialogue_understanding.commands.base import Command,register_command
from app.dialogue_understanding.stack.stack_frame import HumanHandoffStackFrame

if TYPE_CHECKING:
    from app.core.tracker import DialogueStateTracker

@register_command
@dataclass
class SessionStartCommand(Command):
    """启动会话命令。
    
    用于启动新的会话。当用户开始新对话时，会生成此命令。

    """
    
    
    @classmethod
    def command_name(cls) -> str:
        """命令名称"""
        return "session_start"
    
    @classmethod
    def from_dict(cls,data:dict[str,Any]) -> "SessionStartCommand":
        """从字典创建命令对象"""
        return SessionStartCommand()
    
    def run(self,tracker:"DialogueStateTracker",flows:Optional[Any] = None) -> list[dict[str,Any]]:
        """执行启动会话命令。在tracker上启动新的会话"""
        return [{
            "event":"session_start_requested",
            "timestamp":None,
        }]
    
    def to_dsl(self) -> str:
        """将命令对象转换为DSL文本"""
        return "session start"
    
    @classmethod
    def regex_pattern(cls) -> str:
        return  r"""^session_start$"""

    @classmethod
    def _from_regex_match(cls,match:re.Match) -> Optional["SessionStartCommand"]:
        """从正则匹配结果创建命令对象"""
        return SessionStartCommand()
    

@register_command
@dataclass
class ClearifyCommand(Command):
    """澄清命令。
    
    当用户输入不清晰或需要更多信息时，使用此命令请求澄清。
    
    Attributes:
        question: 澄清问题（可选）
        options: 供用户选择的选项列表（可选）
    """
    question: Optional[str] = None
    options: list[str] = field(default_factory=list)
    
    @classmethod
    def command_name(cls) -> str:
        """命令名称"""
        return "clearify"
    
    @classmethod
    def from_dict(cls,data:dict[str,Any]) -> "ClearifyCommand":
        """从字典创建命令对象"""
        return ClearifyCommand(
            question=data.get("question"),
            options=data.get("options",[]),
        )
    
    def run(self,tracker:"DialogueStateTracker",flows:Optional[Any] = None) -> list[dict[str,Any]]:
        """执行澄清命令。在tracker上记录澄清事件"""
        return [{
            "event":"clarification_requested",
            "question":self.question,
            "options":self.options,
            "timestamp":None,
        }]
    
    def to_dsl(self) -> str:
        """将命令对象转换为DSL文本"""
        if self.question:
            return f"clearify({self.question})"
        return "clearify"
    
    @classmethod
    def regex_pattern(cls) -> str:
        return r"""^clarify(?:\(['"]?(.*)['"]?\))?$"""
    
    @classmethod
    def _from_regex_match(cls,match:re.Match) -> Optional["ClearifyCommand"]:
        """从正则匹配结果创建命令对象"""
        question = match.group(1)
        return ClearifyCommand(question=question.strip() if question else None)

@register_command
@dataclass
class HumanHandoffCommand(Command):
    """人工转接命令。
    
    当需要人工介入时，使用此命令请求人工转接。
    
    Attributes:
        reason: 转接原因
    """
    reason: Optional[str] = None
    
    @classmethod
    def command_name(cls) -> str:
        """命令名称"""
        return "human_handoff"
    
    @classmethod
    def from_dict(cls,data:dict[str,Any]) -> "HumanHandoffCommand":
        """从字典创建命令对象"""
        return HumanHandoffCommand(reason=data.get("reason"))
    
    def run(self,tracker:"DialogueStateTracker",flows:Optional[Any] = None) -> list[dict[str,Any]]:
        """执行人工转接命令。在tracker上记录人工转接事件"""
        from app.dialogue_understanding.stack.stack_frame import HumanHandoffStackFrame
        tracker.dialogue_stack.push(HumanHandoffStackFrame(reason=self.reason))

        return [{
            "event":"human_handoff_requested",
            "reason":self.reason,
            "timestamp":None,
        }]
    
    def to_dsl(self) -> str:
        """将命令对象转换为DSL文本"""
        if self.reason:
            return f"human_handoff({self.reason})"
        return "human_handoff"
    
    @classmethod
    def regex_pattern(cls) -> str:
        return r"""^human_handoff(?:\(['"]?(.*)['"]?\))?$"""
    
    @classmethod
    def _from_regex_match(cls,match:re.Match) -> Optional["HumanHandoffCommand"]:
        """从正则匹配结果创建命令对象"""
        reason = match.group(1)
        return HumanHandoffCommand(reason=reason.strip() if reason else None)
    
@register_command
@dataclass
class RestartCommand(Command):
    """重启命令。
    重置当前对话状态，清空所有槽位和Flow。
    """
    
    @classmethod
    def command_name(cls) -> str:
        """命令名称"""
        return "restart"
    
    @classmethod
    def from_dict(cls,data:dict[str,Any]) -> "RestartCommand":
        """从字典创建命令对象"""
        return RestartCommand()
    
    def run(self,tracker:"DialogueStateTracker",flows:Optional[Any] = None) -> list[dict[str,Any]]:
        """执行重启命令。在tracker上记录重启事件"""
        return [{
            "event":"restart_requested",
            "timestamp":None,
        }]
    
    def to_dsl(self) -> str:
        """将命令对象转换为DSL文本"""
        return "restart"
    
    @classmethod
    def regex_pattern(cls) -> str:
        return r"""^restart$"""
    
    @classmethod
    def _from_regex_match(cls,match:re.Match) -> Optional["RestartCommand"]:
        """从正则匹配结果创建命令对象"""
        return RestartCommand()
    
@register_command
@dataclass
class NoopCommand(Command):
    """空操作命令。
    
    不执行任何操作。用于特定场景下需要显式表示"不做任何事"。
    """
    
    @classmethod
    def command_name(cls) -> str:
        """命令名称"""
        return "noop"
    
    @classmethod
    def from_dict(cls,data:dict[str,Any]) -> "NoopCommand":
        """从字典创建命令对象"""
        return NoopCommand()
    
    def run(self,tracker:"DialogueStateTracker",flows:Optional[Any] = None) -> list[dict[str,Any]]:
        """执行空操作命令。不执行任何操作"""
        return []
    
    def to_dsl(self) -> str:
        """将命令对象转换为DSL文本"""
        return "noop"
    
    @classmethod
    def regex_pattern(cls) -> str:
        return r"""^noop$"""
    
    @classmethod
    def _from_regex_match(cls,match:re.Match) -> Optional["NoopCommand"]:
        """从正则匹配结果创建命令对象"""
        return NoopCommand()
    
__all__ = [
    "SessionStartCommand",
    "ClearifyCommand",
    "HumanHandoffCommand",
    "RestartCommand",
    "NoopCommand",
]
