from __future__ import annotations

from gridmind.rag.embedding import tokenize


def simple_rerank(query: str, candidates: list[dict], top_k: int = 5) -> list[dict]:
    q_tokens = set(tokenize(query))
    scored: list[dict] = []
    for item in candidates:
        text_tokens = set(tokenize(item.get("text", "")))
        overlap = len(q_tokens & text_tokens)
        score = float(item.get("score", 0.0)) + overlap * 0.05
        scored.append({**item, "score": score})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]
