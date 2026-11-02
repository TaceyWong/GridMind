"""Unit tests default to in-memory RAG (no Postgres required)."""

from __future__ import annotations

import os

# Must run before gridmind settings are first constructed by test imports.
os.environ["DATABASE_URL"] = ""

from gridmind.core import config as config_mod
from gridmind.core.config import get_settings
from gridmind.rag.retriever import reset_knowledge_store

get_settings.cache_clear()
config_mod.settings = get_settings()
reset_knowledge_store()
