"""读取 docs/prompts 下的 .prompt 文件。"""

from __future__ import annotations

from pathlib import Path

from app.shared.config import settings


def load_prompt(prompt_name: str) -> str:
    """读取提示词文件并返回字符串内容。

    Args:
        prompt_name: 提示词文件名（可带或不带 .prompt 后缀）

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

    key = prompt_name[:-7] if prompt_name.endswith(".prompt") else prompt_name
    if key not in prompt_files:
        raise ValueError(f"未在配置中声明的提示词变量: {prompt_name}")

    filename = prompt_files[key]
    prompt_path = prompts_dir / filename
    return prompt_path.read_text(encoding="utf-8")

__all__ = ["load_prompt"]

