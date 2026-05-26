"""
base_client - LLM客户端基类

定义LLM客户端的抽象接口，所有具体客户端实现都继承此基类。
"""

from __future__ import annotations
from dataclasses import dataclass,field
from typing import Optional,Any
from abc import ABC,abstractmethod

@dataclass
class LLMResponse:
    """LLM响应数据类
    
    封装LLM API的响应结果。
    """
    content:str = ""  # 生成的文本内容
    model:str = "" # 使用的模型名称
    usage:dict[str,Any] = field(default_factory=dict) # token使用统计
    latency:float = 0.0 # 响应时间
    raw_response:Optional[Any] = None # 原始API响应(用于调试)
    metadata:dict[str,Any] = field(default_factory=dict) # 响应元数据

    @property
    def prompt_tokens(self) -> int:
        """获取提示词token数量"""
        return self.usage.get("prompt_tokens",0)
    
    @property
    def completion_tokens(self) -> int:
        """获取完成token数量"""
        return self.usage.get("completion_tokens",0)
    
    @property
    def total_tokens(self) -> int:
        """获取总token数量"""
        return self.usage.get("total_tokens",0)
    
    @property
    def thinking_content(self) -> str:
        """获取思考内容"""
        return self.metadata.get("thinking_content")

class LLMClient:
    """LLM客户端基类
    
    定义LLM客户端的抽象接口，所有具体客户端实现都继承此基类。
    """
    def __init__(self, 
                 model:str,  # 模型名称
                 api_key:str, # API密钥
                 api_base:Optional[str] = None, # API基础URL
                 temperature:float = 0.0, # 温度
                 max_tokens:int = 1024, # 最大token数
                 timeout:int = 30, # 超时时间
                 **kwargs:Any, # 额外参数
                 ):
        """初始化LLM客户端"""
        self.model = model # 模型名称
        self.api_key = api_key # API密钥
        self.api_base = api_base # API基础URL
        self.temperature = temperature # 温度
        self.max_tokens = max_tokens # 最大token数
        self.timeout = timeout # 超时时间
        self.extra_config = kwargs # 额外参数
        
    @abstractmethod
    async def complete(self, messages:list[dict[str,Any]],**kwargs:Any) -> LLMResponse:
        """异步生成文本补全,发送消息列表给LLM并获取响应
        
        Args:
            messages: 消息列表,格式为[{"role":"user","content":"用户消息"}]
            kwargs: 额外参数
        Returns:
            LLMResponse: LLM响应
        """
        pass

    @abstractmethod
    def complete_sync(self, messages:list[dict[str,Any]],**kwargs:Any) -> LLMResponse:
        """同步生成文本补全  同步版本的complete方法，用于非异步上下文 """
        pass

    def validate(self) -> bool:
        """验证客户端配置 检查API密钥等配置是否有效"""
        return bool(self.api_key and self.api_base)
    
    def __repr__(self) -> str:
        """返回客户端的字符串表示"""
        return f"{self.__class__.__name__}(model={self.model}, api_key={self.api_key}, api_base={self.api_base})"
    


