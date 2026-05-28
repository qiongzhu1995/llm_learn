"""
条件边路由函数

定义 LangGraph 图中的条件边路由逻辑。
"""
from __future__ import annotations

import logging
from typing import Any,Optional,TYPE_CHECKING,Literal
from shared.logger import logger
from shared.config import settings
if TYPE_CHECKING:
    from app.agent.graph.state import MessageProcessingState

# Literal["action","response"] 表示返回值只能是"action"或"response"
def should_execute_edge(state:"MessageProcessingState") -> Literal["action","response"]:
    """决定是执行动作还是返回响应。
    
    在 policy_node 之后调用，根据预测结果决定下一步：
    - 如果 is_finished 为 True，或动作为 action_listen，则跳转到 response_node
    - 否则跳转到 action_node 执行动作
    
    Args:
        state: 当前图状态 (MessageProcessingState)
        
    Returns:
        下一个节点名称
    """   
    is_finished = state.get('is_finished',False)
    current_prediction = state.get('current_prediction')

    # 检查是否已完成
    if is_finished:
        logger.info(f"[should_execute_edge] 处理已完成，跳转到 response_node")
        return "response"

    # 检查动作是否为 action_listen
    if current_prediction:
        action = current_prediction.action
        if action == settings.actions.listen or action is None:
            logger.info(f"[should_execute_edge] 动作为 action_listen，跳转到 response_node")
            return "response"
    
    else:
        logger.info(f"[should_execute_edge] 没有预测结果，跳转到 response_node")
        return "response"
    
    # 默认跳转到 action_node
    logger.info(f"[should_execute_edge] 未完成处理，跳转到 action_node")
    return "action"

def should_continue(state:"MessageProcessingState") -> Literal["policy","response"]:
    """决定是否继续循环还是接受
        在 guard_node 之后调用，根据状态决定是否继续：
    - 如果 is_finished 为 True，或达到最大动作数，则跳转到 response_node
    - 否则跳转回 policy_node 继续决策
    """
    is_finished = state.get('is_finished',False)
    action_count = state.get('action_count',0)
    max_actions = state.get('max_actions',10)
    logger.info(f"[should_continue] 检查是否继续循环，is_finished={is_finished}, action_count={action_count}, max_actions={max_actions}")

    if is_finished:
        logger.info(f"[should_continue] 处理已完成，跳转到 response_node")
        return "response"
    
    if action_count >= max_actions:
        logger.info(f"[should_continue] 达到最大动作数，{action_count}/{max_actions}，跳转到 response_node")
        return "response"
    
    logger.info(f"[should_continue] 继续循环，跳转到 policy_node")
    return "action"


# 导出
__all__ = ["should_execute_edge","should_continue"]

