"""
响应节点

负责收集最终响应并标记处理完成。
"""

from __future__ import annotations
from typing import Any,Optional,TYPE_CHECKING
from app.shared.logger import logger
if TYPE_CHECKING:
    from app.agent.graph.state import MessageProcessingState

async def response_node(state:"MessageProcessingState") -> dict[str, Any]:
    """响应节点：收集最终响应并标记处理完成。"""
    final_responses = state.get('final_responses',[])
    action_count = state.get('action_count',0)
    error = state.get('error')

    if error:
        logger.warning(f"[response_node] 处理过程中发生错误: {error}")
    
    return {
        "is_finished":True,
        "node_history":state.get("node_history",[]) + ["response"],
    }

# 导出
__all__ = ["response_node"]

