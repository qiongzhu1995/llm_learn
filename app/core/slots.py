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
from typing import Text,Any,Optional,Union,Type

from app.shared.config import settings
from app.shared.exceptions import InvalidSlotValueError


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
    type_name:str = "any" # 槽位类型名称

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
    def value(self, new_value: Any) -> None:
        """设置槽位值 无效值将抛出异常"""
        if new_value is not None and not self._validate_value(new_value):
            raise InvalidSlotValueError(f"槽位{self.name}的值: {new_value} 无效，期望类型: {self.type_name}")
        self._value = new_value
    
    def _validate_value(self, value: Any) -> bool:
        """验证槽位值是否有效 子类应重写此方法实现具体的验证逻辑"""
        return True

    def reset(self) -> None:
        """重置槽位值为初始值"""
        self._value = self.initial_value
    
    def is_set(self) -> bool:
        """判断槽位是否已设置"""
        return self._value is not None
    
    def to_dict(self) -> dict[str,Any]:
        """将槽位转换为字典"""
        data =  {
            "name": self.name,
            "type": self.type_name,
            "value": self._value,
            "initial_value": self.initial_value,
            "influence_conversion": self.influence_conversion,
            "mapping_type": self.mapping_type.value
        }
        if self.description:
            data["description"] = self.description
        return data

    @classmethod
    def from_dict(cls, data: dict[str,Any]) -> "Slot":
        """从字典创建槽位"""
        slot_type = SlotType.from_type_name(data.get("type", settings.slots.slot_type_any))
        slot_class = slot_type.slot_class
        slot = slot_class(
            name=data["name"],
            initial_value=data.get("initial_value"),
            influence_conversion=data.get("influence_conversion",True),
            mappings=data.get("mappings"),
            mapping_type=data.get("mapping_type",SlotMappingType.FROM_LLM),
            description=data.get("description"),
        )
        if "value" in data:
            slot.value = data["value"]
        return slot

    def is_frin_llm(self) -> bool:
        """判断槽位是否由LLM自动提取"""
        return self.mapping_type == SlotMappingType.FROM_LLM
    
    def is_controlled(self) -> bool:
        """判断槽位是否由Action填充"""
        return self.mapping_type == SlotMappingType.CONTROLLED
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name}, value={self._value})"

class TextSlot(Slot):
    """文本槽位 用于存储文本类型的值"""
    type_name = settings.slots.slot_type_text

    def _validate_value(self, value: Any) -> bool:
        """验证槽位值是否有效"""
        return isinstance(value,str)

class BoolSlot(Slot):
    """布尔槽位 用于存储布尔类型的值"""
    type_name = settings.slots.slot_type_bool

    def _validate_value(self, value: Any) -> bool:
        """验证槽位值是否有效"""
        return isinstance(value,bool)

class FloatSlot(Slot):
    """浮点数槽位 用于存储浮点数类型的值"""
    type_name = settings.slots.slot_type_float
    
    def __init__(self,
        name:Text,
        initial_value:Any=None,
        influence_conversion:bool=True,
        mappings:Optional[list[dict[str,Any]]]=None,
        mapping_type:Union[SlotMappingType,str]=SlotMappingType.FROM_LLM,
        description:Optional[str]=None,
        min_value:Optional[float]=None,
        max_value:Optional[float]=None
    ) -> None:
        super().__init__(name,initial_value,influence_conversion,mappings,mapping_type,description)
        self.min_value = min_value
        self.max_value = max_value

    def _validate_value(self, value: Any) -> bool:
        """验证槽位值是否有效"""
        if not isinstance(value,(int,float)):
            return False
        
        if self.min_value is not None and value < self.min_value:
            return False
        if self.max_value is not None and value > self.max_value:
            return False
        return True

class ListSlot(Slot):
    """列表槽位 用于存储列表类型的值"""
    type_name = settings.slots.slot_type_list

    def __init__(self,
        name:Text,
        initial_value:Any=None,
        influence_conversion:bool=True,
        mappings:Optional[list[dict[str,Any]]]=None,
        mapping_type:Union[SlotMappingType,str]=SlotMappingType.FROM_LLM,
        description:Optional[str]=None,
    ) -> None:

        if initial_value is None:
            initial_value = []
        super().__init__(name,initial_value,influence_conversion,mappings,mapping_type,description)

    def _validate_value(self, value: Any) -> bool:
        """验证槽位值是否有效"""
        return isinstance(value,list)
    
    def append(self, item: Any) -> None:
        """添加元素到列表"""
        if self._value is None:
            self._value = []
        self._value.append(item)
    

class CategoricalSlot(Slot):
    """分类槽位 用于存储分类类型的值"""
    type_name = settings.slots.slot_type_categorical

    def __init__(self,
        name:Text,
        initial_value:Any=None,
        influence_conversion:bool=True,
        mappings:Optional[list[dict[str,Any]]]=None,
        mapping_type:Union[SlotMappingType,str]=SlotMappingType.FROM_LLM,
        description:Optional[str]=None,
        values:Optional[list[Any]]=None
    ) -> None:
        super().__init__(name,initial_value,influence_conversion,mappings,mapping_type,description)
        self.values = values or []
    
    def _validate_value(self, value: Any) -> bool:
        if not self.values:
            return True
        return value in self.values

class AnySlot(Slot):
    """任意槽位 用于存储任意类型的值"""
    type_name = settings.slots.slot_type_any
    
    def _validate_value(self, value: Any) -> bool:
        return True


class SlotType(Enum):
    """槽位类型枚举（同时维护类型名与对应槽位类）。"""

    TEXT = (settings.slots.slot_type_text, TextSlot)
    BOOL = (settings.slots.slot_type_bool, BoolSlot)
    FLOAT = (settings.slots.slot_type_float, FloatSlot)
    LIST = (settings.slots.slot_type_list, ListSlot)
    CATEGORICAL = (settings.slots.slot_type_categorical, CategoricalSlot)
    ANY = (settings.slots.slot_type_any, AnySlot)

    def __init__(self, type_name: str, slot_class: Type[Slot]) -> None:
        self.type_name = type_name
        self.slot_class = slot_class

    @classmethod
    def from_type_name(cls, type_name: str) -> "SlotType":
        """根据字符串类型名解析枚举，未知值回退 ANY。"""
        for item in cls:
            if item.type_name == type_name:
                return item
        return cls.ANY


def create_slot(
    name: Text,
    slot_type: Union[str, SlotType] = settings.slots.slot_type_any,
    mapping_type: Union[SlotMappingType, str] = SlotMappingType.FROM_LLM,
    description: Optional[str] = None,
    **kwargs: Any,
) -> Slot:
    """创建槽位。"""
    parsed_slot_type = slot_type if isinstance(slot_type, SlotType) else SlotType.from_type_name(slot_type)
    slot_class = parsed_slot_type.slot_class
    return slot_class(
        name=name,
        mapping_type=mapping_type,
        description=description,
        **kwargs
    )
