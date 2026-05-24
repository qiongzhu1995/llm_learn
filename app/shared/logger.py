"""全局日志工具（基于 loguru）。

设计目标：
- 控制台 + 文件双写；Docker 部署时 stdout 由平台采集
- 每条日志带 env / session_id / trace_id 等上下文，便于按会话检索
- 框架无关：入口层在请求开始时注入上下文，不绑定 FastAPI
"""

from __future__ import annotations

import json
import re
import sys
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Iterator
from uuid import uuid4

from loguru import logger as _logger

from app.shared.config import settings

# 请求级上下文（协程/线程隔离，由 set_log_context / log_context 写入）
session_id_var: ContextVar[str] = ContextVar("session_id", default="")
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")
port_var: ContextVar[str] = ContextVar("port", default="")
path_var: ContextVar[str] = ContextVar("path", default="")
method_var: ContextVar[str] = ContextVar("method", default="")

# 手机号脱敏正则
_PHONE_PATTERN = re.compile(r"(1[3-9]\d{9})")


def new_trace_id() -> str:
    """生成请求级 trace_id，用于串联单次请求内的全部日志。"""
    return uuid4().hex


def mask_sensitive(text: str) -> str:
    """对日志文本做脱敏：手机号中间四位、password/token 等敏感字段。"""
    masked = _PHONE_PATTERN.sub(lambda m: f"{m.group(1)[:3]}****{m.group(1)[7:]}", text)
    for key in ("password", "token", "secret", "api_key", "authorization"):
        masked = re.sub(
            rf'("{key}"\s*:\s*")[^"]+(")',
            r"\1***\2",
            masked,
            flags=re.IGNORECASE,
        )
    return masked


def _patch_record(record: dict[str, Any]) -> None:
    """loguru patcher：为每条日志注入 env/session/trace 等上下文，并脱敏 message。"""
    extra = record["extra"]
    _s = settings
    extra.setdefault("env", _s["app_env"])
    extra.setdefault("service", _s["service_name"])
    extra.setdefault("session_id", session_id_var.get())
    extra.setdefault("trace_id", trace_id_var.get())
    extra.setdefault("port", port_var.get())
    extra.setdefault("path", path_var.get())
    extra.setdefault("method", method_var.get())
    if isinstance(record.get("message"), str):
        record["message"] = mask_sensitive(record["message"])


def set_log_context(
    *,
    session_id: str | None = None,
    trace_id: str | None = None,
    port: str | int | None = None,
    path: str | None = None,
    method: str | None = None,
) -> None:
    """在请求/任务入口设置日志上下文（框架无关，由调用方显式调用）。"""
    if session_id is not None:
        session_id_var.set(session_id)
    if trace_id is not None:
        trace_id_var.set(trace_id)
    if port is not None:
        port_var.set(str(port))
    if path is not None:
        path_var.set(path)
    if method is not None:
        method_var.set(method.upper())


def clear_log_context() -> None:
    """请求结束后清空上下文，避免泄漏到下一个请求或协程。"""
    session_id_var.set("")
    trace_id_var.set("")
    port_var.set("")
    path_var.set("")
    method_var.set("")


@contextmanager
def log_context(
    *,
    session_id: str | None = None,
    trace_id: str | None = None,
    port: str | int | None = None,
    path: str | None = None,
    method: str | None = None,
) -> Iterator[None]:
    """上下文管理器：进入时设置日志上下文，退出时自动清理。"""
    set_log_context(
        session_id=session_id,
        trace_id=trace_id or new_trace_id(),
        port=port,
        path=path,
        method=method,
    )
    try:
        yield
    finally:
        clear_log_context()


def _console_format() -> str:
    """控制台彩色输出格式：时间 + 级别 + 环境 + 会话 + 文件:行号 - 信息。"""
    return (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level:<8}</level> | "
        "<yellow>env={extra[env]}</yellow> | "
        "<magenta>session={extra[session_id]}</magenta> | "
        "<blue>trace={extra[trace_id]}</blue> | "
        "<cyan>{file.name}:{line}</cyan> - "
        "<level>{message}</level>\n"
        "{exception}"
    )


def _file_format() -> str:
    """文件文本日志格式（无颜色标签，字段比控制台更全）。"""
    return (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | env={extra[env]} | "
        "session={extra[session_id]} | trace={extra[trace_id]} | "
        "port={extra[port]} | path={extra[path]} | method={extra[method]} | "
        "{file.name}:{line} - {message}\n{exception}"
    )


def _build_json_line(record: dict[str, Any]) -> str:
    """将单条日志记录序列化为 JSON 字符串，便于按 session_id 检索。"""
    payload = {
        "time": record["time"].strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        "level": record["level"].name,
        "env": record["extra"].get("env"),
        "service": record["extra"].get("service"),
        "session_id": record["extra"].get("session_id") or None,
        "trace_id": record["extra"].get("trace_id") or None,
        "port": record["extra"].get("port") or None,
        "path": record["extra"].get("path") or None,
        "method": record["extra"].get("method") or None,
        "file": record["file"].name,
        "line": record["line"],
        "message": record["message"],
    }
    if record["exception"] is not None:
        payload["exception"] = str(record["exception"])
    return json.dumps(payload, ensure_ascii=False)


class _LoggerSingleton:
    """全局日志单例：负责初始化目录、sink 配置与轮转策略。"""

    _instance: "_LoggerSingleton | None" = None
    _lock = Lock()

    def __new__(cls) -> "_LoggerSingleton":
        """线程安全的单例构造，保证进程内只初始化一次。"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        """初始化日志目录、本次启动的日志文件路径，并注册控制台/文件 sink。"""
        if self._initialized:
            return

        self.project_root = Path(__file__).resolve().parents[2]
        self.logs_root = self.project_root / "logs"
        self.start_date = datetime.now().strftime("%Y-%m-%d")
        self._rotation_date_marker = self.start_date
        self.start_date_dir = self.logs_root / self.start_date
        self.start_date_dir.mkdir(parents=True, exist_ok=True)

        today_existing = sorted(self.start_date_dir.glob(f"{self.start_date}_*.log"))
        self.start_index = len(today_existing) + 1
        self.run_log_path = self.start_date_dir / f"{self.start_date}_{self.start_index:03d}.log"
        self.json_log_path = self.start_date_dir / f"{self.start_date}_{self.start_index:03d}.jsonl"

        _logger.configure(patcher=_patch_record)
        self._configure_sinks()
        self._initialized = True

        _s = settings
        _logger.info(
            "logger initialized env={} level={} file_enabled={}",
            _s["app_env"],
            _s["log_level"],
            _s["log_enable_file"],
        )

    def _should_rotate(self, message: Any, file_obj: Any) -> bool:
        """判断是否需要轮转：跨日（凌晨）或单文件超过 10MB。"""
        current_date = datetime.now().strftime("%Y-%m-%d")
        if current_date != self._rotation_date_marker:
            self._rotation_date_marker = current_date
            return True
        return file_obj.tell() >= 10 * 1024 * 1024

    def _jsonl_sink(self, message: Any) -> None:
        """自定义 sink：将结构化 JSON 行追加写入 .jsonl 文件。"""
        line = _build_json_line(message.record)
        with self.json_log_path.open("a", encoding="utf-8") as fp:
            fp.write(line + "\n")

    def _configure_sinks(self) -> None:
        """配置所有输出目标：stdout、运行日志、jsonl、debug 专用、error 专用。"""
        _s = settings
        _logger.remove()

        _logger.add(
            sys.stdout,
            level=_s["log_level"],
            format=_console_format(),
            colorize=True,
            backtrace=True,
            diagnose=_s["app_env"] in {"dev", "test"},
            enqueue=True,
        )

        if not _s["log_enable_file"]:
            return

        file_format = _file_format()

        _logger.add(
            str(self.run_log_path),
            level=_s["log_level"],
            format=file_format,
            encoding="utf-8",
            enqueue=True,
            backtrace=True,
            diagnose=_s["app_env"] in {"dev", "test"},
            rotation=self._should_rotate,
            retention="60 days",
        )

        _logger.add(
            self._jsonl_sink,
            level=_s["log_level"],
            format="{message}",
            enqueue=True,
        )

        _logger.add(
            str(self.start_date_dir / "debug.log"),
            level="DEBUG",
            filter=lambda record: record["level"].name == "DEBUG",
            format=file_format,
            encoding="utf-8",
            enqueue=True,
            rotation=self._should_rotate,
            retention="7 days",
        )

        _logger.add(
            str(self.start_date_dir / "error.log"),
            level="ERROR",
            format=file_format,
            encoding="utf-8",
            enqueue=True,
            backtrace=True,
            diagnose=True,
            rotation=self._should_rotate,
            retention="60 days",
        )


_LOGGER_SINGLETON = _LoggerSingleton()
logger = _logger


def get_logger() -> Any:
    """获取全局 logger 实例（与模块级 logger 相同）。"""
    return logger
