"""学习示例：RAG 完整链路

覆盖：
1. 文档加载（loader）
2. 清洗/切分（splitter）
3. Embedding（本地 hash，可换云模型）
4. 索引入库（内存向量 + BM25）
5. 向量召回 / 关键词召回
6. Hybrid 合并 + Rerank
7. Context 组装 + 带引用回答
8. （可选）LLM 基于上下文生成

运行::

    uv run python -m gridmind.demo rag
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from gridmind.core.config import settings
from gridmind.demo._common import banner, has_api_key, need_key_hint
from gridmind.rag.embedding import cosine, hash_embed, tokenize
from gridmind.rag.loader import load_directory
from gridmind.rag.reranker import simple_rerank
from gridmind.rag.retriever import KnowledgeStore
from gridmind.rag.splitter import split_text


def section(title: str) -> None:
    print(f"\n--- {title} ---")


def demo_load_and_split() -> None:
    section("1) 文档加载 Loader")
    docs = load_directory(settings.knowledge_dir)
    if not docs:
        # 兜底：即时造两段文档，保证无种子文件也能跑
        docs = [
            (
                "告警数量口径：按 alarm_id 去重统计告警事件数，不是未处理告警数。",
                {"source": "inline_alarm.md"},
            ),
            (
                "主变温度传感器正常运行温度通常在 40°C～75°C。critical 表示超过保护阈值。",
                {"source": "inline_temp.md"},
            ),
        ]
        print(f"知识目录为空，使用内置文档 {len(docs)} 篇")
    else:
        print(f"从 {settings.knowledge_dir} 加载 {len(docs)} 篇")
    for text, meta in docs:
        print(f"  - {meta.get('source')}: {len(text)} chars")

    section("2) 切分 Splitter")
    for text, meta in docs:
        pieces = split_text(text, chunk_size=180, overlap=40)
        print(f"  {meta.get('source')}: {len(pieces)} chunks")
        if pieces:
            print(f"    chunk0 preview: {pieces[0][:80]!r}...")


def demo_embed() -> None:
    section("3) Embedding")
    a = hash_embed("告警数量口径按 alarm_id 去重")
    b = hash_embed("告警事件数如何统计")
    c = hash_embed("今天天气怎么样")
    print(f"  dim = {len(a)}")
    print(f"  sim(口径, 统计问法) = {cosine(a, b):.4f}")
    print(f"  sim(口径, 天气)     = {cosine(a, c):.4f}")
    print("  说明: 学习版用本地 hash 向量；生产可换 BGE/OpenAI Embedding。")


def build_store():
    section("4) 索引入库（向量 + BM25）")
    from gridmind.rag.retriever import get_knowledge_store, reset_knowledge_store

    reset_knowledge_store()
    store = get_knowledge_store()
    backend = "pgvector" if settings.use_pgvector else "memory"
    print(f"  backend   = {backend}")
    if settings.use_pgvector:
        print(f"  DATABASE_URL set → Postgres pgvector")
        docs = store.list_documents()
        print(f"  documents = {len(docs)}")
        # BM25 cache size if available
        chunks = getattr(store, "_bm25_chunks", None)
        print(f"  chunks    = {len(chunks) if chunks is not None else '?'}")
    else:
        # 独立演示：无 PG 时用内存店
        if isinstance(store, KnowledgeStore) and not store.chunks:
            store.upsert_text(
                "alarm_rules.md",
                "告警数量口径：按 alarm_id 去重统计告警事件数。status=open 表示未处理。",
            )
            store.upsert_text(
                "transformer_manual.md",
                "主变温度传感器正常 40°C～75°C。critical 需立即巡检冷却系统。",
            )
        print(f"  documents = {len(store.documents)}")
        print(f"  chunks    = {len(store.chunks)}")
    print(f"  bm25      = {'ready' if getattr(store, '_bm25', None) else 'empty'}")
    return store


def demo_retrieve(store, question: str) -> list[dict]:
    section("5) 召回：向量 vs BM25 vs Hybrid+Rerank")
    print(f"查询: {question}")
    print(f"query tokens: {tokenize(question)}")

    if hasattr(store, "_vector_search"):
        vector_hits = store._vector_search(question, limit=3)
    else:
        q_emb = hash_embed(question, dim=settings.embedding_dim)
        vector_hits = sorted(
            (
                {
                    "text": c.text,
                    "meta": c.meta,
                    "score": cosine(q_emb, c.embedding),
                    "channel": "vector",
                }
                for c in store.chunks
            ),
            key=lambda x: x["score"],
            reverse=True,
        )[:3]
    print("\n  [向量 Top3]")
    for h in vector_hits:
        src = h.get("meta", {}).get("source") or h.get("source")
        print(f"    {h['score']:.4f} | {src} | {h['text'][:60]}")

    if hasattr(store, "_bm25_search"):
        bm25_hits = store._bm25_search(question, limit=3)
    else:
        bm25_hits = []
        if store._bm25 is not None:
            scores = store._bm25.get_scores(tokenize(question))
            ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:3]
            for idx, score in ranked:
                c = store.chunks[idx]
                bm25_hits.append(
                    {
                        "text": c.text,
                        "meta": c.meta,
                        "score": float(score),
                        "channel": "bm25",
                    }
                )
    print("\n  [BM25 Top3]")
    for h in bm25_hits:
        src = h.get("meta", {}).get("source") or h.get("source")
        print(f"    {h['score']:.4f} | {src} | {h['text'][:60]}")

    hybrid = store.hybrid_search(question, top_k=3)
    print("\n  [Hybrid + Rerank Top3]")
    for h in hybrid:
        print(
            f"    {h['score']:.4f} | {h.get('channel')} | "
            f"{h['meta'].get('source')} | {h['text'][:60]}"
        )
    return hybrid


def demo_rerank_explain(question: str, candidates: list[dict]) -> None:
    section("6) Rerank 说明")
    reranked = simple_rerank(question, candidates, top_k=3)
    print("  简单重排 = 原分数 + 词重叠加成（生产可换 BGE Reranker）")
    for h in reranked:
        src = h.get("source") or (h.get("meta") or {}).get("source")
        print(f"    {h['score']:.4f} | {src}")


async def demo_answer(store, question: str) -> None:
    section("7) Context 组装 + 回答（含引用）")
    payload = await store.answer(question)
    print(f"backend: {payload.get('backend', '?')}")
    print("上下文(截断):")
    print((payload.get("context") or "")[:300], "...\n")
    print("默认回答:")
    print(payload.get("answer"))
    print("\n引用来源:")
    for s in payload.get("sources") or []:
        print(f"  - {s.get('source')} score={s.get('score'):.4f}")
        print(f"    snippet: {s.get('snippet')}")

    if has_api_key():
        section("8) 可选：LLM 基于检索上下文生成")
        from gridmind.llm.gateway import get_llm_gateway
        from gridmind.llm.prompts.answer import ANSWER_SYSTEM
        from gridmind.llm.providers import ChatMessage

        gateway = get_llm_gateway()
        result = await gateway.chat(
            [
                ChatMessage(role="system", content=ANSWER_SYSTEM),
                ChatMessage(
                    role="user",
                    content=(
                        f"问题：{question}\n\n检索上下文：\n{payload.get('context')}"
                    ),
                ),
            ]
        )
        print(result.content)
    else:
        section("8) 可选 LLM 生成（跳过）")
        need_key_hint()


def principle() -> None:
    section("RAG 原理")
    print(
        """
文档 → 解析/清洗 → Chunk → Embedding → 向量库
                              ↘
用户问题 → 向量召回 + BM25召回 → 合并 → Rerank → 组装 Context
                                              → LLM 生成（可引用 source）
""".strip()
    )
    print("本 demo 对应代码: gridmind.rag.{loader,splitter,embedding,retriever,pg_store,reranker}")
    print("有 DATABASE_URL → pgvector；否则 → 内存向量。")


def main() -> None:
    banner("RAG 完整链路 Demo")
    principle()
    demo_load_and_split()
    demo_embed()
    store = build_store()

    question = "告警数量是如何定义的？critical 怎么处理？"
    hits = demo_retrieve(store, question)
    # hybrid 结果结构带 meta；转成 rerank 可用的扁平候选再讲一遍
    flat = [
        {
            "text": h["text"],
            "source": h["meta"].get("source"),
            "score": h["score"],
            "meta": h["meta"],
        }
        for h in hits
    ]
    demo_rerank_explain(question, flat)
    asyncio.run(demo_answer(store, question))

    print("\n要点：RAG ≠ 只有向量库；Hybrid + Rerank + 引用 才接近企业用法。")
    print(f"种子目录: {Path(settings.knowledge_dir)}")


if __name__ == "__main__":
    main()
