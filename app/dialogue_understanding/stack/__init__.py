# 文件说明：包初始化。
from app.dialogue_understanding.stack.dialogue_stack import DialogueStack
from app.dialogue_understanding.stack.stack_frame import StackFrame,FlowStackFrame,FrameState,create_frame_from_dict

# 导出所有公共接口,只有这些接口可以被外部模块使用
__all__ = ["DialogueStack", "StackFrame", "FlowStackFrame", "FrameState", "create_frame_from_dict"]