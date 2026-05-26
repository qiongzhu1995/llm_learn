"""
langchain_client - 统一LLM客户端

通过LangChain框架集成多种LLM后端，提供统一的接口。
支持的类型：
- openai: OpenAI API / vLLM / 其他OpenAI兼容服务
- qwen: 阿里云DashScope通义千问API
- azure: Azure OpenAI
- anthropic: Anthropic Claude
"""
from __future__ import annotations

import time
from typing import Optional,Any

from app.shared.llm.base_client import LLMClient,LLMResponse
from app.shared.logger import logger
from app.shared.exceptions import LLMResponseError,LLMTimeoutError,LLMAuthenticationError,LLMRateLimitError,LLMConnectionError

class LangChainClient(LLMClient):

    # 支持的类型
    SUPPORTED_TYPES = ["openai", "qwen", "azure", "anthropic"]

    def __init__(self, 
                 type:str="openai",
                 model:str="gpt-4o-mini",
                 api_key:str = None,
                 api_base:Optional[str] = None,
                 temperature:float = 0.0,
                 max_tokens:int = 1024,
                 timeout:int = 30,
                 enable_thinking:bool = False,
                 **kwargs:Any):
            """
            初始化LangChain客户端
            Args:
                type: 客户端类型
                model: 模型名称
                api_key: API密钥
                api_base: API基础URL
                temperature: 温度
                max_tokens: 最大token数
                timeout: 超时时间
                enable_thinking: 是否启用思考
                kwargs: 额外参数
            """
            super().__init__(model, api_key, api_base, temperature, max_tokens, timeout, **kwargs)
            self.type = type
            self.enable_thinking = enable_thinking
            self._llm = None

            if self.type not in self.SUPPORTED_TYPES:
                raise ValueError(f"不支持的LLM类型: {self.type},支持的类型: {', '.join(self.SUPPORTED_TYPES)}")


    def _get_llm(self) :
        """获取langchain LLM实例"""
        if self._llm is None:
            self._llm = self._create_llm()
        return self._llm
    
    def _create_llm(self) -> Any:
        """创建langchain LLM实例"""
        if self.type == "openai":
            return self._create_openai_llm()
        elif self.type == "qwen":
            return self._create_qwen_llm()
        elif self.type == "azure":
            return self._create_azure_llm()
        elif self.type == "anthropic":
            return self._create_anthropic_llm()
        else:
            raise ValueError(f"不支持的LLM类型: {self.type}")

    def _create_openai_llm(self) -> Any:
        """创建openai LLM实例"""
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            raise ImportError("请安装langchain-openai: pip install langchain-openai")
        
        llm_kwargs = {
            "model": self.model,
            "api_key": self.api_key,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout": self.timeout,
            **self.extra_config
        }
        # 自定义api地址
        if self.api_base:
            llm_kwargs["api_base"] = self.api_base
        # vLLM thinking模式支持
        # 当使用自定义api_base且启用thinking时，通过extra_body传递配置
        # vLLM需要启动时加 --enable-reasoning --reasoning-parser qwen3
        if self.api_base and self.enable_thinking:
            llm_kwargs["model_kwargs"] = {
                "extra_body": {
                    "chat_template_kwargs": {
                        "enable_thinking": True
                    }
                }
            }
        return ChatOpenAI(**llm_kwargs)
    
    def _create_qwen_llm(self) -> Any:
        """创建qwen LLM实例"""
        try:
            from langchain_community.chat_models import ChatTongyi
        except ImportError:
            raise ImportError("请安装langchain-community: pip install langchain-community")

        llm_kwargs = {
            "model": self.model,
            "dashscope_api_key": self.api_key,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens
        }
        
        if self.enable_thinking:
            llm_kwargs["model_kwargs"] = {"enable_thinking": True}
        
        return ChatTongyi(**llm_kwargs)
    
    def _create_azure_llm(self) -> Any:
        """创建azure LLM实例"""
        try:
            from langchain_openai import AzureChatOpenAI
        except ImportError:
            raise ImportError("请安装langchain_openai: pip install langchain_openai")
        
        llm_kwargs = {
            "model": self.model,
            "api_key": self.api_key,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        # Azure 指定配置
        if "azure_endpoint" in self.extra_config:
            llm_kwargs["azure_endpoint"] = self.extra_config["azure_endpoint"]
        
        if "api_version" in self.extra_config:
            llm_kwargs["api_version"] = self.extra_config["api_version"]
        
        return AzureChatOpenAI(**llm_kwargs)

    def _create_anthropic_llm(self) -> Any:
        """创建anthropic LLM实例"""
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError:
            raise ImportError("请安装langchain-anthropic: pip install langchain-anthropic")
        
        llm_kwargs = {
            "model": self.model,
            "api_key": self.api_key,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        return ChatAnthropic(**llm_kwargs)
    
    def _convert_message(self, messages:list[dict[str,Any]]) -> list:
        """转换消息格式为LangChain格式
        
        参数：
            messages: 标准消息列表 [{"role": "user", "content": "..."}]
            
        返回：
            LangChain消息对象列表
        """
        try:
            from langchain_core.messages import HumanMessage,AIMessage,SystemMessage
        except ImportError:
            raise ImportError("请安装langchain: pip install langchain")
        
        result = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # 系统消息 
            if role == "system":
                result.append(SystemMessage(content=content))
            # 助手消息
            elif role == "assistant":
                result.append(AIMessage(content=content))
            # 用户消息
            else:
                result.append(HumanMessage(content=content))
        return result
    
    async def complete(self, messages:list[dict[str,Any]],**kwargs:Any) -> LLMResponse:
        """异步生成文本补全
        
        参数：
            messages: 消息列表 [{"role": "user", "content": "..."}]
            **kwargs: 额外API参数
            
        返回：
            LLMResponse对象
        """
        llm = self._get_llm()
        langchain_messages = self._convert_message(messages)

        start_time = time.time()
        
        try:
            logger.info(f"开始向LLM发送请求: {messages}")
            response = await llm.ainvoke(langchain_messages,**kwargs)
        except Exception as e:
            logger.error(f"向LLM发送请求失败: {e}")
            self._handle_error(e)
        
        latency = time.time() - start_time

        return self._parse_response(response,latency)
    
    def complete_sync(self, messages:list[dict[str,Any]],**kwargs:Any) -> LLMResponse:
        """同步生成文本补全
        
        参数：
            messages: 消息列表 [{"role": "user", "content": "..."}]
            **kwargs: 额外API参数
            
        返回：
            LLMResponse对象
        """
        llm = self._get_llm()
        langchain_messages = self._convert_message(messages)
        start_time = time.time()
        try:
            logger.info(f"开始向LLM发送请求: {messages}")
            response = llm.invoke(langchain_messages,**kwargs)
        except Exception as e:
            logger.error(f"向LLM发送请求失败: {e}")
            self._handle_error(e)
        
        latency = time.time() - start_time
        return self._parse_response(response,latency)
    
    def _parse_response(self, response:Any, latency:float) -> LLMResponse:
        """解析响应结果为LLMResponse对象"""
        try:
            content = response.content if hasattr(response, "content") else response

            # 提取token使用量
            usage = {}
            if hasattr(response, "response_metadata"):
                response_metadata = response.response_metadata
                if "token_usage" in response_metadata:
                    token_usage = response_metadata.get("token_usage", {})
                    usage = {
                        "prompt_tokens": token_usage.get("prompt_tokens", 0),
                        "completion_tokens": token_usage.get("completion_tokens", 0),
                        "total_tokens": token_usage.get("total_tokens", 0),
                    }
            # 提取thinking内容
            metadata = {}
            if hasattr(response, "response_metadata"):
                additional = response.additional_kwargs
                for key in ['reasoning_content', 'thinking_content','thinking']:
                    if key in additional:
                        metadata['thinking_content'] = additional[key]
                        break
            logger.info(f"向LLM发送请求成功, 响应时间: {latency}秒")
            return LLMResponse(
                content=content,
                model=self.model,
                usage=usage,
                latency=latency,
                raw_response=response,
                metadata=metadata,
            )
        except Exception as e:
            logger.error(f"解析响应结果失败: {e}")
            raise LLMResponseError(f"解析响应结果失败: {e}")
    
    def _handle_error(self, error:Exception) -> None:
        """处理API错误"""
        error_message = str(error)
        error_type = type(error).__name__

        if "timeout" in error_message.lower():
            logger.error(f"向LLM发送请求超时: {error_message}")
            raise LLMTimeoutError(f"向LLM发送请求超时: {error_message}")
        
        elif "auth" in error_message.lower() or "key" in error_message.lower():
            logger.error(f"向LLM发送请求认证失败: {error_message}")
            raise LLMAuthenticationError(f"向LLM发送请求认证失败: {error_message}")

        elif "rate" in error_message.lower():
            logger.error(f"向LLM发送请求速率限制: {error_message}")
            raise LLMRateLimitError(f"向LLM发送请求速率限制: {error_message}")
        
        else:
            logger.error(f"其他未知的失败: {error_message}")
            raise LLMConnectionError(f"其他未知的失败{error_type}: {error_message}")



    
