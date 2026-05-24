"""
slots - 槽位系统

定义对话系统中的槽位类型，用于存储对话过程中收集的信息。
槽位是对话状态的核心组成部分，支持多种数据类型。

槽位映射类型：
- from_llm: 由LLM从用户输入中提取并填充
- controlled: 由Action填充，不由LLM自动提取
"""

from abc import ABC
from enum import Enum
from typing import Text,Any,Optional,Union

from app.shared.config import settings
class SlotMappingType(Enum):
    # Enum类 定义槽位映射类型
    """
    槽位映射类型
    """
    FROM_LLM = "from_llm"    # 由LLM从用户输入中提取并填充
    CONTROLLED = "controlled" # 由Action填充，不由LLM自动提取


class Slot(ABC):
    # ABC类 抽象基类 定义槽位基类 确保子类必须实现
    """
    所有槽位类型的抽象基类，定义槽位的基本属性和行为
    """
    def __init__(self,
        name:Text,
        initial_value:Any=None,
        influence_conversion:bool=True,
        mappings:Optional[list[dict[str,Any]]]=None,
        mapping_type:Union[SlotMappingType,str]=SlotMappingType.FROM_LLM,
        description:Optional[str]=None,
        ) -> None:
        """
        初始化槽位
        args:
            name: 槽位名称
            initial_value: 初始值
            influence_conversion: 是否影响对话流程
            mappings: 槽位映射规则
            mapping_type: 映射类型 FROM_LLM 或 CONTROLLED
            description: 槽位描述
        """
        self.name = name
        self.initial_value = initial_value
        self._value = initial_value
        self.influence_conversion = influence_conversion
        self.mappings = mappings or []

        # 如果映射类型是字符串，转换为枚举类型
        if isinstance(mapping_type,str):
            mapping_type = SlotMappingType(mapping_type)
        self.mapping_type = mapping_type
        self.description = description

    @property
    def value(self) -> Any:
        """
        获取槽位值
        """
        return self._value

    # 设置槽位值 影响对话流程
    @value.setter
    def value(self, value: Any) -> None:
        pass

def create_slot(name: Text, slot_type: Text | None = None, **kwargs) -> Slot:
    """创建槽位。"""
    if slot_type is None:
        slot_type = settings["slots"]["type_any"]
    raise NotImplementedError