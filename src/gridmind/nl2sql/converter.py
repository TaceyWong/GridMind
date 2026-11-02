"""Backward-compatible stub wrapper around Nl2SqlEngine. """

from gridmind.nl2sql.engine import get_nl2sql_engine


class Nl2SqlConverter:
    async def convert(self, natural_language: str) -> str:
        result = await get_nl2sql_engine().run(natural_language, use_llm=False)
        return result["sql"]
