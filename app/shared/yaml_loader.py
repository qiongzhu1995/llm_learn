"""
Flow加载器

从YAML文件加载Flow定义。
"""
from __future__ import annotations # 用于类型提示的注解

import yaml
from pathlib import Path
from typing import Optional,Any,Union

from app.shared.config import settings


class SafeLineLoader(yaml.SafeLoader):
    """安全的行加载器"""
    pass

def _constract_mapping(loader:SafeLineLoader, node:yaml.Node) -> dict[str, Any]:
    """构造映射时保留行号信息"""
    loader.flatten_mapping(node) # 扁平化映射节点
    pairs = loader.construct_pairs(node) # 构造键值对
    return dict(pairs)


#注册自定义构造器 用于构造映射时保留行号信息 
SafeLineLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _constract_mapping)

def read_yaml_file(file_path:str) -> Optional[dict[str, Any]]:
    """读取YAML文件 并返回字典"""
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"文件{path}不存在")
    
    with open(path, "r", encoding=settings.business.default_encoding) as f:
        data = yaml.safe_load(f)  # safe_load 只解析YAML的基础类型 dict,list,str,int,float,bool,None 不会构造自定义对象
    return data # 返回字典

def read_yaml_string(yaml_string:str) -> Optional[dict[str, Any]]:
    """读取YAML字符串 并返回字典"""
    data = yaml.safe_load(yaml_string)
    return data # 返回字典

def read_yaml_files(file_paths:list(Union[str, Path])) -> list[dict[str, Any]]:
    """读取多个YAML文件 并返回字典列表"""
    results = []
    for file_path in file_paths:
        data = read_yaml_file(file_path)
        if data is not None:
            results.append(data)
    return results # 返回字典列表
    
    
def read_yaml_multi_documents(path:Union[str, Path]) -> list[dict[str, Any]]:
    """读取多个YAML文档 支持使用--分隔的多文档yaml文件"""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"文件{path}不存在")
    with open(path, "r", encoding=settings.business.default_encoding) as f:
        documents = list(yaml.safe_load_all(f))
    
    return [doc for doc in documents if doc is not None]


def write_yaml_file(file_path:Union[str, Path], 
                    data:dict[str, Any],
                    allow_unicode:bool = True,
                    dafault_flow_style:bool = False,
                    ) -> None:
    """写入YAML文件
    Args:
        file_path: 文件路径
        data: 数据
        allow_unicode: 是否允许Unicode字符
        dafault_flow_style: 是否使用默认流样式
    Returns:
        None
    """
    return yaml.dump(data, file_path, allow_unicode=allow_unicode, default_flow_style=dafault_flow_style,sort_keys=False)


def merge_yaml_files(file_paths:list(Union[str, Path])) -> dict[str, Any]:
    """合并多个YAML文件 并返回字典"""
    results: dict[str, Any] = {}
    for file_path in file_paths:
        data = read_yaml_file(file_path)
        if data is not None:
            results = _deep_merge(results, data)
    return results # 返回字典
    
    
def _deep_merge(base:dict[str, Any], override:dict[str, Any]) -> dict[str, Any]:
    """深度合并两个字典 递归合并嵌套的字典，override中的值会覆盖base中的值。"""
    result = base.copy()

    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result