# 文件说明：配置 dataclass 定义（仅类型声明，不包含加载逻辑）。

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EnvKeysConfig:
    """环境变量键名配置。"""

    app_env: str
    env_fallback: str
    log_level: str
    log_enable_file: str
    service_name: str


@dataclass(frozen=True)
class DefaultsConfig:
    """默认值配置。"""

    app_env: str
    log_level_dev: str
    log_level_prod: str
    log_enable_file: str
    service_name: str


@dataclass(frozen=True)
class BusinessConfig:
    """业务常量配置。"""

    default_sender_id: str
    default_encoding: str


@dataclass(frozen=True)
class ActionsConfig:
    """动作名称配置。"""

    listen: str
    restart: str
    session_start: str
    default_fallback: str
    deactivate_loop: str
    back: str


@dataclass(frozen=True)
class SlotsConfig:
    """槽位配置。"""

    type_any: str


@dataclass(frozen=True)
class MysqlConfig:
    """MySQL 配置。"""

    host: str | None
    port: int
    user: str
    password: str | None
    db: str
    tracker_table_name: str


@dataclass(frozen=True)
class Settings:
    """顶层配置对象（供业务代码直接引用）。"""

    env_keys: EnvKeysConfig
    defaults: DefaultsConfig
    business: BusinessConfig
    actions: ActionsConfig
    slots: SlotsConfig
    mysql: MysqlConfig
    app_env: str
    log_level: str
    log_enable_file: bool
    service_name: str

