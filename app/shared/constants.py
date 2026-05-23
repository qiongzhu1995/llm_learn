# 文件说明：常量与配置默认值（环境变量键名、默认值、运行时解析值）。

from __future__ import annotations

import os
from typing import Final

# ====================== 环境变量键名 ======================
ENV_APP_ENV: Final[str] = "APP_ENV"
ENV_ENV_FALLBACK: Final[str] = "ENV"
ENV_LOG_LEVEL: Final[str] = "LOG_LEVEL"
ENV_LOG_ENABLE_FILE: Final[str] = "LOG_ENABLE_FILE"
ENV_SERVICE_NAME: Final[str] = "SERVICE_NAME"

# ====================== 配置默认值（与 .env.example 保持一致） ======================
DEFAULT_APP_ENV: Final[str] = "dev"
DEFAULT_LOG_LEVEL_DEV: Final[str] = "DEBUG"
DEFAULT_LOG_LEVEL_PROD: Final[str] = "INFO"
DEFAULT_LOG_ENABLE_FILE: Final[str] = "true"
DEFAULT_SERVICE_NAME: Final[str] = "customer-service-agent"

_TRUE_VALUES: Final[frozenset[str]] = frozenset({"1", "true", "yes"})
_ENV_ALIASES: Final[dict[str, str]] = {
    "production": "prod",
    "development": "dev",
}


def env_bool(key: str, default: str) -> bool:
    """读取布尔型环境变量。"""
    return os.getenv(key, default).lower() in _TRUE_VALUES


def resolve_app_env() -> str:
    """解析运行环境，支持 APP_ENV / ENV 及 production→prod 别名。"""
    raw = (os.getenv(ENV_APP_ENV) or os.getenv(ENV_ENV_FALLBACK) or DEFAULT_APP_ENV).lower()
    return _ENV_ALIASES.get(raw, raw)


# ====================== 运行时配置（logger 等模块统一引用） ======================
APP_ENV: str = resolve_app_env()
LOG_LEVEL: str = (
    os.getenv(ENV_LOG_LEVEL, DEFAULT_LOG_LEVEL_DEV if APP_ENV in {"dev", "test"} else DEFAULT_LOG_LEVEL_PROD)
).upper()
LOG_ENABLE_FILE: bool = env_bool(ENV_LOG_ENABLE_FILE, DEFAULT_LOG_ENABLE_FILE)
SERVICE_NAME: str = os.getenv(ENV_SERVICE_NAME, DEFAULT_SERVICE_NAME)

# ====================== 业务常量 ======================
DEFAULT_SENDER_ID: Final[str] = "default"

# ====================== Action 名称 ======================
ACTION_LISTEN: Final[str] = "action_listen"

# ====================== 槽位类型 ======================
SLOT_TYPE_ANY: Final[str] = "any"
