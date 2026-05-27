"""
Flow相关命令

包含Flow启动、取消等命令。
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
class StartFlowCommand(Command):
    """启动Flow命令。
    
    用于启动指定的对话流程。当LLM识别到用户意图与某个Flow匹配时,
    会生成此命令来启动相应的Flow。
    
    设计说明：
        StartFlowCommand 是"即时数据命令"，其 run() 方法直接操作 tracker
        设置 active_flow，以便 FlowPolicy 能立即接管执行 Flow 步骤。
        这与"动作触发命令"（如 CancelFlowCommand）不同，后者通过
        设置 next_action 触发对应的 Action 来执行操作。
    
    Attributes:
        flow: 要启动的Flow ID
    """
    flow: str = None

    @classmethod
    def command_name(cls) -> str:
        """命令名称"""
        return "start_flow"
    
    @classmethod
    def from_dict(cls,data:dict[str,Any]) -> "StartFlowCommand":
        """从字典创建命令对象"""
        try:
            return StartFlowCommand(flow=data.get("flow"))
        except KeyError as e:
            raise ValueError(f"Failed to create StartFlowCommand from dict: {e}")
    
    def run(self,tracker:"DialogueStateTracker",flows:Optional[Any] = None) -> list[dict[str,Any]]:
        """执行启动Flow命令。在tracker上启动指定的Flow"""
        # 检查flow是否存在
        if flows is not None:
            flow_ids = getattr(flows,"flow_ids",[])

            if hasattr(flows,"__iter__") and not isinstance(flows,str):
                flow_ids = [f.id if hasattr(f,"id") else str(f) for f in flows]
                # 如果flow_ids中不包含self.flow，则直接返回
                if self.flow not in flow_ids:
                    return []
        
        # 启动flow
        tracker.start_flow(self.flow)

        return [{
            "event":"flow_started",
            "flow":self.flow,
            "timestamp":None,
        }]
    
    def to_dsl(self) -> str:
        """将命令对象转换为DSL文本"""
        return f"start flow({self.flow})"
    
    @classmethod
    def regex_pattern(cls) -> str:
        return  r"""(?:start\s+flow\s+['"`]?([a-zA-Z0-9_-]+)['"`]?|StartFlow\(['"]?([a-zA-Z0-9_-]+)['"]?\))"""
    
    @classmethod
    def _from_regex_match(cls,match:re.Match) -> "StartFlowCommand":
        """从正则匹配结果创建命令对象"""
        flow = match.group(1) or match.group(2)
        if flow:
            return StartFlowCommand(flow=flow.strip())
        return None
    
    def __hash__(self) -> int:
        """计算命令对象的哈希值"""
        return hash(self.flow)
    
    def __eq__(self,other:Any) -> bool:
        """判断命令对象是否相等"""
        if not isinstance(other,StartFlowCommand):
            return False
        return self.flow == other.flow


@register_command
@dataclass
class CancelFlowCommand(Command):
    """取消Flow命令。
    
    用于取消当前正在执行的Flow。
        
    """
    flow:Optional[str] = None

    @classmethod
    def command_name(cls) -> str:
        """命令名称"""
        return "cancel_flow"
    
    @classmethod
    def from_dict(cls,data:dict[str,Any]) -> "CancelFlowCommand":
        """从字典创建命令对象"""
        return CancelFlowCommand(flow=data.get("flow"))

    def run(self,tracker:"DialogueStateTracker",flows:Optional[Any] = None) -> list[dict[str,Any]]:
        """ 注意：此方法只返回事件标记，实际的取消操作由 ActionCancelFlow 执行"""

        flow_id = self.flow or tracker.active_flow
        if flow_id:
            # 不直接取消 让active_flow的终止逻辑触发
            return [{
                "event":"flow_cancelled",
                "flow":flow_id,
                "timestamp":None,
            }]
        return []
    
    def to_dsl(self) -> str:
        """将命令对象转换为DSL文本"""
        if self.flow:
            return f"cancel flow({self.flow})"
        return "cancel flow"
    
    @classmethod
    def regex_pattern(cls) -> str:
        return r"""(?:cancel\s+flow(?:\s+['"`]?([a-zA-Z0-9_-]+)['"`]?)?|CancelFlow\((?:['"]?([a-zA-Z0-9_-]*)['"]?)?\))"""

    @classmethod
    def _from_regex_match(cls,match:re.Match) -> Optional["CancelFlowCommand"]:
        """从正则匹配创建命令"""
        flow = match.group(1) or match.group(2)
        return CancelFlowCommand(flow=flow.strip() if flow else None)

@register_command
@dataclass
class ChangeFlowCommand(Command):
    """切换Flow命令。
    
    用于从当前Flow切换到另一个Flow。
    
    设计说明：
        ChangeFlowCommand 是"动作触发命令"，其 run() 方法只返回事件标记，
        实际的切换操作由 ActionChangeFlow 执行。这样设计确保了
        Command 只声明意图，Action 执行实际操作的原则。
    
    Attributes:
        flow: 要切换到的Flow ID
    """
    flow: str = None

    @classmethod
    def command_name(cls) -> str:
        """命令名称"""
        return "change_flow"
    
    @classmethod
    def from_dict(cls,data:dict[str,Any]) -> "ChangeFlowCommand":
        """从字典创建命令对象"""
        try:
            return ChangeFlowCommand(flow=data.get("flow"))
        except KeyError as e:
            raise ValueError(f"Failed to create ChangeFlowCommand from dict: {e}")
    
    def run(self,tracker:"DialogueStateTracker",flows:Optional[Any] = None) -> list[dict[str,Any]]:
        """ 注意：此方法只返回事件标记，实际的切换操作由 ActionChangeFlow 执行"""
        old_flow = tracker.active_flow
        return [{
            "event":"change_flow_requested",
            "old_flow_id":old_flow,
            "new_flow_id":self.flow,
            "timestamp":None,
        }]
    
    def to_dsl(self) -> str:
        """转换为DSL字符串"""
        return f"change flow({self.flow})"

    @classmethod
    def regex_pattern(cls) -> str:
        return r"""change\s+flow\s+['"`]?([a-zA-Z0-9_-]+)['"`]?"""
    
    @classmethod
    def _from_regex_match(cls,match:re.Match) -> "ChangeFlowCommand":
        """从正则匹配创建命令"""
        flow = match.group(1)
        return ChangeFlowCommand(flow=flow.strip() if flow else None)

__all__ = [
    "StartFlowCommand",
    "CancelFlowCommand",
    "ChangeFlowCommand",
]
    

        

    
