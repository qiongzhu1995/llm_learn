"""
tracker - 对话状态追踪器

管理对话过程中的状态信息，包括槽位值、对话历史、活跃Flow等。
Tracker是对话系统的核心数据结构，记录完整的对话上下文。
"""
import time
from typing import Optional,Any
from dataclasses import dataclass,field

from app.core.slots import Slot,create_slot
from app.shared.config import settings
from app.dialogue_understanding.stack.dialogue_stack import DialogueStack

@dataclass
class UserMessage:
    """
    分装用户发送的消息及其元数据
    """
    text: str # 用户发送的消息文本
    sender_id: str = field(default_factory=lambda: settings.business.default_sender_id)
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
            sender_id=data.get("sender_id", settings.business.default_sender_id),
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
    """对话状态追踪器（Tracker）——单个用户会话的运行时「现场记录」。

    实际作用
    --------
    每个 ``sender_id``（用户/会话）对应一个 Tracker 实例，贯穿多轮对话的生命周期。
    每来一条用户消息、每执行一个 Action、每产生一条 Bot 回复，都会在这里留下痕迹。
    Policy、Action、NLG 等模块**读写的都是 Tracker**，而不是直接改 Domain。

    与 :class:`~app.core.domain.Domain` 的关系
    -----------------------------------------
    - Domain 回答：「这个 bot *能* 有哪些槽、动作、话术、Flow？」（静态配置）
    - Tracker 回答：「*当前这一轮* 用户说了什么、槽里填了什么、栈顶是哪个 Flow？」（动态状态）

    二者在 Action 执行时一并传入：用 Domain 查模板/白名单，用 Tracker 读写信道状态。

    核心职责
    --------
  1. **对话历史**：``dialogue_turns`` / ``_current_turn`` 记录每轮的
     :class:`UserMessage`、:class:`BotMessage`、执行的 ``action_name`` 与 commands。
  2. **槽位运行时值**：``slots`` 存的是带 ``.value`` 的槽位实例；``get_slot`` /
     ``set_slot`` / ``get_all_slots`` 供 Action 与模板变量替换使用。
  3. **Flow 上下文**：``dialogue_stack``（待完善）表示当前嵌套/活跃的 Flow；
     ``flow_history`` 记录已完成的 Flow；``active_flow`` 反映栈顶 Flow 名。
  4. **最新快照**：``latest_message``、``latest_action_name``（如 ``action_listen``）
     供策略判断「是否在等待用户输入」。
  5. **持久化载体**：实例状态可序列化后写入 TrackerStore（JSON/MySQL），
     下次请求加载同一 ``sender_id`` 的 Tracker 即可恢复上下文。

    典型生命周期（单轮）
    ------------------
    ``update_with_message`` → Policy 选 action → Action 可能 ``set_slot`` /
    ``add_bot_message`` → ``finalize_turn`` 将当前轮次并入 ``dialogue_turns``。

    注意：Tracker 不负责定义槽位类型或 utter 文案；那些来自 Domain 或加载器，
    初始化时可将 Domain 中的 Slot 定义拷贝/合并进 ``self.slots``。
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
        self.latest_action_name: str = settings.actions.listen

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
        self.latest_action_name = settings.actions.listen
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
    
    def start_flow(self, flow_name:str ,step_id:str = "START") -> None:
        """
        开始一个flow   将FlowStackFrame压入dialogue_stack。

        Args:
            flow_name: flow名称
            step_id: 开始步骤ID
        """
        self.dialogue_stack.push_flow_frame(flow_name,step_id)

        # 记录到历史
        self.flow_history.append({
            "flow_name": flow_name,
            "started_at": time.time(),
            "ended_at": None,
            "completed": False,
        })
        self.updated_at = time.time()
    
    def end_flow(self) -> Optional[str]:
        """结束当前Flow
        
        从dialogue_stack弹出栈顶的FlowStackFrame。
        
        返回：
            结束的Flow名称，栈为空返回None
        """
        # 获取栈顶的FlowStackFrame
        flow_frame = self.dialogue_stack.top_flow_frame()
        if flow_frame is None:
            return None
        
        flow_name = flow_frame.flow_id
        # 将它上面的所有帧弹出到该Flow
        self.dialogue_stack.pop_to_flow(flow_name)
        # 弹出本身
        self.dialogue_stack.pop()

        # 记录到历史
        for hist in reversed(self.flow_history):
            if hist["flow_name"] == flow_name and hist["ended_at"] is None:
                hist["ended_at"] = time.time()
                hist["completed"] = True
                break
        self.updated_at = time.time()
        return flow_name
    
    def cancel_flow(self) -> None:
        """ 取消所有的活跃Flow """
        self.dialogue_stack.clear
        self.updated_at = time.time()
    
    def record_pattern(self, pattern:str,completed:bool = True) -> None:
        """记录内置 Pattern 的执行历史
        
        将内置 Pattern（如 chitchat、search、cannot_handle 等）的执行记录
        添加到 flow_history 中，以便在 Inspect 页面统一展示。
        
        参数：
            pattern_type: Pattern 类型，如 "chitchat"、"search"、"cannot_handle"、
                         "completed"、"human_handoff"
            completed: 是否执行完成，默认为 True
        """
        current_time = time.time()
        self.flow_history.append({
            "flow_name":f"pattern_{pattern}",
            "started_at": current_time,
            "ended_at": current_time if completed else None,
            "completed": completed,
        })
        self.updated_at = current_time

   