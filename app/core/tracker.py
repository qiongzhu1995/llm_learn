"""
tracker - 对话状态追踪器

管理对话过程中的状态信息，包括槽位值、对话历史、活跃Flow等。
Tracker是对话系统的核心数据结构，记录完整的对话上下文。
"""
import time
from typing import Optional,Any
from dataclasses import dataclass,field

from app.core.slots import Slot,create_slot
from app.shared.constants import DEFAULT_SENDER_ID,ACTION_LISTEN


@dataclass
class UserMessage:
    """
    分装用户发送的消息及其元数据
    """
    text: str # 用户发送的消息文本
    sender_id:str = DEFAULT_SENDER_ID # 发送者ID 通常是用户ID
    timestamp: float = field(default_factory=time.time)  # 消息发送时间戳
    input_chanel:Optional[str] = None # 输入通道 如："rest", "websocket", "console"
    metadata:dict[str,Any] = field(default_factory=dict) # 额外元数据
   
    def to_dict(self) -> dict[str,Any]:
        """
        将用户消息转换为字典
        """
        return {
            "text": self.text,
            "sender_id": self.sender_id,
            "timestamp": self.timestamp,
            "input_chanel": self.input_chanel,
            "metadata": self.metadata,
        }
    @classmethod
    # 这里用字符串是“前向引用”：在类型注解解析时延后解析 UserMessage，避免类定义阶段的名称解析问题。
    def from_dict(cls, data: dict[str, Any]) -> "UserMessage":
        """
        从字典创建用户消息
        """
        return cls(
            text=data.get("text",""),
            sender_id=data.get("sender_id",DEFAULT_SENDER_ID),
            timestamp=data.get("timestamp",time.time()),
            input_chanel=data.get("input_chanel"),
            metadata=data.get("metadata",{}),
        )

@dataclass
class BotMessage:
    """
    分装Bot发送的消息及其元数据
    """
    text: str # Bot发送的消息文本
    data: dict[str,Any] # Bot发送的消息数据 ,包括 按钮、图片等
    timestamp: float = field(default_factory=time.time) # 消息发送时间戳
    metadata:dict[str,Any] = field(default_factory=dict) # 消息元数据 

    def to_dict(self) -> dict[str,Any]:
        """
        将Bot响应转换为字典
        """
        return {
            "text": self.text,
            "data": self.data,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BotMessage":
        """
        从字典创建Bot响应
        """
        return cls(
            text=data.get("text",""),
            data=data.get("data",{}),
            timestamp=data.get("timestamp",time.time()),
            metadata=data.get("metadata",{}),
        )

class DialogueTurn:
    """
    一个完整的对话轮次 包含一个用户消息和一个Bot响应
    """

    user_message: Optional[UserMessage] = None # 用户消息
    bot_messages: list[BotMessage] = field(default_factory=list) # Bot响应列表
    commands:list[dict[str,Any]] = field(default_factory=list) # 命令列表
    action_name:Optional[str] = None # 执行的动作名称
    timestamp:float = field(default_factory=time.time) # 轮次开始时间戳

    def to_dict(self) -> dict[str,Any]:
        """
        将对话轮次转换为字典
        """
        return {
            "user_message": self.user_message.to_dict() if self.user_message else None,
            "bot_messages": [message.to_dict() for message in self.bot_messages],
            "commands": self.commands,
            "action_name": self.action_name,
            "timestamp": self.timestamp,
        }

class DialogueStateTracker:
    """
    对话状态追踪器 管理单个用户会话的完整状态
    核心功能：
    - 记录对话历史(用户消息和Bot响应)
    - 管理槽位状态
    - 跟踪活跃的Flow（通过dialogue_stack）
    - 支持状态序列化和反序列化
    """

    def __init__(self,
            sender_id:str,
            slots:Optional[dict[str,Slot]]=None,
            max_turns:int=100,
                ):
        """
        初始化对话状态追踪器
        args:
            sender_id: 会话ID 通常是用户ID
            slots: 初始槽位字典
            max_turns: 最大保留对话回合数
        """
        self.sender_id = sender_id
        self.slots: dict[str,Slot] = slots or {}
        self.max_turns = max_turns

        # 对话历史
        self.dialogue_turns: list[DialogueTurn] = []

        # 当前轮次 (正在进行中的轮次)，还未生成Bot响应
        self._current_turn: Optional[DialogueTurn] = None

        # 对话栈 (用于管理轮次执行顺序) Todo: 实现对话栈 
        self.dialogue_stack: Optional[DialogueStack] = None

        # flow历史记录
        self.flow_history: list[dict[str,Any]] = []

        # 最新状态
        self.latest_message: Optional[UserMessage] = None
        self.latest_action_name:str = ACTION_LISTEN

        # 元数据
        self.follow_action:Optional[str] = None
        self.paused:bool = False
        self.created_at:float = field(default_factory=time.time)
        self.updated_at:float = field(default_factory=time.time)

    @property
    def active_flow(self) -> Optional[str]:
        """
        获取当前活跃的Flow 获取栈顶的Flow
        """
        pass

    # ==== 对话状态管理 ====

    def update_with_message(self, message:UserMessage) -> None:
        """ 使用新的用户更新状态 开始新的对话轮次
            Args: 
        """
        # 保存之前的轮次
        if self._current_turn is not None:
            self._save_current_turn()
        
        # 开始新的轮次
        self._current_turn = DialogueTurn(user_message=message)
        self.latest_message = message
        # 重置 latest_action_name,表示等待下一个动作
        self.latest_action_name = ACTION_LISTEN
        self.updated_at = time.time()

    def add_bot_message(self, message:BotMessage) -> None:
        """ 添加Bot响应消息 """
        if self._current_turn is  None:
            self._current_turn = DialogueTurn()
        
        self._current_turn.bot_messages.append(message)
        self.updated_at = time.time()

    def get_conversation_history(self,max_turns:Optional[int]=None) -> list[dict[str,Any]]:
        """
        获取对话历史
        Args:
            max_turns: 最大返回的轮次数
        Returns:
            list[dict[str,Any]]: 对话历史列表，每个元素是一个字典，包含用户消息和Bot响应
        """
        turns = self.dialogue_turns[:]
        # 如果当前轮次存在，则添加到历史中  
        if self._current_turn is not None:
            turns.append(self._current_turn)
        # 如果max_turns存在，则截取历史列表
        if max_turns is not None:
            turns = turns[-max_turns:]
        
        return [turn.to_dict() for turn in turns]
        
    def finalize_turn(self) -> None:
        """
        完成当前轮次
        """
        
        self._save_current_turn()
        self.updated_at = time.time()
        
        
    
    def _save_current_turn(self) -> None:
        """
        保存当前轮次
        """
        if self._current_turn is not None:
            self.dialogue_turns.append(self._current_turn)
        

            # 如果对话轮次超过最大值，删除最早的轮次
            if len(self.dialogue_turns) > self.max_turns:
                self.dialogue_turns.pop(0)
            
            self._current_turn = None

    # =====slots管理=====
    def get_slot(self, slot_name:str) -> Any:
        """
        获取槽位值
        Args:
            slot_name: 槽位名称
        Returns:
            Any: 槽位值
        """
        slot = self.slots.get(slot_name)
        return slot.value if slot is not None else None
    
    def get_all_slots(self) -> dict[str,Any]:
        """
        获取所有槽位值
        Returns:
            dict[str,Any]: 所有槽位值
        """
        return {slot_name: slot.value for slot_name, slot in self.slots.items()}

    
    def set_slot(self, slot_name:str, value:Any,create_if_exists:bool = True) -> None:
        """
        设置槽位值
        Args:
            slot_name: 槽位名称
            value: 槽位值
            create_if_exists: 如果槽位不存在，是否创建
        """
        if slot_name in self.slots:
            self.slots[slot_name].value = value
        elif create_if_exists:
            self.slots[slot_name] = create_slot(name=slot_name, initial_value=None)
            self.slots[slot_name].value = value
        
        self.updated_at = time.time()

    def rest_slot(self) -> None:
        """
        重置所有槽位为初始值
        """
        for slot in self.slots.values():
            slot.reset()
        self.updated_at = time.time()
    
   
        
        









