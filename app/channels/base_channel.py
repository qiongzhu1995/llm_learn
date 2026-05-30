# 文件说明：通道基类。

from dataclasses import dataclass,field
from typing import Optional,Dict,Any
import time
import uuid

@dataclass
class UserMessage:
    """用户消息。
    
    Attributes:
        text: 消息文本
        sender_id: 发送者ID
        input_channel: 输入通道名称
        message_id: 消息ID
        timestamp: 时间戳
        metadata: 元数据
    """
    text: str
    sender_id: str = "default"
    input_channel: str = "default"
    message_id: Optional[str] = None
    timestamp: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.message_id is None:
            self.message_id = str(uuid.uuid4())
        if self.timestamp is None:
            self.timestamp = time.time()

