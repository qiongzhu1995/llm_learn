"""
策略基类

定义所有策略的抽象接口和通用功能。
"""
from __future__ import annotations

from dataclasses import dataclass,field
from typing import Optional,Any,TYPE_CHECKING
from abc import ABC,abstractmethod

from app.shared.config import settings

if TYPE_CHECKING:
    from app.core.domain import Domain
    from app.dialogue_understanding.flow.flow import FlowsList
    from app.core.tracker import DialogueStateTracker

from app.shared.logger import logger

@dataclass
class PolicyConfig:
    """策略配置
    Attributes:
        priority: 策略优先级，数值越大优先级越高
        max_history: 最大历史记录数，None表示不限制
    """
    priority: int = 1
    max_history: Optional[int] = None

@dataclass
class PolicyPrediction:
    """策略预测结果
    Attributes:
        action: 预测的动作
        confidence: 预测的置信度
        events: 预测的事件
        metadata: 额外的元数据
        policy_name: 产生此预测的策略名称
    """
    action: Optional[str] = None
    confidence: float = 0.0
    events:list[dict[str,Any]] = field(default_factory=list)
    metadata:dict[str,Any] = field(default_factory=dict)
    policy_name:str = ""

    @property
    def is_abstain(self) -> bool:
        """是否放弃预测"""
        return self.action is None or self.confidence < settings.actions.min_confidence
    
    @classmethod
    def abstain(cls,policy_name:str="") -> "PolicyPrediction":
        """放弃预测"""
        # 创建一个放弃预测的PolicyPrediction对象
        return cls(action=None,confidence=settings.actions.min_confidence,policy_name=policy_name)

class Policy(ABC):
    """策略基类
       策略负责根据当前对话状态预测下一步应该执行的动作。
      不同的策略实现不同的决策逻辑：
      - FlowPolicy: 基于Flow定义执行
      - EnterpriseSearchPolicy: 基于知识库检索回答
      - 其他策略：根据具体业务需求实现
      Attributes:
        config: 策略配置
    """
    def __init__(self, config:Optional[PolicyConfig] = None,**kwargs:Any):
        self.config = config or PolicyConfig()
        # __class__.__name__ 获取类名 作为策略名称
        self._name = self.__class__.__name__ 
    
    @property
    def name(self) -> str:
        """策略名称"""
        return self._name
    @property
    def priority(self) -> int:
        """策略优先级"""
        return self.config.priority
    
    @abstractmethod
    async def predict(self, tracker:"DialogueStateTracker",domain:Optional["Domain"] = None,flows:Optional["FlowsList"] = None,**kwargs:Any) -> PolicyPrediction:
        """预测下一步应该执行的动作
        Args:
            tracker: 对话状态跟踪器
            domain: 领域对象
            flows: 流程对象
            kwargs: 额外参数
        Returns:
            PolicyPrediction: 预测结果
        """
        raise NotImplementedError("子类必须实现 predict 方法")
    
    def predict_sync(self, tracker:"DialogueStateTracker",domain:Optional["Domain"] = None,flows:Optional["FlowsList"] = None,**kwargs:Any) -> PolicyPrediction:
        """同步版本的预测方法
        Args:
            tracker: 对话状态跟踪器
            domain: 领域对象
            flows: 流程对象
            kwargs: 额外参数
        Returns:
            PolicyPrediction: 预测结果
        """
        # 设计说明（同步封装异步）：
        # 1) 优先复用当前线程已有事件循环，避免重复创建 loop。
        # 2) 若当前线程没有可用 loop（如普通同步上下文），则创建并绑定一个新的 loop。
        # 3) 最终通过 run_until_complete 驱动 async predict 执行，向调用方返回同步结果。
        import asyncio
        try:
            logger.debug(f"同步版本的预测方法 获取当前事件循环")
            # 获取当前事件循环 并运行预测方法
            loop = asyncio.get_event_loop()
        except Exception as e:
            logger.error(f"同步版本的预测方法失败: {e}")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(self.predict(tracker,domain,flows,**kwargs))
    
    def should_predict(self, tracker:"DialogueStateTracker",domain:Optional["Domain"] = None,flows:Optional["FlowsList"] = None,**kwargs:Any) -> bool:
        """判断是否需要预测 子类可以覆盖此方法以实现条件性预测
        Args:
            tracker: 对话状态跟踪器
            domain: 领域对象
            flows: 流程对象
            kwargs: 额外参数
        Returns:
            bool: True表示需要预测,False表示不需要预测
        """
        return True
    
    def does_support_stack_frame(self,frame:Optional[Any] = None) -> bool:
        """检查策略是否支持处理当前栈帧。
        
        子类可以覆盖此方法以声明支持特定类型的栈帧。
        PolicyEnsemble可以使用此方法路由请求到合适的策略。
        
        Args:
            frame: 要检查的栈帧，如果为None则检查是否支持任何栈帧
            
        Returns:
            是否支持处理该栈帧
        """
        return True
    
    def train(self,training_data:Any,domain:Optional["Domain"] = None,**kwargs:Any) -> None:
        """训练策略"""
        pass

    def persist(self,path:Optional[str] = None) -> None:
        """持久化策略
        Args:
            path: 持久化路径
        """
        pass

    def load(self,path:str = None) -> None:
        """从文件加载策略"""
        pass

__all__ = ["PolicyConfig","PolicyPrediction","Policy"]
        




 