from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from rank_bm25 import BM25Okapi

from gridmind.core.config import settings
from gridmind.rag.embedding import cosine, hash_embed, tokenize
from gridmind.rag.loader import load_directory, load_text_file
from gridmind.rag.reranker import simple_rerank
from gridmind.rag.splitter import split_text


@dataclass
class DocumentRecord:
    doc_id: str
    name: str
    text: str
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChunkRecord:
    chunk_id: str
    doc_id: str
    text: str
    embedding: list[float]
    meta: dict[str, Any] = field(default_factory=dict)


class KnowledgeStore:
    """In-memory hybrid RAG store (vector + BM25 + simple rerank)."""

    def __init__(self) -> None:
        self.documents: dict[str, DocumentRecord] = {}
        self.chunks: list[ChunkRecord] = []
        self._bm25: BM25Okapi | None = None
        self._tokenized: list[list[str]] = []

    def list_documents(self) -> list[dict[str, Any]]:
        return [
            {
                "doc_id": d.doc_id,
                "name": d.name,
                "chars": len(d.text),
                "meta": d.meta,
            }
            for d in self.documents.values()
        ]

    def upsert_text(self, name: str, text: str, meta: dict[str, Any] | None = None) -> str:
        doc_id = str(uuid4())
        record = DocumentRecord(doc_id=doc_id, name=name, text=text, meta=meta or {})
        self.documents[doc_id] = record
        for piece in split_text(text):
            self.chunks.append(
                ChunkRecord(
                    chunk_id=str(uuid4()),
                    doc_id=doc_id,
                    text=piece,
                    embedding=hash_embed(piece),
                    meta={"source": name, **(meta or {})},
                )
            )
        self._rebuild_bm25()
        return doc_id

    def ingest_path(self, path: Path) -> str:
        text, meta = load_text_file(path)
        return self.upsert_text(path.name, text, meta)

    def bootstrap_seed(self) -> int:
        docs = load_directory(settings.knowledge_dir)
        count = 0
        for text, meta in docs:
            self.upsert_text(meta["source"], text, meta)
            count += 1
        return count

    def _rebuild_bm25(self) -> None:
        self._tokenized = [tokenize(c.text) for c in self.chunks]
        self._bm25 = BM25Okapi(self._tokenized) if self._tokenized else None

    def hybrid_search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        if not self.chunks:
            return []
        q_emb = hash_embed(query)
        vector_hits = sorted(
            (
                {
                    "chunk_id": c.chunk_id,
                    "doc_id": c.doc_id,
                    "text": c.text,
                    "meta": c.meta,
                    "score": cosine(q_emb, c.embedding),
                    "channel": "vector",
                }
                for c in self.chunks
            ),
            key=lambda x: x["score"],
            reverse=True,
        )[: top_k * 2]

        bm25_hits: list[dict[str, Any]] = []
        if self._bm25 is not None:
            scores = self._bm25.get_scores(tokenize(query))
            ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[: top_k * 2]
            for idx, score in ranked:
                c = self.chunks[idx]
                bm25_hits.append(
                    {
                        "chunk_id": c.chunk_id,
                        "doc_id": c.doc_id,
                        "text": c.text,
                        "meta": c.meta,
                        "score": float(score),
                        "channel": "bm25",
                    }
                )

        merged: dict[str, dict[str, Any]] = {}
        for hit in vector_hits + bm25_hits:
            key = hit["chunk_id"]
            if key not in merged or hit["score"] > merged[key]["score"]:
                merged[key] = hit
        return simple_rerank(query, list(merged.values()), top_k=top_k)

    async def answer(self, question: str, llm_answer: str | None = None) -> dict[str, Any]:
        hits = self.hybrid_search(question, top_k=4)
        context = "\n\n".join(f"[{h['meta'].get('source', h['doc_id'])}] {h['text']}" for h in hits)
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
        }


_store: KnowledgeStore | None = None


def get_knowledge_store() -> KnowledgeStore:
    global _store
    if _store is None:
        _store = KnowledgeStore()
        _store.bootstrap_seed()
    return _store
