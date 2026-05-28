"""读取并渲染 docs/prompts 下的 jinja2 提示词模板。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Template

from app.shared.config import settings


def load_prompt(prompt_name: str, **context: Any) -> str:
    """读取并渲染提示词模板，返回字符串内容。

    Args:
        prompt_name: 提示词模板名（可带或不带 .jinja2 后缀）
        **context: 渲染模板所需变量

    Returns:
        str: 提示词文本内容
    """
    prompts_dir = Path(settings.prompts.path)
    if not prompts_dir.is_absolute():
        prompts_dir = Path(__file__).resolve().parents[2] / prompts_dir

    prompt_files = {
        "rag_prompt": settings.prompts.rag_prompt_file,
        "chitchat_prompt": settings.prompts.chitchat_prompt_file,
    }

    key = prompt_name
    if key.endswith(".jinja2"):
        key = key[:-7]
    elif key.endswith(".prompt"):
        key = key[:-7]

    if key not in prompt_files:
        raise ValueError(f"未在配置中声明的提示词变量: {prompt_name}")

    filename = prompt_files[key]
    prompt_path = prompts_dir / filename
    template_text = prompt_path.read_text(encoding="utf-8")
    # render 函数是jinja2.Template类的实例方法，用于渲染模板并返回渲染后的字符串
    return Template(template_text).render(**context)

__all__ = ["load_prompt"]

