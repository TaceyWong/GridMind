from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = PACKAGE_ROOT / "data"
REPO_ROOT = PACKAGE_ROOT.parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "GridMind"
    api_v1_prefix: str = "/api/v1"
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # OpenAI-compatible LLM
    llm_base_url: str = Field(default="https://api.openai.com/v1", alias="LLM_BASE_URL")
    llm_api_key: str = Field(default="", alias="LLM_API_KEY")
    llm_model: str = Field(default="gpt-4o-mini", alias="LLM_MODEL")
    llm_timeout: float = Field(default=60.0, alias="LLM_TIMEOUT")
    llm_max_retries: int = Field(default=2, alias="LLM_MAX_RETRIES")

    # Optional infra — set DATABASE_URL to enable Postgres + pgvector RAG
    database_url: str = Field(default="", alias="DATABASE_URL")
    redis_url: str = Field(default="", alias="REDIS_URL")
    api_key: str = Field(default="", alias="GRIDMIND_API_KEY")
    embedding_dim: int = Field(default=64, alias="EMBEDDING_DIM")
    # Docling 走独立 Docker 服务（本仓库不 pip 安装 docling）
    docling_serve_url: str = Field(
        default="http://127.0.0.1:5001",
        alias="DOCLING_SERVE_URL",
    )
    docling_serve_api_key: str = Field(default="", alias="DOCLING_SERVE_API_KEY")
    bge_model_name: str = Field(
        default="BAAI/bge-small-zh-v1.5",
        alias="BGE_MODEL_NAME",
    )

    # Paths
    knowledge_dir: Path = Field(default=DATA_ROOT / "knowledge")
    semantic_model_path: Path = Field(default=DATA_ROOT / "semantic" / "grid.yaml")
    sqlite_path: Path = Field(default=DATA_ROOT / "gridmind.db")

    @property
    def has_llm_key(self) -> bool:
        return bool(self.llm_api_key.strip())

    @property
    def use_pgvector(self) -> bool:
        return bool(self.database_url.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
