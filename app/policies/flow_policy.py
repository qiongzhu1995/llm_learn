"""
Flow策略

基于Flow定义执行对话流程的策略。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional,Any,TYPE_CHECKING

from app.policies.base_policy import Policy, PolicyPrediction
from app.dialogue_understanding.flow.flow import FlowsList
from app.dialogue_understanding.stack.stack_frame import FlowStackFrame
from app.dialogue_understanding.flow.flow_executor import FlowExecutor
from app.shared.config import settings
from app.shared.logger import logger
if TYPE_CHECKING:
    from app.core.tracker import DialogueStateTracker
    from app.core.domain import Domain

@dataclass
class FlowPolicyConfig:
    """Flow策略配置"""
    priority:int = 100 # 最高优先级
    max_steps_per_turn:int = 50 # 每轮最大执行步数（防止死循环）

class FlowPolicy(Policy):
    """基于Flow定义执行对话流程。当对话栈中有活动的Flow时，
       此策略会根据Flow步骤决定下一步动作"""

    DEFAULT_PRIORITY:int = 100

    def __init__(self, config:Optional[FlowPolicyConfig] = None,flows:Optional[FlowsList] = None,**kwargs:Any) -> None:
        """初始化Flow策略"""
        super().__init__(config=config or FlowPolicyConfig(),**kwargs)
        self.flows = flows or FlowsList()
        self.excutor = FlowExecutor(flows=self.flows)
    
    def should_predict(self, tracker:"DialogueStateTracker") -> bool:
        """ 判断是否需要执行预测动作"""
        return tracker.active_flow is not None
    
    async def predict_action(self, tracker:"DialogueStateTracker",domain:Optional["Domain"] = None,flows:Optional[FlowsList] = None,**kwargs:Any) -> PolicyPrediction:
        """ 预测下一步的动作"""

        # 如果没有活动的Flow，放弃预测
        if not tracker.active_flow:
            logger.warning("没有活动的Flow,放弃预测")
            return PolicyPrediction.abstain()
        
        # 使用提供的flows或初始化的flows
        if flows:
            self.excutor.flows = flows
        
        # 检查是否有正在完成的flow
        flow_frame = tracker.dialogue_stack.top_flow_frame()
        if flow_frame and flow_frame.completing:
            completed_flow = flow_frame.flow_id
            logger.info(f"Flow {completed_flow}正在完成,触发action_flow_completed")

            # 重置 scoped slots
            self._reset_scoped_slots(tracker,completed_flow)
            # 结束flow
            tracker.end_flow()
            return PolicyPrediction(
                action="action_flow_completed",
                confidence=1.0,
                events=[],
                policy_name=self.name,
                metadata={
                    "flow_completed": True,
                    "completed_flow": completed_flow,
                }
            )
        
        # 执行flow循环处理，直到需要用户输入或执行动作）
        try:
            logger.info(f"[FlowPolicy] 开始执行Flow循环处理，直到需要用户输入或执行动作")
            max_iterations = self.config.max_steps_per_turn
            all_events = []

            for i in range(max_iterations):
                logger.info(f"[FlowPolicy] 第 {i+1} 次迭代")
                result = self.excutor.excute_next_step(tracker)
                all_events.extend(result.events)

                # 优先检查是否需要收集槽位 （collect 步骤会同时设置 action 和 slot_to_collect）
                # 必须先处理 slot_to_collect，否则会走 action 分支而丢失 metadata 信息
                if result.slot_to_collect:
                    logger.info(f"[FlowPolicy] 正在收集槽位: {result.slot_to_collect}")

                    # 更新slot_to_collect 数学
                    flow_frame = tracker.dialogue_stack.top_flow_frame()
                    if flow_frame:
                        flow_frame.slot_to_collect = result.slot_to_collect
                    
                    # 使用collect 步骤指定的action,或者默认的utter_ask_xxx
                    action = result.action or f"utter_ask_{result.slot_to_collect}"

                    # 构建 metadata，包含 fallback_action 以支持 action_ask_xxx 降级
                    prediction_metadata = {
                        "slot_to_collect": result.slot_to_collect,
                        "next_step_id": result.next_step_id,
                    }

                    # 构建 fallback_action 如果需要
                    if result.metadata.get("fallback_action"):
                        prediction_metadata["fallback_action"] = result.metadata["fallback_action"]
                    logger.info(f"[FlowPolicy] 收集槽位完成,返回预测结果: action={action}, metadata={prediction_metadata}")

                    return PolicyPrediction(
                        action=action,
                        confidence=1.0,
                        events=all_events,
                        policy_name=self.name,
                        metadata=prediction_metadata
                    )
                # 如果有动作需要执行 # 构建 metadata，包含 fallback_action 以支持 action_ask_xxx 降级
                if result.action:
                    logger.info(f"[FlowPolicy] 执行动作: {result.action}")

                    # 检查是否是最后一个动作
                    is_final_action = (result.flow_completed 
                                      or (isinstance(result.next_step_id,str) 
                                      and result.next_step_id == "END"))
                    
                    if is_final_action:
                        completed_flow = tracker.active_flow
                        logger.info(f"[FlowPolicy] 执行最后一个动作: {result.action},触发action_flow_completed")
                        # 设置completing标志 下一轮predict时触发action_flow_completed
                        flow_frame = tracker.dialogue_stack.top_flow_frame()
                        if flow_frame:
                            flow_frame.completing = True
                            # 清除slot_to_collect 避免下一轮重复收集
                            flow_frame.slot_to_collect = None
                        elif result.flow_completed:
                            #更新步骤
                            self.excutor.advance_step(tracker,result.next_step_id)
                        # 检查下一步是否是 collect 步骤，如果是则预设 slot_to_collect
                        # 这样 understand_node 在下一轮可以获取到 current_slot 信息
                            self._preset_slot_to_collect_if_needed(tracker,result.next_step_id)
                        
                        logger.info(f"[FlowPolicy] 执行最后一个动作完成,返回预测结果: action={result.action}, metadata={result.metadata}")
                        return PolicyPrediction(
                            action=result.action,
                            confidence=1.0,
                            events=all_events,
                            policy_name=self.name,
                            metadata=self._build_action_metadata(tracker,result.next_step_id,is_final_action)
                        )
                    # 如果flow已完成且没有下一步，返回flow_completed
                    if result.flow_completed:
                        completed_flow = tracker.active_flow
                        logger.info(f"[FlowPolicy] flow {completed_flow} 已完成,触发action_flow_completed")
                        # 在end_flow之前重置 scoped slots
                        if completed_flow:
                            self._reset_scoped_slots(tracker,completed_flow)
                            # 结束flow
                            tracker.end_flow()
                            logger.info(f"[FlowPolicy] flow {completed_flow} 已完成,返回预测结果: action=action_flow_completed, metadata={self._build_action_metadata(tracker,result.next_step_id,is_final_action)}")
                            return PolicyPrediction(
                                action="action_flow_completed",
                                confidence=1.0,
                                events=all_events,
                                policy_name=self.name,
                                metadata={"flow_completed": True, "completed_flow": completed_flow}
                            )
                    # 如果有下一步没有动作，推进并继续执行
                    if result.next_step_id:
                        logger.info(f"[FlowPolicy] 执行下一步: {result.next_step_id}")
                        # 清除slot_to_collect 避免下一轮重复收集
                        flow_frame = tracker.dialogue_stack.top_flow_frame()
                        if flow_frame:
                            flow_frame.slot_to_collect = None
                        self.excutor.advance_step(tracker,result.next_step_id)
                        logger.info(f"[FlowPolicy] 执行下一步完成,返回预测结果: action=None, metadata={self._build_action_metadata(tracker,result.next_step_id,is_final_action)}")
                        continue

                    # 没有动作也没有下一步 等待用户输入
                    break 
                return PolicyPrediction(
                    action=settings.actions.listen,
                    confidence=1.0,
                    events=all_events,
                    policy_name=self.name
                )
        except Exception as e:
            logger.error(f"[FlowPolicy] 执行Flow循环处理失败: {e}")
            return PolicyPrediction(
                action=settings.actions.default_fallback,
                confidence=0.5,
                events=all_events,
                policy_name=self.name,
                metadata={"error": str(e)}
            )




    def _reset_scoped_slots(self, tracker:"DialogueStateTracker", flow_id:str) -> None:
        """
         重置 flow 作用域内的槽位。
        
                            }
                        )
                    else:
                        logger.info(f"[FlowPolicy] 执行非最后一个动作: {result.action},继续执行下一个动作")
                        return PolicyPrediction(
                            action=result.action,
                            confidence=1.0,
                            events=all_events,
        当 flow 结束时，重置在该 flow 中收集的槽位（除非配置了 reset_after_flow_ends=False
        或者槽位在 persisted_slots 列表中）。
        
        这确保了不同 flow 之间的槽位隔离，避免一个 flow 设置的槽位被下一个 flow 错误地复用。
        
        Args:
            tracker: 对话状态追踪器
            flow_id: 结束的 flow ID
        """
        flow = self.excutor.flows.get_flow(flow_id)
        if not flow:
            logger.warning(f"[FlowPolicy]Flow {flow_id}不存在,跳过槽位重置")
            return
        
        logger.info(f"[FlowPolicy] flow {flow_id} 作用域内的槽位重置完成,开始重置 scoped slots")

        # 重置 scoped slots
        persisted_slots = set(flow.persisted_slots)
        not_resettable_slots = set()

        # 遍历flow 中的collect步骤
        from app.dialogue_understanding.flow.flow import StepType
        for step in flow.steps:
            # 如果是collect步骤 并且有collect槽位
            if step.step_type == StepType.COLLECT and step.collect:
                slot_name = step.collect
                # 检查是否需要重置
                if step.reset_after_flow_ends and slot_name not in persisted_slots:
                    # 需要重置
                    if slot_name in tracker.slots:
                        old_value = tracker.slots[slot_name].value
                        tracker.slots[slot_name].reset()
                        logger.info(f"[FlowPolicy] slot {slot_name} 重置完成,旧值: {old_value}")
                    else:
                        logger.warning(f"[FlowPolicy] slot {slot_name} 不存在,跳过重置")
                else:
                    not_resettable_slots.add(slot_name)
                    logger.debug(
                        f"[FlowPolicy] 槽位 {slot_name} 不需要重置 "
                        f"(reset_after_flow_ends={step.reset_after_flow_ends}, "
                        f"persisted={slot_name in persisted_slots})"
                    )
         # 重置 set_slot 步骤设置的槽位（除非在 not_resettable_slots 或 persisted_slots 中）
        for step in flow.steps:
            if step.step_type == StepType.SET_SLOT and step.slot_name:
                slot_name = step.slot_name
                # 检查是否需要重置
                if step.reset_after_flow_ends and slot_name not in persisted_slots:
                    # 需要重置
                    if slot_name in tracker.slots:
                        old_value = tracker.slots[slot_name].value
                        tracker.slots[slot_name].reset()
                        logger.info(f"[FlowPolicy] slot {slot_name} 重置完成,旧值: {old_value}")


    def _preset_slot_to_collect_if_needed(self, tracker:"DialogueStateTracker",next_step_id:str) -> None:
        """
        预设 slot_to_collect（如果下一步是 collect 步骤）。
        
        当执行完 action 步骤后推进到 collect 步骤时，
        预先设置 slot_to_collect，这样下一轮 understand_node 
        可以在 prompt 中告诉 LLM 当前正在收集哪个槽位。
        
        Args:
            tracker: 对话状态追踪器
            next_step_id: 下一步骤 ID
        """
        
        flow_id = tracker.active_flow
        if not flow_id:
            logger.warning(f"[FlowPolicy] 没有活动的Flow,跳过预设 slot_to_collect")
            return
        
        flow = self.excutor.flows.get_flow(flow_id)
        if not flow:
            logger.warning(f"[FlowPolicy] Flow {flow_id}不存在,跳过预设 slot_to_collect")
            return
        
        next_step = flow.get_step(next_step_id)
        if not next_step:
            logger.warning(f"[FlowPolicy] 下一步骤 {next_step_id}不存在,跳过预设 slot_to_collect")
            return
        
        # 检查下一步是否是 collect 步骤
        from app.dialogue_understanding.flow.flow import StepType
        if next_step.step_type == StepType.COLLECT and next_step.collect:
            flow_frame = tracker.dialogue_stack.top_flow_frame()
            if flow_frame:
                flow_frame.slot_to_collect = next_step.collect
                logger.info(f"[FlowPolicy] 预设 slot_to_collect: {next_step.collect}")
                
    def _build_action_metadata(self, tracker:"DialogueStateTracker", next_step_id:str, is_final_action:bool) -> dict[str, Any]:
        """构建action的 metadata"""
        metadata = {
            "next_step_id": next_step_id,
            "flow_completed": is_final_action
        }
        return metadata

    def set_flows(self, flows:FlowsList) -> None:
        """设置flows"""
        self.excutor.flows = flows
        self.excutor.set_flows(flows)

__all__ = ["FlowPolicy", "FlowPolicyConfig"]