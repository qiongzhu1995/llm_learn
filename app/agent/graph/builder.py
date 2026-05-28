# 文件说明：图构建器。
from __future__ import annotations

from typing import TYPE_CHECKING

from langgraph.graph import StateGraph,START,END
from langgraph.graph.state import CompiledStateGraph

from app.agent.graph.nodes import understand_node,policy_node,action_node,guard_node,response_node
from app.agent.graph.edges import should_execute_edge,should_continue
from app.agent.graph.state import MessageProcessingState
from app.shared.logger import logger

def build_message_processing_graph() -> CompiledStateGraph:
    """构建消息处理图。
    
    构建一个 LangGraph StateGraph，用于编排消息处理流程：
    
    图结构:
    
        START → understand → policy → [route] → action → guard → [route] → ...
                                        ↓                           ↓
                                     response ← ← ← ← ← ← ← ← ← ← ←
                                        ↓
                                       END
    
    Returns:
        编译后的图
    """
    logger.info("[build_message_processing_graph] 开始构建消息处理图...")

    # 创建状态图
    graph = StateGraph(MessageProcessingState)

    # 添加节点
    graph.add_node("understand",understand_node)
    graph.add_node("policy",policy_node)
    graph.add_node("action",action_node)
    graph.add_node("guard",guard_node)
    graph.add_node("response",response_node)

    # 添加入口边
    graph.add_edge(START,"understand")

    # understand -> policy
    graph.add_edge("understand","policy")
    
    # policy -> 条件边 -> action/response
    graph.add_conditional_edges("policy",should_execute_edge,{"action":"action","response":"response"})

    # action -> guard
    graph.add_edge("action","guard")

    # guard -> 条件边 -> policy/response
    graph.add_conditional_edges("guard",should_continue,{"policy":"policy","response":"response"})

    # response -> END
    graph.add_edge("response","END")

    # 编译图
    compiled_graph = graph.compile()
    logger.info("[build_message_processing_graph] 消息处理图构建完成")
    return compiled_graph

# 全局图实例
_graph_instance:CompiledStateGraph | None = None

def get_message_processing_graph() -> CompiledStateGraph:
    """获取全局消息处理图实例。
    
    如果图未初始化，则构建并缓存。
    
    Returns:
        消息处理图实例
    """
    global _graph_instance
    if _graph_instance is None:
        _graph_instance = build_message_processing_graph()
    return _graph_instance

def reset_graph_instance() -> None:
    """重置全局图实例。"""
    global _graph_instance
    _graph_instance = None

# 导出
__all__ = ["get_message_processing_graph","reset_graph_instance","build_message_processing_graph"]


