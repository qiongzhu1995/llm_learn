"""
Flow加载器

从YAML文件加载Flow定义。
"""

from __future__ import annotations

from typing import Union, Text, Any
from pathlib import Path

from app.dialogue_understanding.flow.flow import FlowsList, Flow
from app.shared.exceptions import ConfigurationException
from app.shared.yaml_loader import read_yaml_file, read_yaml_string
from app.shared.logger import logger

class FlowLoader:
    """Flow加载器。
    
    从YAML文件加载Flow定义。
    
    支持的文件格式：
    - 单个flows.yml文件
    - flows目录下的多个YAML文件
    """
    def __init__(self):
        """初始化Flow加载器"""
        pass
    
    def load(self, file_path:Union[str, Path]) -> FlowsList:
        """加载Flow"""
        path = Path(file_path)
        if path.is_file():
            return self._load_single_file(path)
        elif path.is_dir():
            return self._load_directory(path)
        else:
            raise ConfigurationException(f"无效的文件路径: {file_path}")
    
    def _load_single_file(self, file_path:Path) -> FlowsList:
        """加载单个Flow文件"""
        logger.info(f"加载单个Flow文件: {file_path}")
        data = read_yaml_file(str(file_path))
        if data is None:
            logger.warning(f"空的或者格式错误的YAML文件: {file_path}")
            return FlowsList()
        return self._parse_flow_data(data)

    
    def _load_directory(self, directory_path:Path) -> FlowsList:
        """加载目录下的所有Flow文件"""
        logger.info(f"加载目录下的所有Flow文件: {directory_path}")
        # glob 方法返回一个包含所有匹配指定模式的路径名的列表
        flow_files = list(directory_path.glob("*.yml")) + list(directory_path.glob("*.yaml"))
        if not flow_files:
            logger.warning(f"目录下没有找到Flow文件: {directory_path}")
            return FlowsList()
        # 加载所有Flow文件
        flows_list = FlowsList()
        for flow_file in flow_files:
            try:
                flow_list = self._load_single_file(flow_file)
                for flow in flow_list:
                    flows_list.add_flow(flow)
            except Exception as e:
                logger.error(f"加载Flow文件失败: {flow_file} - {e}")
                
        return flows_list
    
    def _parse_flow_data(self, data:dict[str, Any]) -> FlowsList:
        """解析Flow数据"""
        flows = []
        flows_data = data.get("flows", data)

        if not isinstance(flows_data, list):
            logger.warning(f"flows数据格式错误: {flows_data}")
            return FlowsList()
        
        for flow_id,flow_config in flows_data.items():
            # 跳过非flow字段
            if flow_id in ["version", "metadata", "imports"]:
                continue

            if not isinstance(flow_config, dict):
                logger.warning(f"flow配置格式错误: {flow_id}:{type(flow_config)}")
                continue
                
            try:
                flow = Flow.from_dict(flow_id, flow_config)
                flows.append(flow)
                logger.debug(f"加载Flow: {flow_id} - {flow.name} 共 {len(flow.steps)} 个Flow")
            except Exception as e:
                logger.error(f"加载Flow失败: {flow_id} - {e}")

        return FlowsList(flows=flows)
    
    def load_from_string(self, flow_string:str) -> FlowsList:
        """从字符串加载Flow"""
        logger.info(f"从字符串加载Flow")
        data = read_yaml_string(flow_string)
        if data is None:
            logger.warning(f"空的或者格式错误的YAML字符串")
            return FlowsList()
        return self._parse_flow_data(data)
        
def load_flows(path:Union[str, Path]) -> FlowsList:
    """加载Flow"""
    loader = FlowLoader()
    return loader.load(path)

def load_flows_from_string(flow_string:str) -> FlowsList:
    """从字符串加载Flow"""
    loader = FlowLoader()
    return loader.load_from_string(flow_string)

__all__ = ["load_flows", "load_flows_from_string", "FlowLoader"]