# 文件说明：YAML 加载与配置构建工具。

from __future__ import annotations

import os
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
import yaml

from app.shared.config import (
    ActionsConfig,
    BusinessConfig,
    DefaultsConfig,
    EnvKeysConfig,
    Settings,
    SlotsConfig,
    MysqlConfig,
)
from app.shared.utils import env_bool, resolve_app_env

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CONFIG_PATH = _PROJECT_ROOT / "config" / "config.yaml"


def load_yaml_mapping(path: str | Path) -> dict[str, Any]:
    """读取 YAML 文件并返回根节点字典。"""
    yaml_path = Path(path)
    with yaml_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"YAML 根节点必须是映射类型: {yaml_path}")
    return data


def _get_by_path(data: dict[str, Any], path: str) -> Any:
    """按点分路径读取字典值（例如 mysql.port）。"""
    node: Any = data
    for part in path.split("."):
        node = node[part]
    return node


def _set_by_path(data: dict[str, Any], path: str, value: Any) -> None:
    """按点分路径写入字典值，不存在的中间节点会自动创建。"""
    node: dict[str, Any] = data
    parts = path.split(".")
    for part in parts[:-1]:
        child = node.get(part)
        if not isinstance(child, dict):
            child = {}
            node[part] = child
        node = child
    node[parts[-1]] = value


def _resolve_binding_value(config_data: dict[str, Any], rule: dict[str, Any]) -> Any:
    """根据单条 env_bindings 规则解析最终值。"""
    resolver = rule.get("resolver")
    if resolver == "app_env":
        env_keys = config_data["env_keys"]
        defaults = config_data["defaults"]
        return resolve_app_env(env_keys["app_env"], env_keys["env_fallback"], defaults["app_env"])

    env_name = rule.get("env")
    if not env_name:
        raise ValueError(f"env_bindings 缺少 env 或 resolver: {rule}")

    default_ref = rule.get("default")
    default = _get_by_path(config_data, default_ref) if isinstance(default_ref, str) else default_ref

    alt_when = rule.get("alt_when")
    if alt_when and isinstance(default_ref, str):
        field = alt_when.get("field", "app_env")
        not_in = alt_when.get("not_in", [])
        field_value = _get_by_path(config_data, field) if isinstance(field, str) else field
        if field_value not in not_in:
            alt_ref = rule.get("default_alt")
            if alt_ref is not None:
                default = _get_by_path(config_data, alt_ref) if isinstance(alt_ref, str) else alt_ref

    if resolver == "bool":
        return env_bool(env_name, str(default if default is not None else "false"))

    raw = os.getenv(env_name)
    if raw in (None, ""):
        return default

    cast_type = rule.get("cast")
    if cast_type in ("int", int):
        return int(raw)
    if cast_type in ("float", float):
        return float(raw)
    return raw.upper() if rule.get("upper") else raw


def _apply_env_bindings(raw_data: dict[str, Any]) -> dict[str, Any]:
    """对 YAML 原始配置应用 env_bindings 覆盖，并返回新字典。"""
    config_data = deepcopy(raw_data)
    bindings = config_data.pop("env_bindings", {})
    if not isinstance(bindings, dict):
        raise ValueError("env_bindings 必须是字典")

    # app_env 需要优先计算，后续默认值选择可能依赖它
    ordered_items = sorted(bindings.items(), key=lambda item: 0 if item[0] == "app_env" else 1)
    for path, rule in ordered_items:
        if not isinstance(rule, dict):
            raise ValueError(f"env_bindings.{path} 必须为映射")
        value = _resolve_binding_value(config_data, rule)
        _set_by_path(config_data, path, value)
    return config_data


def _to_dataclass(cls: type[Any], section: dict[str, Any]) -> Any:
    """将字典按 dataclass 字段白名单构建对象，忽略多余键。"""
    allowed = set(cls.__dataclass_fields__.keys())
    return cls(**{k: v for k, v in section.items() if k in allowed})


def build_settings(raw_data: dict[str, Any]) -> Settings:
    """将配置字典构建为 Settings dataclass。"""
    data = _apply_env_bindings(raw_data)
    return Settings(
        env_keys=_to_dataclass(EnvKeysConfig, data["env_keys"]),
        defaults=_to_dataclass(DefaultsConfig, data["defaults"]),
        business=_to_dataclass(BusinessConfig, data["business"]),
        actions=_to_dataclass(ActionsConfig, data["actions"]),
        slots=_to_dataclass(SlotsConfig, data["slots"]),
        mysql=_to_dataclass(MysqlConfig, data["mysql"]),
        app_env=str(data["app_env"]),
        log_level=str(data["log_level"]),
        log_enable_file=bool(data["log_enable_file"]),
        service_name=str(data["service_name"]),
    )


@lru_cache
def get_settings() -> Settings:
    """读取配置文件并缓存 Settings 实例。"""
    load_dotenv(_PROJECT_ROOT / ".env")
    return build_settings(load_yaml_mapping(_CONFIG_PATH))


def reload_settings() -> Settings:
    """清空缓存并重新加载配置。"""
    global settings
    get_settings.cache_clear()
    settings = get_settings()
    return settings


# 模块级配置对象，业务代码直接引用，避免反复调用 get_settings()
settings: Settings = get_settings()
