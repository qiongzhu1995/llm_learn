"""
消息处理器

负责处理用户消息的完整流程。
"""

from __future__ import annotations

from dataclasses import dataclass,field
from typing import Any,Optional,TYPE_CHECKING

from app.policies import PolicyEnsemble
from app.dialogue_understanding.generator import LLMCommandGenerator
from app.policies import FlowPolicy,EnterpriseSearchPolicy
from app.dialogue_understanding.processor import CommandProcessor
from app.core.tracker import DialogueStateTracker,UserMessage,BotMessage
from app.agent.actions import ActionResult, get_action
from app.shared.logger import logger
from app.shared.config import settings

if TYPE_CHECKING:
    from app.core.domain import Domain
    from app.dialogue_understanding.flow import FlowsList

@dataclass
class ProcessorConfig:
    """消息处理器配置"""
    max_actions_per_turn: int = 10 # 每个回合最大执行动作数
    enable_command_generation: bool = True # 是否启用命令生效

@dataclass 
class MessageResponse:
    """消息响应"""
    messages:list[dict[str,Any]] = field(default_factory=list) # 机器人响应的消息列表
    events:list[dict[str,Any]] = field(default_factory=list) # 机器人产生的事件列表
    metadata:dict[str,Any] = field(default_factory=dict) # 消息处理器的元数据

    def add_message(self,text:str,**kwargs) -> None:
        """添加回复消息"""
        message = {'text':text}
        message.update(kwargs)
        self.messages.append(message)

class MessageProcessor:
    """消息处理器。
    
    负责处理用户消息的完整流程：
    1. 接收用户消息
    2. 使用命令生成器生成命令
    3. 使用命令处理器处理命令
    4. 使用策略确定下一步动作
    5. 执行动作并返回响应
    """
    def __init__(self,
                 domain:Optional["Domain"] = None,
                 flows:Optional["FlowsList"] = None,
                 police_ensemble:Optional[PolicyEnsemble] = None,
                 command_generator:Optional[LLMCommandGenerator] = None,
                 config:Optional[ProcessorConfig] = None,
                 ) -> None:
        self.domain = domain 
        self.flows = flows 
        self.config = config or ProcessorConfig()

        # 初始化PolicyEnsemble
        if police_ensemble :
            self.police_ensemble = police_ensemble
        else:
            self.police_ensemble = PolicyEnsemble(policies=[
                FlowPolicy(flows=self.flows),
                EnterpriseSearchPolicy(),
            ])
        
        # 初始化命令集成器
        self.command_generator = command_generator
        
        # 初始化命令生成器
        self.command_generator = command_generator

        # 初始化消息处理器
        self.command_processor = CommandProcessor(
            domain=self.domain,
            flows=self.flows.flows if self.flows else []
        )

    async def process_message(self,
                              message:str,
                              tracker:DialogueStateTracker,
                              metadata:Optional[dict[str,Any]] = None,
                              ) -> MessageResponse:
                """处理用户消息"""
                response = MessageResponse()

                # 1. 创建用户消息并添加到Tracker
                user_message = UserMessage(
                    text=message,
                    sender_id=tracker.sender_id,
                    metadata=metadata or {},
                )
                tracker.update_with_message(user_message)
                logger.info(f"用户消息添加到Tracker: {user_message}")

                # 2. 使用命令生成器生成命令
                try:
                    if self.config.enable_command_generation and self.command_generator:
                        generation_result = await self.command_generator.generate(
                            tracker=tracker,domain=self.domain,flows=self.flows.flows if self.flows else []
                        )
                        logger.info(f"命令生成结果: {generation_result}")
                        if generation_result.commands:
                            # 3. 使用命令处理器处理命令
                            processor_result = await self.command_processor.process(
                                commands=generation_result.commands,
                                tracker=tracker,
                            )
                            response.events.extend(processor_result.events)
                            logger.info(f"命令处理器处理结果: {processor_result}")
                            response.metadata['commands'] = [cmd.as_dict() for cmd in generation_result.commands]
                    
                    # 4. 使用策略确定下一步动作
                    prediction = await self.police_ensemble.predict(
                        tracker=tracker,
                        domain=self.domain,
                        flows=self.flows
                    )
                    logger.info(f"策略确定下一步动作: {prediction}")
                    response.metadata['policy'] = prediction.policy_name
                    response.metadata['action'] = prediction.action
                    response.metadata['confidence'] = prediction.confidence

                    # 5. 进行动作循环
                    action_count = 0
                    current_action = prediction.action

                    while current_action and current_action != settings.actions.listen:
                        if action_count >= self.config.max_actions_per_turn:
                            logger.warning(f"每个回合最多执行{self.config.max_actions_per_turn}个动作，达到上限")
                            break

                        # 执行动作
                        action_result = await self._execute_action(current_action,tracker,metadata)

                        # 收集响应
                        for resp in action_result.responses:
                            response.messages.append(resp)
                            # 添加机器人消息到Tracker
                            bot_message = BotMessage(
                                text=resp.get('text',''),
                                data = resp
                            )
                            tracker.add_bot_message(bot_message)
                            logger.info(f"机器人消息添加到Tracker: {bot_message}")
                        response.events.extend(action_result.events)
                        action_count += 1

                        # 获取下一个动作
                        prediction = await self.police_ensemble.predict(
                            tracker=tracker,
                            domain=self.domain,
                            flows=self.flows
                        )
                        logger.info(f"策略确定下一个动作: {prediction}")
                        current_action = prediction.action
                    logger.info(f"消息处理完成，共执行了{action_count}个动作")
                except Exception as e:
                    logger.error(f"消息处理失败: {e}")
                    response.add_message(f"处理消息时出错: {str(e)}")
                    response.metadata['error'] = str(e)
                
                return response

    async def _execute_action(self,
                              action_name:str,
                              tracker:DialogueStateTracker,
                              metadata:Optional[dict[str,Any]] = None,
                              ) -> ActionResult:
                """执行动作"""
                logger.info(f"执行动作: {action_name}")

                # 获取动作
                action = get_action(action_name)

                if action is None:
                    logger.warning(f"未找到动作: {action_name}")
                    return ActionResult(success=False)
                
                # 合并元数据到kwargs
                kwargs = metadata or {}

                # 如果是闲聊动作，船体LLM配置
                if action_name == "action_chitchat_response" and self.command_generator:
                    config = self.command_generator.config
                    kwargs['llm_config'] = {
                        'type':config.type,
                        'model':config.model_name,
                        'api_key':config.api_key,
                        'api_base':config.api_base,
                        'temperature':config.temperature,
                        'max_tokens':config.max_tokens,
                        'enable_thinking':config.enable_thinking,
                    }
                try:
                    result = await action.run(tracker=tracker,domain=self.domain,**kwargs)
                    tracker.latest_action_name = action_name
                    logger.info(f"动作执行结果: {result}")
                    return result
                except Exception as e:
                    logger.error(f"动作执行失败: {e}")
                    return ActionResult(success=False)

    def set_domain(self,domain:"Domain") -> None:
        """设置Domain对象"""
        self.domain = domain
        self.command_processor.set_domain(domain)
    
    def set_flows(self,flows:"FlowsList") -> None:
        """设置Flows对象"""
        self.flows = flows
        self.command_processor.set_flows(flows.flows if flows else [])

        # 更新PolicyEnsemble
        for policy in self.police_ensemble.policies:
            if isinstance(policy,FlowPolicy):
                policy.set_flows(flows)

_all__ = ["MessageProcessor","ProcessorConfig","MessageResponse"]
    
