"""
策略节点

负责调用 PolicyEnsemble 预测下一个动作。
"""
from __future__ import annotations

from typing import Any,Optional,TYPE_CHECKING
from app.shared.logger import logger
from app.shared.config import settings
if TYPE_CHECKING:
    from app.agent.graph.state import MessageProcessingState

async def policy_node(state:"MessageProcessingState") -> dict[str, Any]:
    """策略节点：预测下一个动作。
    
    该节点调用 PolicyEnsemble.predict() 来决定系统应该执行什么动作。
    如果 CommandProcessor 已经确定了 next_action，优先使用该动作（仅第一轮）。
    如果预测的动作是 action_listen，则标记处理完成。
    
    Args:
        state: 当前图状态
        
    Returns:
        状态更新字典
    """
    tracker = state['tracker']
    domain = state.get('domain')
    flows = state.get('flows')
    policy_ensemble = state.get('_policy_ensemble')
    process_result = state.get('process_result')
    action_count = state.get('action_count',0)

    logger.info(f"[policy_node] 开始预测下一个动作...")

    # 默认预测结果
    current_prediction = None
    is_finished = True 

    try:
        # 优先使用 CommandProcessor 确定的 next_action 
        if action_count == 0 and process_result and process_result.next_action:
            next_action = process_result.next_action
            # 跳过 action_run_flow_* 类型的动作，这些由 FlowPolicy 处理
            if not next_action.startswith('action_run_flow_'):
                current_prediction = PolicyPrediction(
                    action = next_action,
                    confidence = 1.0,
                    policy_name = 'CommandProcessor',
                    metadata = process_result.metadata,
                )
                is_finished = (next_action == settings.actions.listen)
                logger.info(f"[policy_node] 使用CommandProcessor确定的下一个动作: {next_action}"
                           f"处理完成: {is_finished}")
                return {
                    "current_prediction":current_prediction,
                    "is_finished":is_finished,
                    "node_history":state.get("node_history",[]) + ["policy"],
                }
        
        # 2. 使用PolicyEnsemble预测
        if policy_ensemble:
            prediction_result = await policy_ensemble.predict(tracker,domain,flows)
            current_prediction = prediction_result

            # 检查是否应该结束
            is_finished = (current_prediction.action == settings.actions.listen or prediction_result.action is None)

            logger.info(f"[policy_node] 使用PolicyEnsemble预测下一个动作: {current_prediction.action},"
                         f"置信度: {current_prediction.confidence},"
                         f"处理完成: {is_finished}")
            return {
                "current_prediction":current_prediction,
                "is_finished":is_finished,
                "node_history":state.get("node_history",[]) + ["policy"],
            }
        
        else:
            logger.warning(f"[policy_node] 没有PolicyEnsemble，跳过预测")
    except Exception as e:
        logger.error(f"[policy_node] 预测失败: {e}")
        return {
            "current_prediction":None,
            "is_finished":True,
            "error":str(e),
            "node_history":state.get("node_history",[]) + ["policy"],
        }
    return {
        "current_prediction":current_prediction,
        "is_finished":is_finished,
        "node_history":state.get("node_history",[]) + ["policy"]
    }
    
