"""
命令基类

定义所有命令的抽象基类，提供统一的接口规范。

## Command 与 Action 的职责边界

在本架构中，Command 和 Action 有明确的职责分工：

### Command（命令）
- **来源**：由 LLM 根据用户输入生成
- **职责**：解析用户意图，更新对话状态
- **执行方式**：通过 CommandProcessor 执行
- **输出**：直接修改 Tracker 状态（如压入栈帧、设置槽位）

### Action（动作）
- **来源**：由 Policy 根据栈帧状态选择
- **职责**：执行具体操作，压入栈帧
- **执行方式**：通过 Agent 执行
- **输出**：返回 ActionResult（事件、响应）

### 处理流程
1. 用户输入 → LLM 生成 Command
2. CommandProcessor 执行 Command → 更新 Tracker（可能压入栈帧）
3. Policy 检测栈帧 → 选择 Action
4. Agent 执行 Action → 生成响应

### 栈帧化 Action
部分 Action 采用"栈帧化"设计：
- Action 只压入栈帧（如 SearchStackFrame）
- Policy 检测栈帧并执行实际操作（如检索）
- 这种设计实现了 Action 与响应生成的解耦

### 示例
```
用户: "帮我查一下订单"
↓
LLM 生成: KnowledgeAnswerCommand
↓
CommandProcessor: 确定 next_action = action_trigger_search
↓
ActionTriggerSearch: 压入 SearchStackFrame
↓
EnterpriseSearchPolicy: 检测到 SearchStackFrame，执行检索，生成响应
```
"""
from __future__ import annotations

import re
import dataclasses
from typing import Type,Any,Optional,TYPE_CHECKING
from abc import ABC,abstractmethod

if TYPE_CHECKING:
    from app.core.tracker import DialogueStateTracker

# 命令注册表
_COMMAND_REGISTRY:dict[str,Type["Command"]] = {}

def register_command(cls:Type["Command"]) -> Type["Command"]:
    """命令注册装饰器"""
    _COMMAND_REGISTRY[cls.command_name()] = cls
    return cls

def get_command_class(name:str) -> Optional[Type["Command"]]:
    """根据命令名称获取命令类"""
    return _COMMAND_REGISTRY.get(name)

def get_all_command_classes() -> dict[str,Type["Command"]]:
    """获取所有命令类"""
    return _COMMAND_REGISTRY.copy()

class Command(ABC):
    """命令基类。
    
    命令是本架构中的核心概念，表示对话系统可以执行的原子操作。
    所有具体的命令类型都应继承此基类。
    
    命令的生命周期：
    1. LLM生成器根据用户输入生成命令文本
    2. 命令解析器将文本解析为命令对象
    3. 命令处理器执行命令并更新对话状态
    """

    @abstractmethod
    @classmethod
    def command_name(cls) -> str:
        """命令名称"""
        raise NotImplementedError("子类必须实现 command_name 方法")
    
    
    @classmethod
    def command_type(cls) -> str:
        """命令类型(别名)"""
        return cls.command_name()
    
    @abstractmethod
    @classmethod
    def from_dict(cls,data:dict[str,Any]) -> "Command":
        """从字典创建命令对象"""
        raise NotImplementedError("子类必须实现 from_dict 方法")

    def as_dict(self) -> dict[str,Any]:
        """将命令对象转换为字典"""
        # dataclasses.asdict 将命令对象转换为字典
        data = dataclasses.asdict(self)
        data["command_name"] = self.command_name()
        return data

    @abstractmethod
    def run(self,tracker:"DialogueStateTracker",flows:Optional[Any] = None) -> list[dict[str,Any]]:
        """在对话状态追踪器上执行此命令，并返回产生的事件。
        Args:
            tracker: 对话状态追踪器
            flows: 对话流程
        Returns:
            list[dict[str,Any]]: 产生的事件
        """
        raise NotImplementedError("子类必须实现 run 方法")
    
    @classmethod
    def from_dsl(cls,text:str) -> Optional["Command"]:
        """从DSL文本解析命令"""
        # 
        pattern = cls.regex_pattern()
        if not pattern:
            return None
        # re.match 匹配文本，返回匹配对象 ,IGNORECASE 忽略大小写
        match = re.match(pattern,text,re.IGNORECASE)
        if match:
            return cls._from_regex_match(match)
        return None

    @classmethod
    def _from_regex_match(cls,match:re.Match) -> Optional["Command"]:
        """从正则匹配结果创建命令 子类应该覆盖此方法以实现具体的解析逻辑"""
        raise NotImplementedError("子类必须实现 _from_regex_match 方法")

    @classmethod
    def regex_pattern(cls) -> Optional[str]:
        """返回用于解析此命令的正则表达式模式"""
        return None
    
    def to_dsl(self) -> str:
        """将命令对象转换为DSL文本"""
        return f"{self.command_name()}"

    def __hash__(self) -> int:
        """返回命令对象的哈希值 用于在集合中唯一标识命令"""
        return hash(self.command_name())

    def __eq__(self,other:object) -> bool:
        """判断两个命令对象是否相等 通过as_dict()比较"""
        if not isinstance(other,Command):
            return False
        return self.as_dict() == other.as_dict()
    
    def __repr__(self) -> str:
        """返回命令对象的表示字符串 用于调试和日志记录"""
        return f"{self.__class__.__name__}({self.as_dict()})"
    
@staticmethod
def command_from_dict(data:dict[str,Any]) -> Command:
    """从字典创建命令对象。
    
    根据字典中的command字段确定命令类型，然后创建对应的命令对象"""
    command_name = data.get("command")
    if not command_name:
        raise ValueError("字典中没有command字段")
    
    command_class = get_command_class(command_name)
    if command_class is None:
        raise ValueError(f"未找到命令类: {command_name}")
    
    return command_class.from_dict(data)

def parse_command_from_text(text:str) -> Optional["Command"]:
    """从文本解析命令 尝试使用所有已注册的命令类的正则模式解析文本"""
    text = text.strip()
    for command_class in _COMMAND_REGISTRY.values():
        try:
            command = command_class.from_dsl(text)
            if command is not None:
                return command
        except (NotImplementedError,ValueError):
            continue
    return None

__all__ = ["Command","register_command","get_command_class","get_all_command_classes","command_from_dict","parse_command_from_text"]



        
        