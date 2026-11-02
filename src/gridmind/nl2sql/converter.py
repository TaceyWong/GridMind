class Nl2SqlConverter:
    """NL2SQL converter stub. Wire real SQL generation later."""

    async def convert(self, natural_language: str) -> str:
        safe = natural_language.replace("'", "''")
        return f"-- stub NL2SQL\nSELECT '{safe}' AS query_echo;"
