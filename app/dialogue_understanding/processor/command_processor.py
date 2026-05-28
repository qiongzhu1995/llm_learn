"""
命令处理器

负责执行命令并更新对话状态。
"""

from __future__ import annotations

from dataclasses import dataclass,field
from typing import Any,Optional,TYPE_CHECKING
from app.dialogue_understanding.commands.base import Command
from app.shared.logger import logger
from app.dialogue_understanding.commands.flow_commands import StartFlowCommand,CancelFlowCommand,ChangeFlowCommand
from app.dialogue_understanding.commands.slot_commands import SetSlotCommand
if TYPE_CHECKING:
    from app.core.domain import Domain
    from app.dialogue_understanding.flow import FlowsList
    from app.core.tracker import DialogueStateTracker

@dataclass
class ProcessorConfig:
    """处理器配置"""
    allow_parallel_commands:bool = True # 是否允许并行执行命令
    validate_flows:bool = True # 是否验证flows存在
    validate_slots:bool = True # 是否验证slots存在

@dataclass
class ProcessorResult:
    """处理器结果"""
    events:list[dict[str,Any]] = field(default_factory=list) # 产生的事件列表
    commands_executed:int = 0 # 执行的命令数量 
    errors:list[str] = field(default_factory=list) # 错误信息列表
    next_action:Optional[str] = None # 下一个动作
    response_type:str = "none"  # 响应类型（flow, chitchat, knowledge, cannot_handle等）
    metadata:dict[str,Any] = field(default_factory=dict) # 元数据

    @property
    def success(self) -> bool:
        """是否成功"""
        return self.commands_executed > 0 and len(self.errors) == 0

class CommandProcessor:
    """命令处理器。
    
    负责执行命令并更新对话状态。这是对话理解模块的核心组件之一。
    
    处理流程：
    1. 接收命令列表
    2. 按顺序执行每个命令
    3. 更新对话状态（Tracker, Stack）
    4. 返回产生的事件和下一步动作
    """
    def __init__(self,
                config:ProcessorConfig = None,
                domain:Optional["Domain"] = None,
                flows:Optional[list[Any]] = None,
                    ) -> None:
        """初始化命令处理器"""
        self.config = config or ProcessorConfig()
        self.domain = domain
        self.flows = flows or []
        self._flows_ids = set(getattr(f,'id',str(f)) for f in self.flows)
    
    def process(self,commands:list[Command],tracker:"DialogueStateTracker") -> ProcessorResult:
        """处理命令"""
        result = ProcessorResult()

        if not commands:
            logger.debug("没有命令需要处理")
            return result

        logger.debug("共有{len(commands)}个命令需要处理")

        # 基于 force_slot_filling 过滤collect中的无效命令
        commands = self._filter_commands_during_collect(commands,tracker)

        if not commands:
            logger.debug("所有命令在收集阶段都被过滤掉，直接返回空结果")
            return result
        
        logger.debug("过滤后还有{len(commands)}个命令需要处理")
        for command in commands:
            try:
                # 执行命令
                logger.debug(f"开始执行命令: {command.command_name()}")
                events = self._execute_command(command,tracker)
                result.events.extend(events)
                result.commands_executed += 1
                logger.debug(f"执行命令成功: {command.command_name()}")

                # 确定下一步动作
                self._determine_next_action(tracker,result)

                return result

                
            except Exception as e:
                logger.error(f"执行命令失败: {e}")
                result.errors.append(str(e))
    
    def set_domain(self,domain:"Domain") -> None:
        """设置Domain对象"""
        self.domain = domain
    
    def set_flows(self,flows:list[Any]) -> None:
        """设置Flows对象"""
        self.flows = flows
        self._flows_ids = set[Any | str](getattr(f,'id',str(f)) for f in self.flows) if flows else set()

    
    def validate_command(self,command:Command) -> bool:
        """验证命令是否有效"""
        # 验证startflowcommand的flow是否存在、
        if isinstance(command,StartFlowCommand):
            if self.config.validate_flows and self._flows_ids:
                return command.flow in self._flows_ids
            
            # 验证setslotcommand的slot是否存在
            if isinstance(command,SetSlotCommand):
                if self.config.validate_slots and self.domain:
                    return command.name in self.domain.slots
        
        return True

    def filter_valid_commands(self,commands:list[Command]) -> list[Command]:
        """过滤有效的命令"""
        return [command for command in commands if self.validate_command(command)]
    
    def _determine_next_action(self,tracker:"DialogueStateTracker",result:ProcessorResult) -> None:
        """确定下一步动作。
        
        根据当前状态和处理结果，决定下一步应该执行什么动作。
        
        注意：对于已经在 Command.run() 中压入栈帧的 Command 类型
        （chitchat, knowledge, cannot_handle, human_handoff），
        不设置 next_action，让 Policy 通过检测栈帧来决定动作。
        
        Args:
            tracker: 对话状态追踪器
            result: 处理结果
        """
        # 根据响应类型决定下一步
        if result.response_type == "flow":
            # flow已启动，执行flow下一步
            if tracker.active_flow:
                result.next_action = f"action_run_flow_{tracker.active_flow}"
            else:
                result.next_action = "action_listen"
        
        elif result.response_type == "cancel_flow":
            result.next_action = "action_cancel_flow"
        
        elif result.response_type == "change_flow":
            result.next_action = "action_change_flow"
        
        elif result.response_type == "session_start":
            result.next_action = "action_session_start"
        
        elif result.response_type == "restart":
            result.next_action = "action_restart"
        
        elif result.response_type == "clarify":
            result.next_action = "action_clarify"
    
            # 以下类型的 Command 已经在 run() 中压入了栈帧，
        # 不设置 next_action，让 Policy 检测栈帧来决定动作：
        # - chitchat → ChitChatStackFrame → Policy 返回 action_send_text
        # - knowledge → SearchStackFrame → Policy 返回 action_send_text
        # - cannot_handle → CannotHandleStackFrame → Policy 返回 action_send_text
        # - human_handoff → HumanHandoffStackFrame → Policy 返回 action_send_text

        elif result.response_type in ("chitchat","knowledge","cannot_handle","human_handoff"):
            pass

        else:
            # 默认情况处理
            # 如果存在活跃 flow，不设置 next_action，让 FlowPolicy 决定下一步
            # 这对于按钮点击 SetSlots 等情况尤为重要
            if tracker.active_flow:
                # 不设置 next_action，让 FlowPolicy 处理 flow 的下一步
                pass
            else:
                # 不存在活跃 flow，设置为 action_listen
                result.next_action = "action_listen"


            

                
    
    def _execute_command(self,command:Command,tracker:"DialogueStateTracker") -> list[dict[str,Any]]:
        """执行命令并返回产生的事件列表
        
        Args:
            command: 要执行的命令
            tracker: 对话状态追踪器
            
        Returns:
            list[dict[str,Any]]: 产生的事件列表

        """
        events = command.run(tracker,self.flows)

        # 记录命令到tracker
        tracker.add_command([command.as_dict()])

        return events


    
    def _filter_commands_during_collect(self,commands:list[Command],tracker:"DialogueStateTracker") -> list[Command]:
        """基于 force_slot_filling 机制，过滤 collect 步骤中的无效命令。
        
        当处于 collect 步骤（正在收集某个槽位）时：
        1. 只保留设置当前槽位的 SetSlotCommand
        2. 丢弃其他 SetSlotCommand（防止 LLM 同时设置多个槽位）
        3. 丢弃 StartFlowCommand（防止 LLM 错误触发新流程）
        4. 保留其他命令（如 CancelFlowCommand）
        
        Args:
            commands: 原始命令列表
            tracker: 对话状态追踪器
            
        Returns:
            过滤后的命令列表
        """
        slot_to_collect =self._get_current_slot_to_collect(tracker)
        if not slot_to_collect:
            logger.debug("不在收集阶段，直接返回原始命令列表")
            return commands
        
        logger.debug(f"[force_slot_filling] 当前正在收集的槽位为: {slot_to_collect}")
        filtered_commands = []
        for command in commands:
            if isinstance(command,SetSlotCommand):
                if command.name == slot_to_collect:
                    filtered_commands.append(command)
                    logger.debug(f"[force_slot_filling] 保留SetSlotCommand: {command.name}={command.value}")
                
                else:
                    logger.debug(f"[force_slot_filling] 忽略非当前槽位的设置: {command.name}")
            
            elif isinstance(command,StartFlowCommand):
                logger.debug(f"[force_slot_filling] 忽略StartFlowCommand: {command.flow_id}")
            
            else:
                filtered_commands.append(command)
                logger.debug(f"[force_slot_filling] 保留其他命令: {command.name}")
        
        return filtered_commands
        




    
    def _get_current_slot_to_collect(self,tracker:"DialogueStateTracker") -> Optional[str]:
        """获取当前正在收集的槽位名称。
        
        从 DialogueStack 的 FlowStackFrame 中获取 slot_to_collect。
        
        Args:
            tracker: 对话状态追踪器
            
        Returns:
            当前正在收集的槽位名，如果不在 collect 步骤则返回 None
        """
        if not hasattr(tracker,'dialogue_stack'):
            logger.warning("对话状态追踪器没有对话栈，无法获取当前正在收集的槽位")
            return None
        
        flow_frame = tracker.dialogue_stack.top_flow_frame() # 获取当前流程栈顶的帧
        if flow_frame and hasattr(flow_frame,'slot_to_collect'):
            return flow_frame.slot_to_collect
        return None


def process_commands(
    commands:list[Command],
    tracker:"DialogueStateTracker",
    domain:"Domain" = None,
    flows:Optional[list[Any]] = None
    ) -> ProcessorResult:
    """便捷函数 处理命令"""
    processor = CommandProcessor(domain=domain,flows=flows)
    return processor.process(commands,tracker)

__all__ = ["process_commands","CommandProcessor","ProcessorConfig","ProcessorResult"]
