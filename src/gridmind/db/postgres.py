"""Postgres connection + pgvector schema bootstrap."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from pgvector.psycopg import register_vector

from gridmind.core.config import settings


def pg_available() -> bool:
    return bool(settings.database_url.strip())


@contextmanager
def get_pg_connection() -> Iterator[psycopg.Connection]:
    if not pg_available():
        raise RuntimeError("DATABASE_URL is empty; Postgres backend disabled.")
    conn = psycopg.connect(settings.database_url, autocommit=False)
    try:
        register_vector(conn)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_pg_schema() -> None:
    """Create extension + knowledge tables (idempotent)."""
    dim = settings.embedding_dim
    with get_pg_connection() as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge_documents (
                doc_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                text TEXT NOT NULL,
                meta JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS knowledge_chunks (
                chunk_id TEXT PRIMARY KEY,
                doc_id TEXT NOT NULL REFERENCES knowledge_documents(doc_id) ON DELETE CASCADE,
                text TEXT NOT NULL,
                embedding vector({dim}) NOT NULL,
                meta JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS knowledge_chunks_doc_id_idx
                ON knowledge_chunks (doc_id)
            """
        )
        # ANN index; tiny corpora still work with sequential scan if this fails.
        conn.execute(
            """
            DO $$
            BEGIN
              IF NOT EXISTS (
                SELECT 1 FROM pg_indexes WHERE indexname = 'knowledge_chunks_embedding_hnsw'
              ) THEN
                BEGIN
                  CREATE INDEX knowledge_chunks_embedding_hnsw
                    ON knowledge_chunks USING hnsw (embedding vector_cosine_ops);
                EXCEPTION WHEN OTHERS THEN
                  NULL;
                END;
              END IF;
            END $$;
            """
        )
