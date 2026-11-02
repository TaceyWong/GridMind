"""Postgres + pgvector backed knowledge store."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from pgvector import Vector
from rank_bm25 import BM25Okapi

from gridmind.core.config import settings
from gridmind.db.postgres import get_pg_connection, init_pg_schema
from gridmind.rag.embedding import hash_embed, tokenize
from gridmind.rag.loader import load_directory, load_text_file
from gridmind.rag.reranker import simple_rerank
from gridmind.rag.splitter import split_text


class PgKnowledgeStore:
    """Hybrid RAG store: pgvector ANN + in-process BM25 + simple rerank."""

    def __init__(self) -> None:
        init_pg_schema()
        self._bm25: BM25Okapi | None = None
        self._bm25_chunks: list[dict[str, Any]] = []
        self._rebuild_bm25()

    def list_documents(self) -> list[dict[str, Any]]:
        with get_pg_connection() as conn:
            rows = conn.execute(
                """
                SELECT doc_id, name, length(text) AS chars, meta
                FROM knowledge_documents
                ORDER BY created_at
                """
            ).fetchall()
        return [
            {
                "doc_id": r[0],
                "name": r[1],
                "chars": int(r[2]),
                "meta": r[3] if isinstance(r[3], dict) else json.loads(r[3] or "{}"),
            }
            for r in rows
        ]

    def upsert_text(self, name: str, text: str, meta: dict[str, Any] | None = None) -> str:
        doc_id = str(uuid4())
        meta = meta or {}
        chunk_meta = {"source": name, **meta}
        pieces = split_text(text)
        with get_pg_connection() as conn:
            conn.execute(
                """
                INSERT INTO knowledge_documents (doc_id, name, text, meta)
                VALUES (%s, %s, %s, %s::jsonb)
                """,
                (doc_id, name, text, json.dumps(meta, ensure_ascii=False)),
            )
            for piece in pieces:
                emb = hash_embed(piece, dim=settings.embedding_dim)
                conn.execute(
                    """
                    INSERT INTO knowledge_chunks (chunk_id, doc_id, text, embedding, meta)
                    VALUES (%s, %s, %s, %s, %s::jsonb)
                    """,
                    (
                        str(uuid4()),
                        doc_id,
                        piece,
                        Vector(emb),
                        json.dumps(chunk_meta, ensure_ascii=False),
                    ),
                )
        self._rebuild_bm25()
        return doc_id

    def ingest_path(self, path: Path) -> str:
        text, meta = load_text_file(path)
        return self.upsert_text(path.name, text, meta)

    def bootstrap_seed(self) -> int:
        with get_pg_connection() as conn:
            existing = conn.execute("SELECT COUNT(*) FROM knowledge_documents").fetchone()
            if existing and int(existing[0]) > 0:
                self._rebuild_bm25()
                return 0
        docs = load_directory(settings.knowledge_dir)
        count = 0
        for text, meta in docs:
            self.upsert_text(meta["source"], text, meta)
            count += 1
        return count

    def _rebuild_bm25(self) -> None:
        with get_pg_connection() as conn:
            rows = conn.execute(
                "SELECT chunk_id, doc_id, text, meta FROM knowledge_chunks ORDER BY created_at"
            ).fetchall()
        self._bm25_chunks = [
            {
                "chunk_id": r[0],
                "doc_id": r[1],
                "text": r[2],
                "meta": r[3] if isinstance(r[3], dict) else json.loads(r[3] or "{}"),
            }
            for r in rows
        ]
        tokenized = [tokenize(c["text"]) for c in self._bm25_chunks]
        self._bm25 = BM25Okapi(tokenized) if tokenized else None

    def _vector_search(self, query: str, limit: int) -> list[dict[str, Any]]:
        q_emb = Vector(hash_embed(query, dim=settings.embedding_dim))
        with get_pg_connection() as conn:
            rows = conn.execute(
                """
                SELECT chunk_id, doc_id, text, meta,
                       1 - (embedding <=> %s) AS score
                FROM knowledge_chunks
                ORDER BY embedding <=> %s
                LIMIT %s
                """,
                (q_emb, q_emb, limit),
            ).fetchall()
        hits: list[dict[str, Any]] = []
        for r in rows:
            meta = r[3] if isinstance(r[3], dict) else json.loads(r[3] or "{}")
            hits.append(
                {
                    "chunk_id": r[0],
                    "doc_id": r[1],
                    "text": r[2],
                    "meta": meta,
                    "score": float(r[4]),
                    "channel": "vector",
                }
            )
        return hits

    def _bm25_search(self, query: str, limit: int) -> list[dict[str, Any]]:
        if self._bm25 is None or not self._bm25_chunks:
            return []
        scores = self._bm25.get_scores(tokenize(query))
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:limit]
        hits: list[dict[str, Any]] = []
        for idx, score in ranked:
            c = self._bm25_chunks[idx]
            hits.append(
                {
                    "chunk_id": c["chunk_id"],
                    "doc_id": c["doc_id"],
                    "text": c["text"],
                    "meta": c["meta"],
                    "score": float(score),
                    "channel": "bm25",
                }
            )
        return hits

    def hybrid_search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        vector_hits = self._vector_search(query, limit=top_k * 2)
        bm25_hits = self._bm25_search(query, limit=top_k * 2)
        if not vector_hits and not bm25_hits:
            return []
        merged: dict[str, dict[str, Any]] = {}
        for hit in vector_hits + bm25_hits:
            key = hit["chunk_id"]
            if key not in merged or hit["score"] > merged[key]["score"]:
                merged[key] = hit
        return simple_rerank(query, list(merged.values()), top_k=top_k)

    async def answer(self, question: str, llm_answer: str | None = None) -> dict[str, Any]:
        hits = self.hybrid_search(question, top_k=4)
        context = "\n\n".join(
            f"[{h['meta'].get('source', h['doc_id'])}] {h['text']}" for h in hits
        )
        if llm_answer:
            answer = llm_answer
        elif hits:
            answer = (
                f"根据知识库检索，相关内容如下：\n{hits[0]['text'][:400]}\n"
                f"（来源：{hits[0]['meta'].get('source', hits[0]['doc_id'])}）"
            )
        else:
            answer = "知识库暂无相关内容。请先上传文档。"
        return {
            "answer": answer,
            "context": context,
            "sources": [
                {
                    "doc_id": h["doc_id"],
                    "source": h["meta"].get("source"),
                    "score": h["score"],
                    "snippet": h["text"][:160],
                }
                for h in hits
            ],
            "backend": "pgvector",
        }
