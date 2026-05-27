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

#
# ======================槽位相关异常======================
class InvalidSlotValueError(CustomerServiceAgentException):
    """槽位异常基类
    
    所有槽位相关异常的基类。
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

# ======================LLM请求异常======================
class LLMException(AtguiguException):
    """LLM异常基类
    
    所有LLM相关异常的基类。
    """
    pass


class LLMConnectionError(LLMException):
    """LLM连接错误
    
    当无法连接到LLM API服务时抛出。
    """
    pass


class LLMTimeoutError(LLMException):
    """LLM超时错误
    
    当LLM API请求超时时抛出。
    """
    pass


class   LLMResponseError(LLMException):
    """LLM响应错误
    
    当LLM返回无效或无法解析的响应时抛出。
    """
    pass


class LLMAuthenticationError(LLMException):
    """LLM认证错误
    
    当API密钥无效或认证失败时抛出。
    """
    pass


class LLMRateLimitError(LLMException):
    """LLM速率限制错误
    
    当超过API调用速率限制时抛出。
    """
    pass

