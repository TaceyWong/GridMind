"""学习示例：LlamaIndex Agent + pgvector + BGE

分两段语义：
1) 入库：Document → SentenceSplitter → BGE embed → vector_store.add
2) 查询：from_vector_store → Retriever Tool → ReActAgent

前置：DATABASE_URL；LLM_BASE_URL / LLM_API_KEY / LLM_MODEL

运行::

    uv run python -m gridmind.demo llamaindex
"""

from __future__ import annotations

import asyncio
import os
from urllib.parse import unquote

from sqlalchemy.engine import make_url

from gridmind.core.config import settings
from gridmind.demo._common import (
    api_key,
    banner,
    base_url,
    has_api_key,
    model_name,
    need_key_hint,
)

os.environ.setdefault("HTTP_PROXY", os.getenv("HTTP_PROXY", "http://127.0.0.1:7890"))
os.environ.setdefault("HTTPS_PROXY", os.getenv("HTTPS_PROXY", "http://127.0.0.1:7890"))

BGE_DIMS = {
    "BAAI/bge-small-zh-v1.5": 512,
    "BAAI/bge-base-zh-v1.5": 768,
    "BAAI/bge-large-zh-v1.5": 1024,
}


def _require_database_url() -> str:
    url = settings.database_url.strip()
    if not url:
        raise SystemExit(
            "未配置 DATABASE_URL。请在 .env 中设置 Postgres（含 pgvector），例如：\n"
            "  DATABASE_URL=postgresql://postgres:icosmos@127.0.0.1:5432/gridmind"
        )
    return url


def _bge_embed_dim(name: str) -> int:
    if name in BGE_DIMS:
        return BGE_DIMS[name]
    env_dim = os.getenv("BGE_EMBED_DIM", "").strip()
    return int(env_dim) if env_dim.isdigit() else 512


def _ping_postgres(database_url: str) -> None:
    import psycopg2

    url = make_url(database_url)
    try:
        conn = psycopg2.connect(
            host=url.host or "127.0.0.1",
            port=url.port or 5432,
            user=url.username or "postgres",
            password=unquote(url.password) if url.password else "",
            dbname=url.database or "postgres",
            connect_timeout=5,
        )
        conn.close()
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(
            f"无法连接 Postgres（pgvector）：{exc}\n"
            "请先启动带 pgvector 的容器。"
        ) from exc


def _pg_vector_store(database_url: str, embed_dim: int, table_name: str):
    from llama_index.vector_stores.postgres import PGVectorStore

    url = make_url(database_url)
    return PGVectorStore.from_params(
        database=url.database or "postgres",
        host=url.host or "127.0.0.1",
        port=str(url.port or 5432),
        user=url.username or "postgres",
        password=unquote(url.password) if url.password else "",
        table_name=table_name,
        embed_dim=embed_dim,
        perform_setup=True,
        use_jsonb=True,
    )


def _build_llm():
    from llama_index.llms.openai import OpenAI

    base = base_url()
    is_local = any(h in base for h in ("127.0.0.1", "localhost"))
    key = api_key()
    if not key:
        if is_local:
            key = "sk-local"
        else:
            need_key_hint()
            raise SystemExit(
                "Agent 需要 LLM。请配置 LLM_API_KEY，或把 LLM_BASE_URL 指到本地兼容接口。"
            )

    llm = OpenAI(
        model=model_name(),
        api_key=key,
        api_base=base,
        temperature=0,
        request_timeout=120.0,
    )
    print(f"LLM          = {model_name()} @ {base}")
    return llm


def ingest_to_pgvector(vector_store, docs) -> int:
    """只负责入库：切分 → 嵌入 → add，不创建查询用 Index。"""
    from llama_index.core import Settings
    from llama_index.core.node_parser import SentenceSplitter

    print("\n--- 1) 入库：SentenceSplitter → BGE → vector_store.add ---")
    splitter = SentenceSplitter(chunk_size=128, chunk_overlap=20)
    nodes = splitter.get_nodes_from_documents(docs)
    print(f"documents = {len(docs)} → nodes = {len(nodes)}")
    for i, node in enumerate(nodes):
        src = (node.metadata or {}).get("source", "?")
        preview = node.get_content().replace("\n", " ")[:60]
        print(f"  chunk[{i}] source={src}: {preview}...")

    embed_model = Settings.embed_model
    texts = [n.get_content(metadata_mode="embed") for n in nodes]
    embeddings = embed_model.get_text_embedding_batch(texts, show_progress=True)
    for node, emb in zip(nodes, embeddings, strict=True):
        node.embedding = emb

    ids = vector_store.add(nodes)
    print(f"已写入 pgvector：{len(ids)} 条（仅入库，未建 Query Index）")
    return len(ids)


def open_retriever(vector_store, top_k: int = 2):
    """查询侧：挂已有表，再 as_retriever。"""
    from llama_index.core import VectorStoreIndex

    print("\n--- 2) 查询：from_vector_store → retriever ---")
    index = VectorStoreIndex.from_vector_store(vector_store)
    return index.as_retriever(similarity_top_k=top_k)


def main() -> None:
    banner("LlamaIndex：入库 / Agent 查询分离")

    from llama_index.core import Document, Settings
    from llama_index.core.agent.workflow import ReActAgent
    from llama_index.core.tools import FunctionTool
    from llama_index.embeddings.huggingface import HuggingFaceEmbedding

    database_url = _require_database_url()
    _ping_postgres(database_url)

    bge_name = settings.bge_model_name
    embed_dim = _bge_embed_dim(bge_name)
    table_name = "llamaindex_bge"

    print(f"BGE model    = {bge_name}")
    print(f"embed_dim    = {embed_dim}")
    print(f"DATABASE_URL → {make_url(database_url).render_as_string(hide_password=True)}")
    print(f"table        = data_{table_name}")

    Settings.embed_model = HuggingFaceEmbedding(model_name=bge_name)
    Settings.llm = _build_llm()

    vector_store = _pg_vector_store(database_url, embed_dim, table_name)
    try:
        vector_store.clear()
        print("已清空旧索引行")
    except Exception as exc:  # noqa: BLE001
        print(f"clear 跳过: {exc}")

    # 稍长一点，方便看出 SentenceSplitter 切出多段
    docs = [
        Document(
            text=(
                "告警数量口径：按 alarm_id 去重统计告警事件数。"
                "注意：不是未处理告警数，也不是告警设备数。"
                "status=open 表示未处理；acked 表示已确认。"
            ),
            metadata={"source": "alarm"},
        ),
        Document(
            text=(
                "主变温度传感器用于监测变压器绕组与油面温度。"
                "正常运行温度通常在 40°C～75°C。"
                "critical 表示超过保护阈值，需立即巡检冷却系统。"
            ),
            metadata={"source": "transformer"},
        ),
        Document(
            text="MCP 用于把 IoT 工具以标准协议暴露给 Agent。可通过工具查询设备与告警。",
            metadata={"source": "mcp"},
        ),
    ]

    ingest_to_pgvector(vector_store, docs)
    retriever = open_retriever(vector_store, top_k=3)

    def knowledge_search(query: str) -> str:
        """检索电网知识库，返回与问题相关的原文片段。"""
        nodes = retriever.retrieve(query)
        if not nodes:
            return "知识库未命中相关内容。"
        chunks: list[str] = []
        for n in nodes:
            src = (n.metadata or {}).get("source", "?")
            score = getattr(n, "score", None)
            chunks.append(f"[source={src} score={score}] {n.get_content()}")
        return "\n".join(chunks)

    print("\n--- 3) Agent：ReAct + knowledge_search Tool ---")
    search_tool = FunctionTool.from_defaults(fn=knowledge_search)
    agent = ReActAgent(
        name="GridKnowledgeAgent",
        description="回答电网口径与设备知识问题",
        system_prompt=(
            "你是电网知识助手。涉及口径、温度、MCP 等事实时，"
            "必须先调用 knowledge_search 工具，再基于检索结果用中文简要回答；"
            "不要编造检索结果中没有的信息。"
        ),
        tools=[search_tool],
        llm=Settings.llm,
        verbose=True,
        timeout=180.0,
    )

    question = "告警数量怎么统计？主变正常温度大概多少？"
    print(f"Q: {question}\n")

    async def _run() -> None:
        result = await agent.run(user_msg=question)
        print("\n--- Agent 最终回答 ---")
        print(str(result))

    asyncio.run(_run())
    print(
        "\n要点：入库用 SentenceSplitter + vector_store.add；"
        "查询用 from_vector_store；Agent 只消费检索 Tool。"
    )
    if not has_api_key():
        print("提示：当前可能在用本地兼容接口或占位 Key。")


if __name__ == "__main__":
    main()
