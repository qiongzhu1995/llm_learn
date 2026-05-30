# 文件说明：包初始化。
from app.core.stores.tracker_store import TrackerStore
from app.core.stores.json_store import JSONTrackerStore
from app.core.stores.mysql_store import MySQLTrackerStore

def create_tracker_store(store_type:str="json",**kwargs) -> TrackerStore:
    """创建Tracker存储实例
    
    工厂函数，根据类型创建对应的存储后端。
    
    参数：
        store_type: 存储类型 (json/mysql/memory)
        **kwargs: 存储配置参数
        
    返回：
        TrackerStore实例
        
    示例：
        >>> store = create_tracker_store("json", path="./trackers")
        >>> await store.save(tracker)
    """
    store_type = store_type.lower()
    if store_type == "json":
        return JSONTrackerStore(**kwargs)
    elif store_type == "mysql":
        return MySQLTrackerStore(**kwargs)
    elif store_type == "memory":
        return JSONTrackerStore(path=None,in_memory=True)
    else:
        raise ValueError(f"不支持的存储类型: {store_type}"
                         f"支持的存储类型: json/mysql/memory"
                         f"请使用create_tracker_store(store_type,**kwargs)创建存储实例"
                         f"示例：create_tracker_store('json',path='./trackers')")

__all__ = ["TrackerStore","JSONTrackerStore","MySQLTrackerStore","create_tracker_store"]