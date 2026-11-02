"""Demo 共用小工具：读环境变量、无 Key 时降级提示。"""

from __future__ import annotations

import os
from pathlib import Path


def _load_dotenv_simple() -> None:
    """不额外依赖 python-dotenv：手工解析仓库根 .env（存在才读）。"""
    path = Path(__file__).resolve().parents[3] / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        os.environ.setdefault(key, value)


_load_dotenv_simple()


def has_api_key() -> bool:
    return bool(os.getenv("LLM_API_KEY", "").strip() or os.getenv("OPENAI_API_KEY", "").strip())


def api_key() -> str:
    return os.getenv("LLM_API_KEY", "").strip() or os.getenv("OPENAI_API_KEY", "").strip()


def base_url() -> str:
    return os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")


def model_name() -> str:
    return os.getenv("LLM_MODEL", "gpt-4o-mini")


def banner(title: str) -> None:
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def need_key_hint() -> None:
    print("未检测到 LLM_API_KEY / OPENAI_API_KEY，本示例走本地/Mock 路径。")
    print("真连模型时在仓库根目录配置 .env 后重跑即可。")
