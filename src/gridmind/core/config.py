from pydantic import BaseModel


class Settings(BaseModel):
    """Application settings placeholder. Wire env/config later."""

    app_name: str = "GridMind"
    api_v1_prefix: str = "/api/v1"
    host: str = "0.0.0.0"
    port: int = 8000


settings = Settings()
