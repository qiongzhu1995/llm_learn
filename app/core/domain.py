# 文件说明：领域定义。

from typing import Any,Optional,Union
from dataclasses import dataclass,field

from app.shared.config import settings
from app.core.slots import Slot


@dataclass
class ResponseTemplate:
    """响应模板类 定义Bot的响应内容，支持多种响应变体和条件。
    """
    text:Optional[str] = None  # 响应文本
    buttons:list[dict[str,Any]] = field(default_factory=list) # 按钮列表
    image:Optional[str] = None # 图片
    custom:Optional[dict[str,Any]] = None # 自定义内容
    conditions:Optional[str] = None # 条件表达式
    channel:Optional[str] = None # 指定通道类型
    metadata:dict[str,Any] = field(default_factory=dict) # 元数据
    
    def from_dict(cls,data:Union[dict[str,Any],str]) -> "ResponseTemplate":
        """从字典或字符串创建响应模板实例"""
        if isinstance(data,str):
            return cls(text=data)
        return cls(
            text=data.get("text"),
            buttons=data.get("buttons",[]),
            image=data.get("image"),
            custom=data.get("custom"),
            conditions=data.get("conditions"),
            channel=data.get("channel"),
            metadata=data.get("metadata",{})
        )
    
    def to_dict(self) -> dict[str,Any]:
        """将响应模板实例转换为字典"""
        result:dict[str,Any] = {}
        if self.text:
            result["text"] = self.text
        if self.buttons:
            result["buttons"] = self.buttons
        if self.image:
            result["image"] = self.image
        if self.custom:
            result["custom"] = self.custom
        if self.conditions:
            result["conditions"] = self.conditions
        if self.channel:
            result["channel"] = self.channel
        if self.metadata:
            result["metadata"] = self.metadata
        return result


@dataclass
class Domain:
    """领域配置（Domain）：描述 Bot「能做什么、怎么说」，一般全程不变。

    可以把它看成静态说明书，通常从 domain.yml 等配置加载；和 Tracker 各管一块：

    Domain（配置）          Tracker（状态）
    ─────────────────────────────────────────
    槽位怎么定义            槽位当前填了什么
    有哪些 action           这一轮执行了哪个 action
    utter 话术模板          用户说了什么、Bot 回了什么
    启用哪些 Flow/表单      当前卡在哪个 Flow

    一轮对话里的大致流程：
    1. Policy 选出下一个 action
    2. Action.run(tracker, domain) 执行
    3. 例如 ActionUtter：从 domain.responses 取话术，
       用 tracker 里的槽位值替换 {slot_name} 后发给用户

    改回复文案、增删动作时，应改 Domain（或 YAML），不要改 Tracker 代码。
    """
    slots:dict[str,Slot] = field(default_factory=dict) # 槽位字典
    actions:set(str) = field(default_factory=list) # 动作名称集合
    responses:dict[str,list[ResponseTemplate]] = field(default_factory=dict) # 响应模板字典
    flows:list(str) = field(default_factory=list) # Flow名称列表
    forms:dict[str,dict(str,Any)] = field(default_factory=dict) # 表单定义字典
    session_config:dict[str,Any] = field(default_factory=dict) # 会话配置字典
    version:str = field(default="1.0.0") # 版本号

    def __post_init__(self) -> None:
        """初始化后处理"""
        self._add_default_responses()

    def _add_default_responses(self) -> None:
        """添加默认响应模板"""
        actions = settings.actions
        default_actions = {
            actions.listen,
            actions.restart,
            actions.session_start,
            actions.default_fallback,
        }