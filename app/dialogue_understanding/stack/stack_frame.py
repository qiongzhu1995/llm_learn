"""
栈帧定义

定义对话栈中的各种帧类型。
"""
import uuid
from typing import Any, Optional, Type
from abc import abstractmethod
from enum import Enum
from dataclasses import dataclass,field,fields

from app.shared.logger import logger

def generate_frame_id() -> str:
    """生成帧ID"""
    return str(uuid.uuid4().hex[:8])

# 注册栈帧类型字典
_frame_types_registry: dict[str, Type["StackFrame"]] = {}

def register_frame_type(cls: Type["StackFrame"]) -> Type["StackFrame"]:
    """注册栈帧类型装饰器"""
    _frame_types_registry[cls.frame_type()] = cls
    return cls


class FrameState(str,Enum):
    """帧状态枚举。"""
    ACTIVE = "active"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"
    CANCELLED = "cancelled"

class FlowFrameType(str,Enum):
    """Flow帧类型枚举。"""
    REGULAR = "regular" # 常规帧
    INTERRUPT = "interrupt" # 中断帧
    LINK = "link" # 链接帧

@dataclass
class StackFrame:
    """栈帧基类 栈帧表示对话栈中的一个条目，记录对话上下文的一个状态点"""

    # 帧ID 唯一标识一个栈帧
    frame_id: str = field(default_factory=generate_frame_id)
    # 帧状态 表示栈帧当前的状态 默认为活跃状态
    state: FrameState = FrameState.ACTIVE

    @classmethod
    @abstractmethod
    def frame_type(cls) -> str:
        """返回帧类型标识"""
        # 使用 raise NotImplementedError 是为了强制所有继承 StackFrame 的子类都必须实现 frame_type 方法。
        # 如果子类未实现该方法，调用时就会抛出异常，提醒开发者该抽象方法未被正确覆写，防止出现只调用了基类的情况。
        raise NotImplementedError("子类必须实现该方法") 

    @classmethod
    def from_dict[T: "StackFrame"](cls: type[T], data: dict[str, Any]) -> T:
        """从字典创建栈帧（通用实现：仅恢复 frame_id/state）。"""
        state = data.get("state", FrameState.ACTIVE.value)
        if isinstance(state, str):
            state = FrameState(state)
        return cls(
            frame_id=data.get("frame_id", generate_frame_id()),
            state=state,
        )

    def as_dict(self) -> dict[str, Any]:
        """将栈帧转换为字典"""
        data = {}
        # 遍历该数据类的所有字段，用于后续将每个字段的值序列化到字典中
        for f in fields(self):
            # 获取字段名和值
            value = getattr(self, f.name)
            # 如果字段值是枚举类型，则序列化为其对应的 value（字符串），否则原样赋值
            if isinstance(value, Enum):
                data[f.name] = value.value
            else:
                data[f.name] = value
        data["type"] = self.frame_type()
        return data

    def is_active(self) -> bool:
        """判断栈帧是否处于活跃状态"""
        return self.state == FrameState.ACTIVE

    def is_completed(self) -> bool:
        """判断栈帧是否处于完成状态"""
        return self.state == FrameState.COMPLETED

    def complete(self) -> None:
        """将栈帧状态设置为完成状态"""
        self.state = FrameState.COMPLETED
 
    def interrupt(self) -> None:
        """将栈帧状态设置为中断状态"""
        self.state = FrameState.INTERRUPTED

    def cancel(self) -> None:
        """将栈帧状态设置为取消状态"""
        self.state = FrameState.CANCELLED
    
@register_frame_type
@dataclass
class FlowStackFrame(StackFrame):
    """表示一个正在执行的Flow"""
    # Flow ID
    flow_id:str = ""
    # 当前步骤 ID
    step_id:str = "START"
    # Flow 帧类型
    flow_frame_type:FlowFrameType = FlowFrameType.REGULAR
    # 当前正在收集的槽位名称
    slot_to_collect:Optional[str] = None
    # Flow是否正在完成
    completing:bool = False

    @classmethod
    def frame_type(cls) -> str:
        """返回帧类型标识"""
        return "flow"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FlowStackFrame":
        """从字典创建Flow栈帧"""
        state = data.get("frame_id",generate_frame_id())

        if isinstance(state, str):
            state = FrameState(state)
        
        flow_frame_type = data.get("flow_frame_type") or data.get("frame_type",FlowFrameType.REGULAR.value)

        if isinstance(flow_frame_type, str):
            flow_frame_type = FlowFrameType(flow_frame_type)
        
        return FlowStackFrame(
            frame_id=data.get("frame_id",generate_frame_id()),
            state=state,
            flow_id=data.get("flow_id",""),
            step_id=data.get("step_id","START"),
            flow_frame_type=flow_frame_type,
            slot_to_collect=data.get("slot_to_collect"),
            completing=data.get("completing",False)
        )

    def advance_to_step(self, step_id: str) -> None:
        """前进到指定步骤"""
        self.step_id = step_id
    
    def is_interrupt(self) -> None:
        """判断是否是中断帧"""
        return self.flow_frame_type == FlowFrameType.INTERRUPT

@register_frame_type
@dataclass
class SearchStackFrame(StackFrame):
    """搜索栈帧。
    
    表示正在执行知识库搜索（RAG）。
    不存储query，从latest_message获取。
    """

    @classmethod
    def frame_type(cls) -> str:
        """返回帧类型标识"""
        return "search"
    
@register_frame_type
@dataclass
class ChitChatStackFrame(StackFrame):
    """闲聊栈帧。
    
    表示正在执行闲聊。
    """
    @classmethod
    def frame_type(cls) -> str:
        """返回帧类型标识"""
        return "chit_chat"
    
@register_frame_type
@dataclass
class CannotHandleStackFrame(StackFrame):
    """无法处理栈帧。
    
    表示系统无法处理用户请求。
    """
    # 无法处理的原因
    reason:str = ""

    @classmethod
    def frame_type(cls) -> str:
        """返回帧类型标识"""
        return "cannot_handle"
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CannotHandleStackFrame":
        """从字典创建无法处理栈帧"""
        state = data.get("state",FrameState.ACTIVE.value)
        if isinstance(state, str):
            state = FrameState(state)
        return CannotHandleStackFrame(
            frame_id=data.get("frame_id",generate_frame_id()),
            state=state,
            reason=data.get("reason","")
        )

@register_frame_type
@dataclass
class CompleteStackFrame(StackFrame):
    """完成栈帧。
    
        表示所有Flow已完成，系统处于空闲状态。
    由 FlowPolicy 在 Flow 完成后自动压入。
    由 EnterpriseSearchPolicy 处理，生成询问用户是否还有其他需求的响应。
    """
    # 刚完成的Flow ID
    previous_flow_id:str = ""
    @classmethod
    def frame_type(cls) -> str:
        """返回帧类型标识"""
        return "complete"
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CompleteStackFrame":
        """从字典创建完成栈帧"""
        state = data.get("state",FrameState.ACTIVE.value)

        return CompleteStackFrame(
            frame_id=data.get("frame_id",generate_frame_id()),
            state=state,
            previous_flow_id=data.get("previous_flow_id","")
        )

@register_frame_type
@dataclass
class HumanHandoffStackFrame(StackFrame):
    """人工转接栈帧。
    
    表示需要人工转接。
    """
    # 需要人工转接的原因
    reason:str = ""
    @classmethod
    def frame_type(cls) -> str:
        """返回帧类型标识"""
        return "human_handoff"
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HumanHandoffStackFrame":
        """从字典创建人工转接栈帧"""
        state = data.get("state",FrameState.ACTIVE.value)
        if isinstance(state, str):
            state = FrameState(state)
        return HumanHandoffStackFrame(
            frame_id=data.get("frame_id",generate_frame_id()),
            state=state,
            reason=data.get("reason","")
        )

def create_frame_from_dict(data: dict[str, Any]) -> StackFrame:
    """从字典创建栈帧"""
    frame_type = data.get("type")
    if frame_type is None:
        logger.error(f"栈帧类型不能为空: {data}")
        raise ValueError("栈帧类型不能为空")

    if frame_type not in _frame_types_registry:
        logger.error(f"未知栈帧类型: {frame_type}")
        raise ValueError(f"未知栈帧类型: {frame_type}")
    return _frame_types_registry[frame_type].from_dict(data)
