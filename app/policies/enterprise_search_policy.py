"""
企业搜索策略

基于知识库检索的策略，实现RAG功能和降级机制。
"""
from __future__ import annotations
from dataclasses import dataclass,field
from typing import Optional,Any,TYPE_CHECKING

from app.policies.base_policy import PolicyConfig,PolicyPrediction,Policy
from app.shared.logger import logger
from app.shared.llm.base_client import LLMClient
from app.shared.llm import create_llm_client
from app.shared.config import settings
from app.shared.load_prompt import load_prompt
from app.retrieval.base_retriever import SearchResult

if TYPE_CHECKING:
    from app.core.domain import Domain
    from app.core.tracker import DialogueStateTracker
    from app.dialogue_understanding.flow.flow import FlowsList

@dataclass
class _InternalRetrievalConfig:
    """内部检索(向量数据库检索)配置"""
    enabled:bool = True # 是否启用内部检索
    top_k:int = 3 # 检索结果数量
    similarity_threshold:float = 0.5 # 相似度阈值

@dataclass
class EnterpriseSearchPolicyConfig(PolicyConfig):
    """企业搜索策略配置"""
    priority:int = 50 # 策略优先级
    retrieval:_InternalRetrievalConfig = field(default_factory=_InternalRetrievalConfig)
    llm_type:str = "openai" # 大模型类型
    llm_model:str = "gpt-4o-mini" # 大模型名称
    llm_temperature:float = 0.5 # 大模型温度
    enable_citations:bool = True # 是否启用引用
    enable_relevancy_check:bool = True # 是否启用相关性检查
    chitchat_enabled:bool = True # 是否启用闲聊降级


class EnterpriseSearchPolicy(Policy):
    """企业搜索策略。
    
    基于知识库检索实现RAG功能，并包含内置的降级机制。
    
    降级链：
    1. Flow匹配 → 执行Flow
    2. 知识库检索 → 生成RAG回答
    3. 闲聊识别 → 生成闲聊回复
    4. 无法处理 → 返回默认回复
    
    工作流程：
    1. 检索相关文档
    2. 检查相关性
    3. 使用LLM生成回答
    4. 如果无相关答案，降级到闲聊或默认回复
    """
    DEFAULT_PRIORITY = 50
    RAG_PROMPT_FILE = settings.prompts.rag_prompt_file
    CHITCHAT_PROMPT_FILE = settings.prompts.chitchat_prompt_file
    def __init__(self, 
                 config:Optional[EnterpriseSearchPolicyConfig] = None,
                 llm_client:Optional[LLMClient] = None,
                 retriever:Optional[Any] = None,
                 **kwargs:Any):
        """
        初始化企业搜索策略
        Args:
            config: 策略配置
            llm_client: 大模型客户端
            retriever: 检索器
            kwargs: 额外参数
        """
        super().__init__(config or EnterpriseSearchPolicyConfig(),**kwargs)
        self.config:EnterpriseSearchPolicyConfig = self.config
        self._llm_client = llm_client
        self._retriever = retriever # 检索器
    
    @property
    def llm_client(self) -> LLMClient:
        """获取大模型客户端 延迟初始化"""
        if self._llm_client is None:
            self._llm_client = create_llm_client(
                type=self.config.llm_type,
                model=self.config.llm_model,
                temperature=self.config.llm_temperature,
            )
        return self._llm_client
    
    def _does_support_stack_frame(self,frame:Optional[Any]) -> bool:
        """检查策略是否支持处理指定栈帧。
        
        支持：SearchStackFrame、ChitChatStackFrame、CannotHandleStackFrame、
              CompleteStackFrame  、HumanHandoffStackFrame
        
        Args:
            frame: 要检查的栈帧
            
        Returns:
            是否支持处理该栈帧
        """
        from app.dialogue_understanding.stack.stack_frame import (
            SearchStackFrame,
            ChitChatStackFrame,
            CannotHandleStackFrame,
            CompleteStackFrame,
            HumanHandoffStackFrame
            )
        return isinstance(frame, (SearchStackFrame, ChitChatStackFrame, CannotHandleStackFrame, CompleteStackFrame, HumanHandoffStackFrame))
    
    async def predict(self, tracker:DialogueStateTracker, domain:Domain, flows:FlowsList,**kwargs:Any) -> PolicyPrediction:
        """预测下一步动作。
        
        检测栈帧类型并分发处理：
        - SearchStackFrame → 执行检索
        - ChitChatStackFrame → 生成闲聊回复
        - CannotHandleStackFrame → 返回降级响应
        - CompletedStackFrame → 询问是否还有其他需求
        - HumanHandoffStackFrame → 执行人工转接
        
        Args:
            tracker: 对话状态追踪器
            domain: Domain定义
            flows: Flow列表
            **kwargs: 额外参数
            
        Returns:
            预测结果
        """
        from app.dialogue_understanding.stack.stack_frame import (
            SearchStackFrame,
            ChitChatStackFrame,
            CannotHandleStackFrame,
            CompleteStackFrame,
            HumanHandoffStackFrame
            )

        # 获取栈顶帧
        top_frame = tracker.dialogue_stack.top_flow_frame()

        # 检查是否有bot响应 如果执行了该动作，则放弃
        from app.dialogue_understanding.stack.stack_frame import CompleteStackFrame as CompleteFrame,HumanHandoffStackFrame as HandoffFrame
        # 如果栈顶帧是CompleteFrame或HandoffFrame，则需要立即处理
        needs_immediate_handling = isinstance(top_frame, (CompleteFrame, HandoffFrame))
        
        if tracker.latest_action_name and tracker.latest_action_name != 'action_listen' and not needs_immediate_handling:
            logger.info(f"action {tracker.latest_action_name}已执行")
            return PolicyPrediction.abstain(self.name)
    
        # 从last_message获取用户消息 
        user_message = ""
        if tracker.latest_message:
            user_message = tracker.latest_message.text
        
        # 根据栈帧类型分发处理 从高优先级一次到低优先级处理
        if isinstance(top_frame, CompleteStackFrame):
            return await self._handle_complete_frame(tracker, top_frame, domain)
        
        if isinstance(top_frame, HumanHandoffStackFrame):
            return await self._handle_handoff_frame(tracker, top_frame, domain)
        
        if isinstance(top_frame, ChitChatStackFrame):
            return await self._handle_chitchat_frame(tracker, user_message)

        if isinstance(top_frame, CannotHandleStackFrame):
            return await self._handle_cannot_handle_frame(tracker, top_frame, domain)
        
        if isinstance(top_frame, SearchStackFrame):
            return await self._handle_search_frame(tracker, user_message)
        
        # 如果栈帧类型不支持，则放弃
        return PolicyPrediction.abstain(self.name)
    
    async def _handle_search_frame(self, tracker:"DialogueStateTracker", user_message:str) -> PolicyPrediction:
        """处理搜索栈帧。
        
        执行知识库检索，生成RAG回答。
        
        Args:
            tracker: 对话状态追踪器
            user_message: 用户消息
        """
        if not user_message:
            logger.warning("处理搜索栈帧时，用户消息为空,放弃处理")
            return PolicyPrediction.abstain(self.name)
        
        logger.info(f"开始处理搜索栈帧: {user_message} ...")

        try:
            # 从知识库里检索
            if self.config.retrieval.enabled and self._retriever:
                search_results = await self._search(user_message,tracker)

                if search_results:
                    logger.info(f"[EnterpriseSearchPolicy]知识库检索成功,检索结果数量: {len(search_results)}")
                    # 根据RAG生成的回答，使用LLM生成回答
                    answer = await self._generate_rag_answer(user_message,search_results)
                    logger.info(f"[EnterpriseSearchPolicy]RAG回答生成完成: {answer[:200] if answer else 'None'}")

                    if answer and "[NO_RAG_ANSWER]" not in answer:
                        # 检索成功，弹出栈帧
                        tracker.dialogue_stack.pop()
                        # 记录Pattern 执行历史
                        tracker.record_pattern("search")
                        logger.debug(f"检索栈帧处理完成,弹出栈帧: {tracker.dialogue_stack.top_flow_frame().frame_id}")

                        return PolicyPrediction(
                            action="action_send_text",
                            confidence=0.9,
                            policy_name=self.name,
                            metadata={
                                "text": answer,
                                "degradation_reason": settings.degradation.DEFAULT,
                                "answer_result": [answer.content for answer in search_results],
                            }
                        )

            # 降级到闲聊
            if self.config.chitchat_enabled:
                chitchat_answer = await self._generate_chitchat_answer(user_message)
                if chitchat_answer:
                    tracker.dialogue_stack.pop()
                    # 记录 Pattern 执行历史
                    tracker.record_pattern("search")
                    logger.debug(f"[EnterpriseSearchPolicy]检索栈帧弹出，降级到闲聊: {user_message} ...")
                    return PolicyPrediction(
                        action="action_send_text",
                        confidence=0.7,
                        policy_name=self.name,
                        metadata={
                            "text": chitchat_answer,
                            "degradation_reason": settings.degradation.CHITCHAT,
                        }
                    )
            # 降级到无法处理
            tracker.dialogue_stack.pop()
            # 记录 Pattern 执行历史
            tracker.record_pattern("search")
            logger.debug(f"[EnterpriseSearchPolicy]检索栈帧弹出，降级到无法处理: {user_message} ...")
            return PolicyPrediction(
                action="action_send_text",
                confidence=0.5,
                policy_name=self.name,
                metadata={"degradation_reason": settings.degradation.CANNOT_HANDLE}
            )

        except Exception as e:
            logger.error(f"[EnterpriseSearchPolicy]处理搜索栈帧时发生错误: {e}")
            try:
                # 弹出栈帧 防止栈帧堆积 如果失败，则忽略
                tracker.dialogue_stack.pop()
            except Exception as e:
                logger.error(f"[EnterpriseSearchPolicy]处理搜索栈帧时，弹出栈帧失败: {e}")
                pass
            return PolicyPrediction(
                action=settings.actions.default_fallback,
                confidence=0.3,
                policy_name=self.name,
                metadata={"degradation_reason": settings.degradation.INTERNAL_ERROR,"error_message": str(e)}
            )

    async def _handle_chitchat_frame(self, tracker:"DialogueStateTracker", user_message:str) -> PolicyPrediction:
        """处理闲聊栈帧。
        
        生成闲聊回复。
        
        Args:
            tracker: 对话状态追踪器
            user_message: 用户消息
        """
        logger.info(f"开始处理闲聊栈帧: {user_message} ...")
        # 弹出栈帧
        tracker.dialogue_stack.pop()
        # 记录 Pattern 执行历史
        tracker.record_pattern("chitchat")

        if not user_message:
            logger.info("处理闲聊栈帧时，用户消息为空,使用默认初始化响应")
            return PolicyPrediction(
                action="action_send_text",
                confidence=0.8,
                policy_name=self.name,
                metadata=settings.prompts.default_init_response
            )
        
        try:
            chitchat_answer = await self._generate_chitchat_answer(user_message)
            if chitchat_answer:
                return PolicyPrediction(
                    action="action_send_text",
                    confidence=0.9,
                    policy_name=self.name,
                    metadata={
                        "text": chitchat_answer,
                        "degradation_reason": settings.degradation.CHITCHAT,
                    }
                )
            logger.info(f"[EnterpriseSearchPolicy]闲聊栈帧处理完成: {chitchat_answer} ...")
        except Exception as e:
            logger.error(f"[EnterpriseSearchPolicy]处理闲聊栈帧时发生错误: {e}")


        return PolicyPrediction(
            action="action_send_text",
            confidence=0.7,
            policy_name=self.name,
            metadata={"text": settings.prompts.chitchat_init_response}
        )
    
    async def _handle_handoff_frame(self, tracker:"DialogueStateTracker", frame:Any,domain:Optional[Domain]) -> PolicyPrediction:
        """ 处理人工转接栈帧。"""
        reason = getattr(frame,"reason","") # 获取人工转接原因
        logger.info(f"开始处理人工转接栈帧: {reason} ...")

        # 弹出栈帧
        tracker.dialogue_stack.pop()
        # 记录 Pattern 执行历史
        tracker.record_pattern("human_handoff")

        # 从domain中获取获取转接响应
        handoff_text = settings.prompts.handoff_text
        if domain:
            response = domain.get_response("utter_human_handoff")
            if response:
                import random
                handoff_text = random.choice(response).text
        
        logger.info(f"[EnterpriseSearchPolicy]人工转接栈帧处理完成: {handoff_text} ...")
        return PolicyPrediction(
            action="action_send_text",
            confidence=0.95,
            policy_name=self.name,
            metadata={
                "text": handoff_text,
                "human_handoff": True,
                "reason": reason,
            }
        )
    
    async def _handle_cannot_handle_frame(self, tracker:"DialogueStateTracker", frame:Any,domain:Optional[Domain]) -> PolicyPrediction:
        """ 处理无法处理栈帧,返回降级响应"""
        logger.info(f"开始处理无法处理栈帧: {frame} ,原因：{getattr(frame,"reason","")}")

        # 弹出栈帧
        tracker.dialogue_stack.pop()
        # 记录 Pattern 执行历史
        tracker.record_pattern("cannot_handle")

        # 获取默认回复
        fallback_text = settings.prompts.default_fallback_response
        if domain:
            response = domain.get_response("utter_default")
            if response:
                import random
                fallback_text = random.choice(response).text
        
        logger.info(f"[EnterpriseSearchPolicy]无法处理栈帧处理完成: {fallback_text} ...")
        return PolicyPrediction(
            action="action_send_text",
            confidence=0.5,
            policy_name=self.name,
            metadata={
                "text": fallback_text,
                "degradation_reason": settings.degradation.CANNOT_HANDLE,
            }
        )
    
    async def _handle_complete_frame(self, tracker:"DialogueStateTracker", frame:Any,domain:Optional[Domain]) -> PolicyPrediction:
        """ 处理完成栈帧,询问是否还有其他请求"""
        previous_flow = getattr(frame,"previous_flow","")
        logger.info(f"开始处理完成栈帧: {previous_flow} ,之前执行的Flow: {previous_flow.name if previous_flow else 'None'}")

        # 弹出栈帧
        tracker.dialogue_stack.pop()
        # 记录 Pattern 执行历史
        tracker.record_pattern("complete")

        # 获取默认回复
        fallback_text = settings.prompts.default_complete_response
        if domain:
            response = domain.get_response("utter_can_do_something_else")
            if response:
                import random
                fallback_text = random.choice(response).text
            
        logger.info(f"[EnterpriseSearchPolicy]完成栈帧处理完成: {fallback_text} ...")
        return PolicyPrediction(
            action="action_send_text",
            confidence=0.9,
            policy_name=self.name,
            metadata={
                "text": fallback_text,
                "previos_flow": previous_flow,
            }
        )
    
    async def _search(self, user_message:str, tracker:"DialogueStateTracker") -> list[SearchResult]:
        """ 执行知识库检索。"""
        if not self._retriever:
            logger.warning("没有配置检索器,无法执行知识库检索")
            return []
        
        try:
            logger.info(f"[EnterpriseSearchPolicy]开始调用检索器{type(self._retriever).__name__}执行知识库检索...")
            logger.info(f"[EnterpriseSearchPolicy] 查询语句: {user_message} ...,top_k: {self.config.retrieval.top_k}")

            # 构建 tracker_state 用于检索器获取用户信息和历史对话
            tracker_state = tracker.to_dict() if tracker else None

            # 调用检索器
            results = await self._retriever.search(user_message,top_k=self.config.retrieval.top_k,tracker_state=tracker_state)

            logger.info(f"[EnterpriseSearchPolicy]知识库检索完成,检索结果数量: {len(results)}")

            # 过滤低相似度结果
            threshold = self.config.retrieval.similarity_threshold
            filtered_results = [result for result in results if result.score >= threshold]
            logger.info(f"[EnterpriseSearchPolicy]过滤低相似度结果后,检索结果数量: {len(filtered_results)},阈值: {threshold}")

            return filtered_results
        except Exception as e:
            logger.error(f"[EnterpriseSearchPolicy]执行知识库检索时发生错误: {e}")
            return []
    
    async def _generate_rag_answer(self, question:str, search_results:list[SearchResult]) -> str:
        """ 生成RAG回答。"""
        if not search_results:
            logger.warning("没有检索到结果,无法生成RAG回答")
            return ""
        
        try:
            logger.info(f"[EnterpriseSearchPolicy]开始生成RAG回答...")
            # 构建上下文
            context_parts = []
            for i,result in enumerate(search_results,1):
                source = result.source
                content = result.content
                # 编号. 来源\n内容
                context_parts.append(f"{i}. {source}\n{content}\n")

            context = "\n\n".join(context_parts)
            logger.info(f"[EnterpriseSearchPolicy]构建上下文完成,上下文: {context}")

            # 构建RAG提示词
            rag_prompt = load_prompt(self.RAG_PROMPT_FILE, context=context, question=question)

            # 调用LLM生成回答
            response = await self.llm_client.complete([
                {
                    "role": "user",
                    "content": rag_prompt,
                }
            ])
            logger.info(f"[EnterpriseSearchPolicy]LLM生成回答完成: {response.content[:200] if response.content else 'None'}")
            return response.content

        except Exception as e:
            logger.error(f"[EnterpriseSearchPolicy]生成RAG回答时发生错误: {e}")
            return None
    
    async def _generate_chitchat_answer(self, message:str) -> Optional[str]:
        """ 生成闲聊回答。"""
        prompt = load_prompt(self.CHITCHAT_PROMPT_FILE, message=message)

        logger.info(f"[EnterpriseSearchPolicy]开始生成闲聊回答: {message} ...")
        try:
            response = await self.llm_client.complete([
                {
                    "role": "user",
                    "content": prompt,
                }
            ])
            logger.info(f"[EnterpriseSearchPolicy]LLM生成闲聊回答完成: {response.content[:200] if response.content else 'None'}")
            return response.content
        except Exception as e:
            logger.error(f"[EnterpriseSearchPolicy]生成闲聊回答时发生错误: {e}")
            return None

__all__ = ["EnterpriseSearchPolicy","EnterpriseSearchPolicyConfig","SearchResult"]



        


        

