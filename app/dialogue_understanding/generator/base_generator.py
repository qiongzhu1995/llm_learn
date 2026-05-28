"""
命令生成器基类

定义命令生成器的抽象接口。
"""

from __future__ import annotations
from abc import ABC,abstractmethod
from dataclasses import dataclass,field
from typing import Text,Optional,Any,TYPE_CHECKING

if TYPE_CHECKING:
    from app.dialogue_understanding.commands.base import Command
    from app.core.domain import Domain
    from app.core.tracker import DialogueStateTracker
@dataclass
class GeneratorConfig:
    """命令生成器配置"""
    max_history_turns:int = 5 # 发送给LLM的最大历史轮数
    include_slots:bool = True # 是否包含槽位信息
    include_flows:bool = True # 是否包含流程信息
    temperature:float = 0.0 # 生成命令的温度


@dataclass
class GeneratorResult:
    """命令生成器结果"""
    commands:list["Command"] = field(default_factory=list) # 生成的命令列表
    raw_output:str = "" # LLM原始输出内容
    prompt:str = "" # 使用的提示词
    metadata:dict[str,Any] = field(default_factory=dict) # 额外的元数据

    @property
    def success(self) -> bool:
        """判断命令生成是否成功"""
        return len(self.commands) > 0
    
    @property
    def first_command(self) -> Optional["Command"]:
        """获取第一个命令"""
        return self.commands[0] if self.commands else None
    
class CommandGenerator(ABC):
    """命令生成器抽象基类。
    
    命令生成器负责将用户输入转换为系统可执行的命令。
    不同的实现可以使用不同的策略（LLM、规则、NLU等）。
    """
    def __init__(self,config:Optional[GeneratorConfig] = None) -> None:
        self.config = config or GeneratorConfig()


    @abstractmethod
    async def generate(self,tracker:"DialogueStateTracker",domain:Optional["Domain"] = None,flows:Optional[list[str]] = None) -> GeneratorResult:
        """生成命令
        Args:
            tracker: 对话状态跟踪器
            domain: 领域对象
            flows: 流程列表
        Returns:
            GeneratorResult: 命令生成结果
        """
        raise NotImplementedError
    
    def generate_sync(self,tracker:"DialogueStateTracker",domain:Optional["Domain"] = None,flows:Optional[list[str]] = None) -> GeneratorResult:
        """同步生成命令
        Args:
            tracker: 对话状态跟踪器
            domain: 领域对象
            flows: 流程列表
        Returns:
            GeneratorResult: 命令生成结果
        """
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(self.generate(tracker,domain,flows))

        @property
        def name(self) -> str:
            """获取命令生成器名称"""
            return self.__class__.__name__

__all__ = ["GeneratorConfig","GeneratorResult","CommandGenerator"]

            

