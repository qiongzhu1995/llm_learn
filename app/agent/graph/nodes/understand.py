"""
理解节点

负责调用 LLMCommandGenerator 生成命令，并调用 CommandProcessor 处理命令。
这是消息处理流程的第一个核心节点。
"""
from __future__ import annotations

import re
from typing import Any,Optional,TYPE_CHECKING

from app.dialogue_understanding.commands.slot_commands import SetSlotCommand
from app.shared.logger import logger
from app.core.tracker import UserMessage
if TYPE_CHECKING:
    from app.dialogue_understanding.commands.base import Command
    from app.agent.graph.state import MessageProcessingState

def parse_set_slots_payload(payload:str) -> list['Command']:
    """解析 /SetSlots(slot=value) 格式的 payload。
    
    支持按钮点击时直接解析槽位设置，绕过 LLM 处理。
    
    支持的格式：
    - /SetSlots(order_id=123)
    - /SetSlots(order_id="订单123")
    - /SetSlots(slot1=value1, slot2=value2)
    
    Args:
        payload: 以 /SetSlots( 开头的字符串
        
    Returns:
        SetSlotCommand 列表
    """

    commands = list['Command'] = []

    # 提取括号内的内容
    match = re.match(r'/SetSlots\((.+)\)$', payload.strip())
    if not match:
        logger.warning(f"[parse_set_slots_payload] 无法解析无效的 SetSlots 格式: {payload}")
        return commands
    
    content = match.group(1)
    # 解析 key=value 对
    # 支持格式: slot=value, slot="value with spaces", slot='value'
    pattern = r'(\w+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^,\s]+))'
    # finditer() 返回一个迭代器，包含所有匹配的组
    for m in re.finditer(pattern, content):
        slot_name = m.group(1)
        # 取第一个非空值(带引号或不带引号)
        slot_value = m.group(2) or m.group(3) or m.group(4)

        # 上述转换数字
        if slot_value.isdigit():
            slot_value = int(slot_value)
        elif slot_value.lower() == 'true':
            slot_value = True
        elif slot_value.lower() == 'false':
            slot_value = False
        
        commands.append(SetSlotCommand(slot_name=slot_name, slot_value=slot_value))
        logger.info(f"[parse_set_slots_payload] 解析 SetSlots 命令: {slot_name}={slot_value}")
    
    return commands

async def understand_node(state:"MessageProcessingState") -> dict[str, Any]:
    """理解节点：生成命令并处理。
    
    该节点执行以下步骤：
    1. 检测 /SetSlots payload（按钮点击），直接解析绕过 LLM
    2. 将用户输入封装为 UserMessage 并更新 tracker
    3. 调用 LLMCommandGenerator 生成命令
    4. 调用 CommandProcessor 处理命令
    
    Args:
        state: 当前图状态
        
    Returns:
        状态更新字典
    """
    tracker = state['tracker']
    input_message = state['input_message']
    metadata = state['metadata']
    domain = state['domain']
    flows = state['flows']

    command_generator = state['_command_generator']
    command_processor = state['_command_processor']

    logger.info(f"[understand_node] 开始处理消息：｛input_message[:50]｝...")

    # 1. 检测 /SetSlots payload（按钮点击），直接解析绕过 LLM
    if input_message.strip().startswith('/SetSlots'):
        logger.info(f"[understand_node] 检测到 /SetSlots payload，直接解析绕过 LLM")
        commands = parse_set_slots_payload(input_message)
        # 执行命令
        if commands and command_processor:
            user_message = UserMessage(
                text=input_message,
                sender_id = tracker.sender_id,
                metadata = metadata,
            )
        tracker.update_with_message(user_message)

        # 直接处理解析的命令
        process_result = command_processor.process(commands,tracker)
        logger.info(f"[understand_node] 解析了 {len(commands)} 个命令，处理结果: {process_result.commands_executed} 个命令执行成功")

        return {
            "tracker": tracker,
            "current_commands":None,
            "process_result":process_result,
            "node_history":state.get("node_history",[]) + ["understand"],
        }
    
    # 2. 创建用户消息 并更新tracker
    user_message = UserMessage(
        text=input_message,
        sender_id = tracker.sender_id,
        metadata = metadata
    )
    tracker.update_with_message(user_message)

    # 初始化结果
    current_commands = None
    process_result = None
    events = []

    try:
        # 3. 使用command_generator生成命令
        if command_generator:
            flows_list = flows.flows if  flows else []
            generation_result = await command_generator.generate(
                tracker = tracker,
                domain = domain,
                flows = flows_list)
            current_commands = generation_result
            logger.warning(f"[understand_node] 使用command_generator生成命令: {current_commands}"
                           f"产生了{len(events)}个事件"
                           f"下一个动作：{process_result.next_action}")
    
        else:
            logger.warning(f"[understand_node] 没有command_generator，跳过命令生成")
        
    except Exception as e:
        logger.error(f"[understand_node] 命令生成失败: {e}")
        return {
            "tracker": tracker,
            "current_commands":None,
            "error":str(e),
            "node_history":state.get("node_history",[]) + ["understand"],
        }
    return {
        "tracker": tracker,
        "current_commands":current_commands,
        "process_result":process_result,
        "node_history":state.get("node_history",[]) + ["understand"],
    }

# 导出
__all__ = ["understand_node"]
        
        



