# 文件说明：保护节点。
"""
保护节点

负责检查循环次数，防止无限循环。
"""
from __future__ import annotations

from typing import Any,Optional,TYPE_CHECKING
from app.shared.logger import logger
if TYPE_CHECKING:
    from app.agent.graph.state import MessageProcessingState

async def guard_node(state:"MessageProcessingState") -> dict[str, Any]:
    """保护节点：检查循环次数，防止无限循环。如果达到则强制终止处理"""
    action_count = state.get('action_count',0)
    max_actions = state.get('max_actions',10)

    if action_count >= max_actions:
        logger.warning(f"[guard_node] 达到最大动作执行次数: {max_actions}，强制终止处理")
        return {
            "is_finished":True,
            "error":"达到最大动作执行次数: {max_actions}",
            "node_history":state.get("node_history",[]) + ["guard"],
        }
    
    logger.info(f"[guard_node] 动作执行次数: {action_count}，继续处理")

    return {
        "node_history":state.get("node_history",[]) + ["guard"],
    }

# 导出
__all__ = ["guard_node"]

