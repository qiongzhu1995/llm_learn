"""
动作节点

负责执行策略预测的动作。
"""
from __future__ import annotations

from typing import Any,Optional,TYPE_CHECKING
from app.shared.logger import logger
from app.agent.actions import get_action,ActionResult
from app.core.tracker import BotMessage
if TYPE_CHECKING:
    from app.agent.graph.state import MessageProcessingState

async def action_node(state:"MessageProcessingState") -> dict[str, Any]:
    """动作节点：执行预测的动作。
    
    该节点执行以下步骤：
    1. 从 current_prediction 获取动作名称
    2. 查找并实例化对应的 Action
    3. 执行 Action.run()
    4. 将响应添加到 final_responses
    5. 将机器人消息添加到 tracker
    
    Args:
        state: 当前图状态
        
    Returns:
        状态更新字典
    """
    tracker = state['tracker']
    domain = state.get('domain')
    metadata = state.get('metadata',{})
    current_prediction = state.get('current_prediction')
    final_responses = list(state.get('final_responses',[]))
    action_count = state.get('action_count',0)

    # 获取目录生成器配置,用于闲聊动作
    command_generator = state.get('_command_generator')
    if not current_prediction or current_prediction.action is None:
        logger.warning(f"[action_node] 没有预测动作，跳过执行")
        return {
            "current_acion_result":None,
            "action_count":action_count,
            "node_history":state.get("node_history",[]) + ["action"],
        }
    action_name = current_prediction.action
    logger.info(f"[action_node] 执行动作: {action_name}...")

    try:
        # 查找动作
        action = get_action(action_name)

        if action is None:
            logger.warning(f"[action_node] 未找到动作: {action_name}")
            return {
                "current_acion_result":ActionResult(success=False),
                "action_count":action_count + 1,
                "node_history":state.get("node_history",[]) + ["action"],
            }
        
        # 合并元数据
        kwargs = dict(metadata)
        kwargs.update({current_prediction.metadata} or {})

        # 如果是闲聊动作，传递LLM配置
        if action_name == "action_chitchat_response" and command_generator:
            config = command_generator.config
            kwargs['llm_config'] = {
                'type':config.type,
                'model':config.model,
                'apo_key':config.apo_key,
                'api_base':config.api_base,
                'enable_thinking':config.enable_thinking,
            }
        
        # 执行动作
        result = await action.run(tracker,domain,**kwargs)
        logger.info(f"[action_node] 动作执行结果: {result}")

        # 如果是 utter 动作但没有产生响应，尝试使用 fallback_action
        # 这是为了支持 collect 步骤中 action_ask_xxx 优先于 utter_ask_xxx 的机制
        prediction_metadata = current_prediction.metadata or {}
        fallback_action_name = prediction_metadata.get('fallback_action')

        if (not result.responses and action_name.startswith('utter_') and fallback_action_name):
            logger.info(f"[action_node] 动作 {action_name} 没有产生响应，尝试使用 fallback_action: {fallback_action_name}")
            fallback_action = get_action(fallback_action_name)
            if fallback_action:
                fallback_result = await fallback_action.run(tracker,domain,**kwargs)
                logger.info(f"[action_node] fallback_action {fallback_action_name} 执行结果: {fallback_result}")
                action_name = fallback_action_name
        
        for resp in result.responses:
            final_responses.append(resp)
            # 添加机器人消息到tracker
            bot_message = BotMessage(
                text = resp.get('text',''),
                data = resp
                )
            tracker.add_bot_message(bot_message)
        
        # 更新tracker的最新动作名
        tracker.latest_action_name = action_name
        logger.info(f"[action_node] 动作执行完成，共产生{len(result.responses)}条响应")

        # 检查是否需要等待用户输入（收集槽位的情况）
        # 当 FlowPolicy 返回 slot_to_collect 时，执行完 utter 动作后应该停止
        # 但如果是 flow_completed，需要继续循环以触发 action_flow_completed
        prediction_metadata = current_prediction.metadata or {}
        flow_completed = prediction_metadata.get('flow_completed',False)
        wait_for_input = "slot_to_collect" in prediction_metadata or not flow_completed

        if wait_for_input:
            logger.info(f"[action_node] 检测到 slot_to_collect={prediction_metadata.get('slot_to_collect',[])}，需要等待用户输入")
        
        return {
            "tracker":tracker,
            "current_action_result":result,
            "final_responses":final_responses,
            "action_count":action_count + 1,
            "is_finished":wait_for_input,
            "node_history":state.get("node_history",[]) + ["action"],
        }
    except Exception as e:
        logger.error(f"[action_node] 动作执行失败: {e}")
        return {
            "current_acion_result":ActionResult(success=False),
            "action_count":action_count + 1,
            "error":str(e),
            "node_history":state.get("node_history",[]) + ["action"],
        }

# 导出
__all__ = ["action_node"]


    
    


