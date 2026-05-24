"""
tracker 存储基类 
定义Tracker存储的抽象接口，所有存储后端都需要实现这个接口。
"""

from abc import ABC,abstractmethod
from typing import Optional,Iterable,Text

from app.core.domain import Domain
from app.core.tracker import DialogueStateTracker
from app.shared.logger import logger


class TrackerStore(ABC):
    """Tracker存储基类"""

    def __init__(self, domain:Optional[Domain] = None) -> None:
        """初始化Tracker存储"""
        self.domain = domain
    
    @abstractmethod
    async def save(self, tracker:DialogueStateTracker) -> None:
        """保存Tracker状态
        将Tracker序列化后保存到存储后端
        Args:
            tracker: Tracker对象
        """
        pass
    
    @abstractmethod
    async def retrieve(self, session_id:Text) -> Optional[DialogueStateTracker]:
        """从存储后端检索Tracker状态
        Args:
            session_id: 会话ID
        Returns:
            DialogueStateTracker: Tracker对象,None表示不存在
        """
        pass
    
    
    async def retrieve_full_tracker(self, session_id:Text) -> Optional[DialogueStateTracker]:
        """从存储后端检索完整的Tracker状态
        获取包含所有历史会话的Tracker。
        默认实现与retrieve相同，子类可重写以支持会话分割
        Args:
            session_id: 会话ID
        Returns:
            DialogueStateTracker: Tracker对象,None表示不存在
        """
        logger.debug("retrieve_full_tracker: 获取完整的Tracker状态 session_id={}", session_id)
        return await self.retrieve(session_id)
    
    @abstractmethod
    async def delete(self, session_id:Text) -> None:
        """删除Tracker状态
        Args:
            session_id: 会话ID
        """
        logger.debug("delete: 删除Tracker状态 session_id={}", session_id)
        pass
    
    @abstractmethod
    async def keys(self) -> Iterable[Text]:
        """获取所有会话ID列表
        Returns:
            session_id的可迭代对象 
        """
        pass
    
    
    async def exists(self, session_id:Text) -> bool:
        """检查会话ID是否存在
        Args:
            session_id: 会话ID
        Returns:
            bool: True表示存在,False表示不存在
        """
        tracker = await self.retrieve(session_id)
        return tracker is not None
    
    def create_tracker(self, session_id:Text) -> DialogueStateTracker:
        """创建新的Tracker对象 使用Domain定义的槽位和动作创建新的Tracker对象
        Args:
            session_id: 会话ID
        Returns:
            DialogueStateTracker: 新的Tracker对象
        """
        slots = {}
        if self.domain:
            logger.debug("当前Domain对象有槽位定义，将使用Domain定义的槽位和动作创建新的Tracker对象")
            # 从domain辅助槽位定义
            from copy import deepcopy
            slots = {name:deepcopy(slot) for name,slot in self.domain.slots.items()}
            logger.debug("创建新的Tracker对象 slots={}", slots)
        
        return DialogueStateTracker(session_id=session_id, slots=slots)
    
    async def get_or_create_tracker(self, session_id:Text) -> DialogueStateTracker:
        """获取或创建新的Tracker对象
        Args:
            session_id: 会话ID
        Returns:
            DialogueStateTracker: 新的Tracker对象
        """
        logger.debug("get_or_create_tracker: 获取或创建新的Tracker对象 session_id={}", session_id)
        tracker = await self.retrieve(session_id)
        if tracker is None:
            tracker = self.create_tracker(session_id)
            await self.save(tracker)
        return tracker
    
    def set_domain(self, domain:Domain) -> None:
        """设置Domain对象
        Args:
            domain: Domain对象
        """
        self.domain = domain