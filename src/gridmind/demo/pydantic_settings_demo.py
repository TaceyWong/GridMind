"""学习示例 1：pydantic-settings

目标：
- 用 BaseSettings 从环境变量 / .env 读配置
- Field(alias=...) 映射大写环境变量
- 缺省值与类型校验

运行::

    uv run python -m gridmind.demo pydantic_settings
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from gridmind.demo._common import banner


class DemoSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[3] / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "GridMind-Demo"
    llm_base_url: str = Field(default="https://api.openai.com/v1", alias="LLM_BASE_URL")
    llm_api_key: str = Field(default="", alias="LLM_API_KEY")
    llm_model: str = Field(default="gpt-4o-mini", alias="LLM_MODEL")
    max_retries: int = Field(default=2, alias="LLM_MAX_RETRIES", ge=0, le=10)

    @property
    def has_key(self) -> bool:
        return bool(self.llm_api_key.strip())


def main() -> None:
    banner("1) pydantic-settings")
    settings = DemoSettings()
    print(f"app_name     = {settings.app_name}")
    print(f"llm_base_url = {settings.llm_base_url}")
    print(f"llm_model    = {settings.llm_model}")
    print(f"has_key      = {settings.has_key}")
    print(f"max_retries  = {settings.max_retries}")

    print("\n# 类型校验演示：非法 retries 会失败")
    try:
        DemoSettings.model_validate({"LLM_MAX_RETRIES": -1})
    except ValidationError as exc:
        print(exc.errors()[0]["msg"])

    print("\n要点：配置集中在 Settings；业务代码读 settings，不要散落 os.getenv。")


if __name__ == "__main__":
    main()
