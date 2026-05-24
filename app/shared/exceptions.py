# 文件说明：异常定义。



from typing import Optional,Text
from app.shared.logger import logger


class CustomerServiceAgentException(Exception):
    """该系统的基础异常类"""
    def __init__(self, message:Optional[Text] = None) -> None:

        self.message = message or self.__class__.__name__
        super().__init__(self.message)
        logger.error(f"CustomerServiceAgentException: {self.message}")

    def __str__(self) -> Text:
        return f"{self.__class__.__name__}: {self.message}"

# ======================配置异常======================
class ConfigurationException(CustomerServiceAgentException):
    """
    配置异常
    当配置文件格式错误、缺少必要配置项或配置值无效时抛出。
    """
    pass

class InvalidConfigException(ConfigurationException):
    """无效配置异常
    
    当配置值不符合预期格式或范围时抛出。
    """
    pass


class MissingConfigException(ConfigurationException):
    """缺少配置异常
    
    当必需的配置项未提供时抛出。
    """
    pass

# ======================Tracker Store相关异常======================

class TrackerStoreException(CustomerServiceAgentException):
    """Tracker Store异常基类
    
    所有Tracker Store相关异常的基类。
    """
    pass



class TrackerStoreConnectionError(TrackerStoreException):
    """Tracker存储连接错误
    
    当无法连接到存储后端时抛出。
    """
    pass


class TrackerSerializationError(TrackerStoreException):
    """Tracker序列化错误
    
    当Tracker对象无法正确序列化或反序列化时抛出。
    """
    pass

# ======================数据库连接异常======================
class DatabaseConnectionError(CustomerServiceAgentException):
    """数据库连接错误
    
    当无法连接到数据库时抛出。
    """
    pass

# ======================数据库操作异常======================
class DatabaseOperationError(CustomerServiceAgentException):
    """数据库操作错误
    
    当数据库操作失败时抛出。
    """
    pass