"""
json_store - JSON文件存储

将Tracker状态以JSON文件格式存储到本地文件系统。
适合开发、测试和小规模部署场景。
"""

import json
from typing import Optional,Iterable,Text
from pathlib import Path

from app.core.stores.tracker_store import TrackerStore
from app.core.domain import Domain
from app.core.tracker import DialogueStateTracker
from app.shared.logger import logger
from app.shared.config import Settings
from app.shared.exceptions import TrackerSerializationError,TrackerStoreException

class JSONTrackerStore(TrackerStore):
    """JSON文件Tracker存储
    
    将每个Tracker保存为独立的JSON文件。
    
    文件结构：
        {path}/
        ├── {sender_id_1}.json
        ├── {sender_id_2}.json
        └── ...
    
    属性：
        path: 存储目录路径
        in_memory: 是否使用内存存储(不持久化)
    """
    def __init__(self,
                domain:Optional[Domain] = None,
                path:Optional[str] = 'trackers',
                in_memory:bool = False,
                ) -> None:
        """
        初始化JSON文件Tracker存储
        Args:
            domain: Domain实例
            path: 存储目录路径
            in_memory: 是否使用内存存储
        """

        super().__init__(domain)

        self.in_memory = in_memory
        self._memory_store:dict[str:dict] = {} 

        if not in_memory and not path:
            self.path = Path(path)
            # 创建目录
            self.path.mkdir(parents=True,exist_ok=True)
        else:
            self.path = None
        
    def _get_file_path(self,sender_id:Text) -> Path:
        """
        获取文件路径
        """
        # 清理sender_id中的特殊字符 只保留字母、数字和下划线
        safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in sender_id)
        return self.path / f"{safe_id}.json"

    
    async def save(self,tracker: DialogueStateTracker) -> None:
        """
        保存Tracker到JSON文件
        """

        try:
            tracker_data = tracker.to_dict()
            if self.in_memory:
                self._memory_store[tracker.sender_id] = tracker.to_dict()
                logger.info(f"Tracker状态保存到内存成功...")
            else:
                file_path = self._get_file_path(tracker.sender_id)
                with open(file_path, "w", encoding=Settings.business.default_encoding) as f:
                    json.dump(tracker.to_dict(), f, ensure_ascii=False, indent=2)
                logger.info(f"Tracker状态保存到文件{file_path}成功...")
        
        except Exception as e:
            logger.error(f"保存Tracker状态失败: {e}")
            raise TrackerStoreException(f"保存Tracker状态失败: {e}")
    
    async def retrieve(self,sender_id:Text) -> Optional[DialogueStateTracker]:
        """
        从JSON文件中检索Tracker状态
        """
        try:
            if self.in_memory:
                tracker_data = self._memory_store.get(sender_id)
                logger.info(f"从内存中检索Tracker状态成功...")
            else:
                file_path = self._get_file_path(sender_id)

                if not file_path.exists():
                    logger.warning(f"文件{file_path}不存在...")
                    return None
                
                with open(file_path, "r", encoding=Settings.business.default_encoding) as f:
                    tracker_data = json.load(f)
                logger.info(f"从文件{file_path}中检索Tracker状态成功...")
            
            return DialogueStateTracker.from_dict(tracker_data,self.domain.slots)
        
        except FileNotFoundError:
            logger.warning(f"文件{file_path}不存在...")
            return None
        
        except json.JSONDecodeError as e:
            logger.error(f"文件{file_path}内容格式错误...{e}")
            return TrackerSerializationError(f"文件{file_path}内容格式错误...{e}")
        
        except Exception as e:
            logger.error(f"从JSON文件中检索Tracker状态失败: {e}")
            raise TrackerStoreException(f"从JSON文件中检索Tracker状态失败: {e}")
    
    async def delete(self,sender_id:Text) -> None:
        """
        从JSON文件中删除Tracker文件
        """
        try:
            if self.in_memory:
                self._memory_store.pop(sender_id,None)
                logger.info(f"从内存中删除Tracker状态成功...")
            else:
                file_path = self._get_file_path(sender_id)
                if  file_path.exists():
                    file_path.unlink()
                    logger.info(f"从文件{file_path}中删除Tracker文件成功...")
                else:
                    logger.warning(f"文件{file_path}不存在...")
                    return None
        
        except Exception as e:
            logger.error(f"从JSON文件中删除Tracker文件失败: {e}")
            raise TrackerStoreException(f"从JSON文件中删除Tracker文件失败: {e}")
    
    async def keys(self) -> Iterable[Text]:
        """
        获取所有会话ID
        """
        try:
            if self.in_memory:
                return list(self._memory_store.keys())

            if not self.path:
                return []
            
            return [file_path.stem for file_path in self.path.glob("*.json")]
        
        except Exception as e:
            logger.error(f"获取所有会话ID失败: {e}")
            raise TrackerStoreException(f"获取所有会话ID失败: {e}")
    
    async def close(self) -> None:
        """
        关闭JSON文件Tracker存储
        """
        if self.in_memory:
            self._memory_store.clear()
        else:
            for sender_id in await self.keys():
                await self.delete(sender_id)
        logger.info(f"JSON文件Tracker存储关闭成功...")
    
    async def __aenter__(self) -> "JSONTrackerStore":
        """
        异步上下文管理器 进入上下文时初始化JSON文件Tracker存储
        """
        return self
    
    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        """
        异步上下文管理器 退出上下文时关闭JSON文件Tracker存储
        """
        await self.close()
