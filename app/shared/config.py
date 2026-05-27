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

    listen: str = "action_listen" # 监听动作
    restart: str = "action_restart" # 重启动作
    session_start: str = "action_session_start" # 会话开始动作
    default_fallback: str = "action_default_fallback" # 默认降级动作
    deactivate_loop: str = "action_deactivate_loop" # 关闭循环动作
    back: str = "action_back" # 回退动作
    min_confidence: float = 0.0 # 最小置信度


@dataclass
class SlotsConfig:
    """槽位配置。"""

    slot_type_text: str = "text"
    slot_type_bool: str = "bool"
    slot_type_float: str = "float"
    slot_type_list: str = "list"
    slot_type_categorical: str = "categorical"
    slot_type_any: str = "any"


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
class PromptConfig:
    """提示词配置。"""

    path: str = "${oc.env:PROMPTS_DIR,docs/prompts}"
    rag_prompt_file: str = "rag_prompt.prompt"
    chitchat_prompt_file: str = "chitchat_prompt.prompt"
    default_init_response: str = "你好，我是客服小助手，有什么可以帮您的？" # 默认初始化响应
    chitchat_init_response: str = "您好，很开心和您聊天，请问有什么可以帮您的？" # 闲聊初始化响应
    handoff_text: str = "好的，正在为您转接人工客服，请稍候..." # 人工转接响应
    default_fallback_response: str = "抱歉，我没有理解您的意思。请换一种方式表达。" # 默认降级响应
    default_complete_response: str = "还有什么我可以帮您的吗?" # 默认完成响应

@dataclass
class DegradationReasonConfig:
    """降级原因常量类。
    
    封装企业搜索策略中的降级原因常量。
    降级链: Flow -> RAG -> Chitchat -> CannotHandle
    """
    DEFAULT: str = "default" # 默认降级
    CHITCHAT: str = "chitchat" # 闲聊降级
    NOT_SUPPORTED: str = "not_supported" # 不支持降级
    INVALID_INTENT: str = "invalid_intent" # 无效意图降级
    NO_RELEVANT_ANSWER: str = "no_relevant_answer" # 无相关答案降级
    INTERNAL_ERROR: str = "internal_error" # 内部错误降级
    CANNOT_HANDLE: str = "cannot_handle" # 无法处理降级


@dataclass
class Settings:
    """顶层配置对象（供业务代码直接引用）。"""

    env_keys: EnvKeysConfig = field(default_factory=EnvKeysConfig)
    defaults: DefaultsConfig = field(default_factory=DefaultsConfig)
    business: BusinessConfig = field(default_factory=BusinessConfig)
    actions: ActionsConfig = field(default_factory=ActionsConfig)
    slots: SlotsConfig = field(default_factory=SlotsConfig)
    mysql: MysqlConfig = field(default_factory=MysqlConfig)
    prompts: PromptConfig = field(default_factory=PromptConfig)
    degradation: DegradationReasonConfig = field(default_factory=DegradationReasonConfig)
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
    return OmegaConf.structured(Settings)


def merge_config_with_omegaconf(
    config_data: dict[str, Any], config_type: DictConfig | None = None
) -> Settings:
    """3) 合并配置内容与 OmegaConf 类型，返回合并后的 Settings。"""
    schema = config_type or to_omegaconf_type(config_data)
    merged_cfg = OmegaConf.merge(schema, OmegaConf.create(config_data))
    merged_obj = OmegaConf.to_object(merged_cfg)
    if not isinstance(merged_obj, Settings):
        raise ValueError("合并后的配置必须为 Settings 类型")
    return merged_obj


@lru_cache
def get_settings() -> Settings:
    """读取、转换、合并配置并缓存结果。"""
    load_dotenv(_PROJECT_ROOT / ".env")
    raw = load_config_file()
    conf_type = to_omegaconf_type(raw)
    return merge_config_with_omegaconf(raw, conf_type)


def reload_settings() -> Settings:
    """清空缓存并重新加载配置。"""
    global settings
    get_settings.cache_clear()
    settings = get_settings()
    return settings


# 模块级配置对象，业务代码直接引用，避免反复调用 get_settings()
settings: Settings = get_settings()

