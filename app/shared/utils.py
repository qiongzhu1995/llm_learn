# 文件说明：共享工具函数（环境变量解析等）。

from __future__ import annotations

import os
from typing import Final

_TRUE_VALUES: Final[frozenset[str]] = frozenset({"1", "true", "yes"})
_ENV_ALIASES: Final[dict[str, str]] = {
    "production": "prod",
    "development": "dev",
}


def env_bool(key: str, default: str) -> bool:
    """读取布尔型环境变量。"""
    return os.getenv(key, default).lower() in _TRUE_VALUES


def resolve_app_env(env_app_env: str, env_fallback: str, default_app_env: str) -> str:
    """解析运行环境，支持 APP_ENV / ENV 及 production→prod 别名。"""
    raw = (os.getenv(env_app_env) or os.getenv(env_fallback) or default_app_env).lower()
    return _ENV_ALIASES.get(raw, raw)
