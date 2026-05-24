"""
对话栈

管理对话上下文的栈结构，支持Flow嵌套、中断和恢复。
"""

from dataclasses import dataclass,field
from typing import List,Optional,Iterator,Any
from app.dialogue_understanding.stack.stack_frame import StackFrame
from app.dialogue_understanding.stack.stack_frame import FlowStackFrame,FrameState,create_frame_from_dict

@dataclass
class DialogueStack:
    """
        管理对话过程中的上下文栈，支持：
    - Flow嵌套执行
    - 中断和恢复
    - 模式触发
    
    栈采用后进先出(LIFO)结构，栈顶是当前活动的帧。
    """
    frames:list[StackFrame] = field(default_factory=list)

    #=== 栈基础操作 ===

    def push(self, frame: StackFrame) -> None:
        """将栈压入栈顶"""
        self.frames.append(frame)

    def pop(self) -> Optional[StackFrame]:
        """将栈顶弹出"""
        return self.frames.pop() if self.frames else None

    def peek(self) -> Optional[StackFrame]:
        """获取栈顶元素"""
        return self.frames[-1] if self.frames else None
    
    def is_empty(self) -> bool:
        """判断栈是否为空"""
        return len(self.frames) == 0

    def size(self) -> int:
        """获取栈的大小"""
        return len(self.frames)
    
    def clear(self) -> None:
        """清空栈"""
        self.frames.clear()

    def __iter__(self) -> Iterator[StackFrame]:
        """从栈顶到栈底迭代"""
        return reversed(self.frames).__iter__()

    def __len__(self) -> int:
        """获取栈的大小"""
        return len(self.frames)
    
    def bottom_up(self) -> Iterator[StackFrame]:
        """从栈底到栈顶迭代"""
        return iter(self.frames)

    #=== 基础操作 ===
    def top_flow_frame(self) -> Optional[FlowStackFrame]:
        """获取栈顶的Flow帧"""
        for frame in self:
            if isinstance(frame, FlowStackFrame):
                return frame
        return None
    
    def active_flow_frame(self) -> Optional[FlowStackFrame]:
        """获取当前活动的Flow帧
        return 栈顶的活动状态的Flow帧
        """
        for frame in self:
            if isinstance(frame, FlowStackFrame) and frame.is_active():
                return frame
        return None

    def push_flow_frame(self, flow_id:str, step_id:str="START") -> FlowStackFrame:
        """压入新的Flow帧
        
           Args:
           flow_id: Flow ID
           step_id: 步骤ID
           Returns:
               创建新的Flow帧并压入栈顶
        """
        frame = FlowStackFrame(flow_id=flow_id, step_id=step_id)
        self.push(frame)
        return frame
    
    def find_flow_frame(self, flow_id:str) -> Optional[FlowStackFrame]:
        """查找指定的Flow帧
        
           Args:
           flow_id: Flow ID
           Returns:
               查找指定的Flow帧
        """
        for frame in self:
            if isinstance(frame, FlowStackFrame) and frame.flow_id == flow_id:
                return frame
        return None
    
    def has_flow_frame(self, flow_id:str) -> bool:
        """判断是否存在指定的Flow帧"""
        return self.find_flow_frame(flow_id) is not None
    
    def get_all_flow_ids(self) -> List[str]:
        """获取所有的Flow ID的ID列表"""
        return [frame.flow_id for frame in self if isinstance(frame, FlowStackFrame)]
    
    def pop_to_flow(self, flow_id:str) -> list[StackFrame]:
        """弹出栈顶到指定的Flow帧 弹出目标Flow之上的所有帧（不包括目标Flow本身）
        
           Args:
           flow_id: Flow ID
           Returns:
               被弹出的帧列表
        """
        popped_frames = []
        while self.frames:
            top = self.peek()
            if isinstance(top, FlowStackFrame) and top.flow_id == flow_id:
                break
            popped_frames.append(self.pop())
        return popped_frames
    
    def find_frame(self, frame_id:str) -> Optional[StackFrame]:
        """根据帧ID查找帧"""
        for frame in self:
            if frame.frame_id == frame_id:
                return frame
        return None
    
    def find_frames_of_type(self, frame_type:type[StackFrame]) -> list[StackFrame]:
        """根据帧类型查找帧"""
        return [frame for frame in self if isinstance(frame, frame_type)]

    def remove_frame(self, frame:StackFrame) -> None:
        """删除指定的帧"""
        for i,frame in enumerate(self.frames):
            if frame.frame_id == frame.frame_id:
                return self.frames.pop(i)
        return None
    
    #=== 序列化 ===

    def as_dict(self) -> dict[str, Any]:
        """将栈转换为字典"""
        return {"frames": [frame.as_dict() for frame in self]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DialogueStack":
        """从字典创建对话栈"""
        frames = []
        for frame_data in data.get("frames",[]):
            try:
                frame = create_frame_from_dict(frame_data)
                frames.append(frame)
            except Exception as e:
                # 跳过无法创建的帧
                continue
        return cls(frames=frames) # 创建对话栈并返回


    def copy(self) -> "DialogueStack":
        """创建对话栈的副本"""
        return DialogueStack.from_dict(self.as_dict())
    
    def __repr__(self) -> str:
        """返回对话栈的字符串表示"""
        if self.is_empty():
            return "DialogueStack(empty)"
        
        frame_strs = []
        for frame in self:
            if isinstance(frame, FlowStackFrame):
                frame_strs.append(f"Flow: {frame.flow_id} (step: {frame.step_id})")
            else:
                frame_strs.append(f"{frame.frame_id}: {frame.__class__.__name__}")
        return f"DialogueStack(frames={', '.join(frame_strs)})"

#
# __all__用于指定当from xxx import *导入时导出的名称
__all__ = ["DialogueStack"]
    
