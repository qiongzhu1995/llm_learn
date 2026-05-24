# 文件说明：配置 dataclass 定义（Structured Config，含默认值）。

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from omegaconf import DictConfig, OmegaConf

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class EnvKeysConfig:
    """环境变量键名配置。"""

    app_env: str = "APP_ENV"
    env_fallback: str = "ENV"
    log_level: str = "LOG_LEVEL"
    log_enable_file: str = "LOG_ENABLE_FILE"
    service_name: str = "SERVICE_NAME"


@dataclass
class DefaultsConfig:
    """默认值配置。"""

    app_env: str = "dev"
    log_level_dev: str = "DEBUG"
    log_level_prod: str = "INFO"
    log_enable_file: str = "true"
    service_name: str = "customer-service-agent"


@dataclass
class BusinessConfig:
    """业务常量配置。"""

    default_sender_id: str = "default"
    default_encoding: str = "utf-8"


@dataclass
class ActionsConfig:
    """动作名称配置。"""

    listen: str = "action_listen"
    restart: str = "action_restart"
    session_start: str = "action_session_start"
    default_fallback: str = "action_default_fallback"
    deactivate_loop: str = "action_deactivate_loop"
    back: str = "action_back"


@dataclass
class SlotsConfig:
    """槽位配置。"""

    type_any: str = "any"


@dataclass
class MysqlConfig:
    """MySQL 配置。"""

    host: str = "${oc.env:DB_HOST,localhost}"
    port: int = "${oc.env:DB_PORT,3306}"
    user: str = "${oc.env:DB_USER,root}"
    password: str = "${oc.env:DB_PASSWORD,''}"
    db: str = "${oc.env:DB_NAME,ecs}"
    tracker_table_name: str = "${oc.env:DB_TRACKER_TABLE_NAME,trackers}"


@dataclass
class Settings:
    """顶层配置对象（供业务代码直接引用）。"""

    env_keys: EnvKeysConfig = field(default_factory=EnvKeysConfig)
    defaults: DefaultsConfig = field(default_factory=DefaultsConfig)
    business: BusinessConfig = field(default_factory=BusinessConfig)
    actions: ActionsConfig = field(default_factory=ActionsConfig)
    slots: SlotsConfig = field(default_factory=SlotsConfig)
    mysql: MysqlConfig = field(default_factory=MysqlConfig)
    app_env: str = "${oc.env:APP_ENV,dev}"
    log_level: str = "${oc.env:LOG_LEVEL,INFO}"
    log_enable_file: bool = "${oc.env:LOG_ENABLE_FILE,true}"
    service_name: str = "${oc.env:SERVICE_NAME,customer-service-agent}"


def load_config_file() -> dict[str, Any]:
    """1) 加载配置内容（来自 Structured Config 默认值）。"""
    loaded: dict[str, Any] = OmegaConf.to_container(
        OmegaConf.structured(Settings),
        resolve=False,
    )  # type: ignore[assignment]
    if not isinstance(loaded, dict):
        raise ValueError("加载的配置必须为字典")
    return loaded


def to_omegaconf_type(config_data: dict[str, Any]) -> DictConfig:
    """2) 将配置类型转换为 OmegaConf Structured Config 类型。"""
    _ = config_data
    return OmegaConf.create(config_data)


def merge_config_with_omegaconf(
    config_data: dict[str, Any], config_type: DictConfig | None = None
) -> dict[str, Any]:
    """3) 合并配置内容与 OmegaConf 类型，返回合并后的 dict。"""
    schema = config_type or to_omegaconf_type(config_data)
    merged: dict[str, Any] = OmegaConf.to_container(
        OmegaConf.merge(schema, OmegaConf.structured(Settings)),
        resolve=True,
    )  # type: ignore[assignment]
    if not isinstance(merged, dict):
        raise ValueError("合并后的配置必须为字典")
    return merged


@lru_cache
def get_settings() -> dict[str, Any]:
    """读取、转换、合并配置并缓存结果。"""
    load_dotenv(_PROJECT_ROOT / ".env")
    raw = load_config_file()
    conf_type = to_omegaconf_type(raw)
    return merge_config_with_omegaconf(raw, conf_type)


def reload_settings() -> dict[str, Any]:
    """清空缓存并重新加载配置。"""
    global settings
    get_settings.cache_clear()
    settings = get_settings()
    return settings


# 模块级配置对象，业务代码直接引用，避免反复调用 get_settings()
settings: dict[str, Any] = get_settings()

