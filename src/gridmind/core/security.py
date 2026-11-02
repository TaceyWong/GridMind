from fastapi import Header, HTTPException

from gridmind.core.config import settings


async def optional_api_key(x_api_key: str | None = Header(default=None)) -> str | None:
    """If GRIDMIND_API_KEY is set, require matching X-API-Key header."""
    expected = settings.api_key.strip()
    if not expected:
        return None
    if not x_api_key or x_api_key != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")
    return x_api_key


class UserContext:
    """Trusted user context injected by the backend (never trust LLM-provided ids)."""

    def __init__(
        self,
        user_id: str = "demo-user",
        tenant_id: str = "demo-tenant",
        roles: list[str] | None = None,
    ) -> None:
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.roles = roles or ["analyst"]
