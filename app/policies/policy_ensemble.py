"""
策略集成器

管理多个策略，按优先级选择最佳预测。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional,Any,TYPE_CHECKING

from app.shared.config import settings
from app.policies.base_policy import Policy,PolicyPrediction
from app.shared.logger import logger
if TYPE_CHECKING:
    from app.core.domain import Domain
    from app.dialogue_understanding.flow.flow import FlowsList
    from app.core.tracker import DialogueStateTracker
@dataclass
class EmsenmbleConfig:
    """ 策略集成配置 """
    fallback_action:str = settings.actions.listen # 所有策略都放弃时的默认动作
    min_confidence:float = 0.0 # 最小置信度

class PolicyEnsemble:
    """策略集成器。
    
    管理多个策略，按优先级顺序执行预测，选择最佳结果。
    
    策略选择逻辑：
    1. 按优先级从高到低遍历策略
    2. 选择第一个非放弃且置信度最高的预测
    3. 如果所有策略都放弃，返回默认动作
    """ 
    def __init__(self, policies:Optional[list[Policy]]=None, config:EmsenmbleConfig = None) -> None:
        """初始化策略集成器"""
        self.policies = policies or []
        self.config = config or EmsenmbleConfig()
        self._sort_policies() # 按优先级排序策略

    def _sort_policies(self) -> None:
        """按优先级排序策略"""
        self.policies.sort(key=lambda x: x.priority, reverse=True)
    
    def add_policy(self, policy:Policy) -> None:
        """添加策略"""
        self.policies.append(policy)
        self._sort_policies() # 按优先级排序策略
    
    def remove_policy(self, policy_name:str) -> None:
        """删除策略"""
        for i,policy in enumerate(self.policies):
            if policy.name == policy_name:
                return self.policies.pop(i)
        return None
    
    async def predict(self,tracker:"DialogueStateTracker",domain:Optional["Domain"] = None,flows:Optional["FlowsList"] = None,**kwargs:Any) -> PolicyPrediction:
        """使用策略集成进行预测 按照优先级顺序尝试每个顺序，返回最佳策略"""
        best_prediction:Optional[PolicyPrediction] = None
        all_predictions:list[PolicyPrediction] = []

        for policy in self.policies:
            # 检查策略是否应该预测
            if not policy.should_predict(tracker,domain,flows,**kwargs):
                logger.debug(f"策略{policy.name}跳过")
                continue

            try:
                prediction = await policy.predict(tracker,domain,flows,**kwargs)
                all_predictions.append(prediction)
                logger.debug(f"策略{policy.name}预测成功,执行action: {prediction.action},置信度: {prediction.confidence}")

                # 如果策略没有放弃预测，则更新最佳预测
                if not prediction.is_abstain:
                    # 检查置信度是否满足最小置信度
                    if prediction.confidence >= self.config.min_confidence:
                        # 选择置信度最高的
                        if best_prediction is None or prediction.confidence > best_prediction.confidence:
                            best_prediction = prediction
                            logger.debug(f"策略{policy.name}置信度最高,更新最佳预测为: {best_prediction.action},置信度: {best_prediction.confidence}")
                        
                        # 如果置信度为1.0，则直接返回
                        if prediction.confidence == 1.0:
                            logger.debug(f"策略{policy.name}置信度为1.0,直接返回")
                            break
                    
            except Exception as e:
                logger.error(f"策略{policy.name}预测失败: {e}")
                continue
        # 如果有有效预测，则返回最佳预测
        if best_prediction is not None:
            logger.info(f"策略集成器预测成功,执行action: {best_prediction.action},置信度: {best_prediction.confidence}")
            return best_prediction
        # 如果没有有效预测，则返回放弃预测
        logger.info(f"策略集成器预测失败,返回降级动作: {self.config.fallback_action}")
        
        return PolicyPrediction(
            action=self.config.fallback_action,
            confidence=settings.actions.min_confidence,
            policy_name="PolicyEnsemble",
            metadata={"fallback":True}
        )
    
    def predict_sync(self,tracker:"DialogueStateTracker",domain:Optional["Domain"] = None,flows:Optional["FlowsList"] = None,**kwargs:Any) -> PolicyPrediction:
        """使用策略集成进行同步预测 按照优先级顺序尝试每个顺序，返回最佳策略"""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self.predict(tracker,domain,flows,**kwargs))

    def get_policy(self,policy_name:str) -> Optional[Policy]:
        """根据名称获取策略"""
        for policy in self.policies:
            if policy.name == policy_name:
                return policy
        return None
    
    @property
    def policy_names(self) -> list[str]:
        """获取所有策略名称"""
        return [policy.name for policy in self.policies]
    
    def train_all(self,training_data:any,domain:Optional["Domain"] = None,**kwargs:Any) -> None:
        """训练所有策略"""
        for policy in self.policies:
            try:
                policy.train(training_data,domain,**kwargs)
                logger.info(f"策略{policy.name}训练成功")
            except Exception as e:
                logger.error(f"策略{policy.name}训练失败: {e}")
                continue
        logger.info(f"所有策略训练成功")

def create_default_policy_ensemble() -> PolicyEnsemble:
    """创建默认策略集成器"""
    from app.policies.flow_policy import FlowPolicy
    from app.policies.enterprise_search_policy import EnterpriseSearchPolicy
    return PolicyEnsemble(policies=[FlowPolicy(),EnterpriseSearchPolicy()])

__all__ = ["PolicyEnsemble","EmsenmbleConfig","create_default_policy_ensemble"]


    






    
