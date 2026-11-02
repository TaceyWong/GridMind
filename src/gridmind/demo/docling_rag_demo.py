"""学习示例：Docling Server + LlamaIndex + BGE + LLM 完整问答

链路：
1. Docling Serve（Docker HTTP）解析文档 → Markdown
2. LlamaIndex 切分 / 建索引
3. BGE（本地 HuggingFace）做 embedding
4. 检索 + LLM 生成答案（OpenAI 兼容；无 Key 则检索摘要）

前置：
- 本机已 `uv sync`（含 llama-index embeddings/llms，不含 docling 库）
- 单独启动 Docling Serve，例如::

    docker run -p 5001:5001 -e DOCLING_SERVE_ENABLE_UI=1 \\
      quay.io/docling-project/docling-serve-cpu

  或::

    docker compose -f docker/docker-compose.yml up -d docling

运行::

    uv run python -m gridmind.demo docling_rag
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx

from gridmind.core.config import settings
from gridmind.demo._common import api_key, banner, base_url, has_api_key, model_name, need_key_hint

# 首次拉 BGE 建议走本机代理（可按需改）
os.environ.setdefault("HTTP_PROXY", os.getenv("HTTP_PROXY", "http://127.0.0.1:7890"))
os.environ.setdefault("HTTPS_PROXY", os.getenv("HTTPS_PROXY", "http://127.0.0.1:7890"))


def section(title: str) -> None:
    print(f"\n--- {title} ---")


def docling_health(url: str) -> bool:
    try:
        r = httpx.get(f"{url.rstrip('/')}/health", timeout=5.0)
        return r.status_code < 500
    except httpx.HTTPError:
        return False


def convert_via_docling(path: Path, serve_url: str) -> str:
    """调用 docling-serve `/v1/convert/file`，返回 markdown 文本。"""
    endpoint = f"{serve_url.rstrip('/')}/v1/convert/file"
    headers = {}
    if settings.docling_serve_api_key:
        headers["X-Api-Key"] = settings.docling_serve_api_key

    with path.open("rb") as f:
        files = {"files": (path.name, f, "application/octet-stream")}
        data = {
            "to_formats": "md",
            "do_ocr": "false",
            "table_mode": "fast",
            "abort_on_error": "false",
        }
        resp = httpx.post(endpoint, files=files, data=data, headers=headers, timeout=180.0)
    resp.raise_for_status()
    payload = resp.json()

    # 兼容常见响应形状
    if isinstance(payload, dict):
        doc = payload.get("document") or payload.get("data") or payload
        if isinstance(doc, dict):
            for key in ("md_content", "markdown", "text_content", "text"):
                if doc.get(key):
                    return str(doc[key])
        docs = payload.get("documents")
        if isinstance(docs, list) and docs:
            first = docs[0]
            if isinstance(first, dict):
                for key in ("md_content", "markdown", "text_content", "text"):
                    if first.get(key):
                        return str(first[key])
        # 有的版本把内容放在 document.md_content 嵌套里
        nested = payload.get("document")
        if isinstance(nested, dict) and nested.get("md_content"):
            return str(nested["md_content"])

    raise RuntimeError(f"无法从 Docling 响应解析 markdown: {json.dumps(payload)[:400]}")


def load_docs_with_docling_or_fallback(serve_url: str) -> list[tuple[str, str]]:
    """返回 [(source_name, markdown_text), ...]。"""
    knowledge = Path(settings.knowledge_dir)
    paths = sorted(knowledge.glob("*.md")) + sorted(knowledge.glob("*.txt"))
    if not paths:
        raise FileNotFoundError(f"知识目录为空: {knowledge}")

    out: list[tuple[str, str]] = []
    server_ok = docling_health(serve_url)
    if server_ok:
        print(f"Docling Serve 可用: {serve_url}")
    else:
        print(f"Docling Serve 不可达: {serve_url}")
        print("将直接读取本地 md/txt（请先 docker 启动 docling-serve-cpu）。")

    for path in paths:
        if server_ok:
            try:
                md = convert_via_docling(path, serve_url)
                print(f"  [docling] {path.name} → {len(md)} chars")
                out.append((path.name, md))
                continue
            except Exception as exc:  # noqa: BLE001 — demo 容错展示
                print(f"  [docling失败→本地] {path.name}: {exc}")
        text = path.read_text(encoding="utf-8")
        print(f"  [local] {path.name} → {len(text)} chars")
        out.append((path.name, text))
    return out


def build_query_engine(docs: list[tuple[str, str]]):
    from llama_index.core import Document, Settings, VectorStoreIndex
    from llama_index.core.node_parser import SentenceSplitter
    from llama_index.embeddings.huggingface import HuggingFaceEmbedding

    section("2) BGE Embedding（CPU）")
    model_id = settings.bge_model_name
    print(f"model = {model_id}")
    embed_model = HuggingFaceEmbedding(model_name=model_id)
    Settings.embed_model = embed_model

    section("3) LlamaIndex 切分 + 建索引")
    splitter = SentenceSplitter(chunk_size=256, chunk_overlap=40)
    Settings.node_parser = splitter

    documents = [
        Document(text=text, metadata={"source": name}) for name, text in docs
    ]
    index = VectorStoreIndex.from_documents(documents)
    print(f"documents = {len(documents)}")

    section("4) 配置 LLM")
    if has_api_key():
        from llama_index.llms.openai import OpenAI

        llm = OpenAI(
            model=model_name(),
            api_key=api_key(),
            api_base=base_url(),
            temperature=0.1,
        )
        Settings.llm = llm
        print(f"LLM = {model_name()} @ {base_url()}")
        return index.as_query_engine(similarity_top_k=3, response_mode="compact")

    Settings.llm = None
    need_key_hint()
    print("无 Key：仅演示检索，不调用 LLM。")
    return index.as_retriever(similarity_top_k=3)


def run_qa(engine_or_retriever, question: str) -> None:
    section("5) 问答")
    print(f"Q: {question}")

    # retriever 没有 query，有 retrieve
    if hasattr(engine_or_retriever, "retrieve") and not hasattr(engine_or_retriever, "query"):
        nodes = engine_or_retriever.retrieve(question)
        print("检索命中:")
        for i, node in enumerate(nodes, 1):
            src = (node.metadata or {}).get("source", "?")
            score = getattr(node, "score", None)
            text = node.get_content()
            print(f"  [{i}] score={score} source={src}")
            print(f"      {text[:160].replace(chr(10), ' ')}...")
        if nodes:
            print("\n降级答案（无 LLM）:")
            print(nodes[0].get_content()[:400])
        return

    response = engine_or_retriever.query(question)
    print("A:", str(response).strip())
    source_nodes = getattr(response, "source_nodes", None) or []
    if source_nodes:
        print("\n引用:")
        for i, node in enumerate(source_nodes, 1):
            src = (node.metadata or {}).get("source", "?")
            print(f"  [{i}] {src} score={getattr(node, 'score', None)}")


def main() -> None:
    banner("Docling Serve + LlamaIndex + BGE + LLM")
    print(
        """
文档 → Docling Server(HTTP) → Markdown
     → LlamaIndex 切分 → BGE 向量索引
     → 检索 → LLM 回答
""".strip()
    )

    serve = settings.docling_serve_url
    section("1) Docling 解析")
    docs = load_docs_with_docling_or_fallback(serve)
    engine = build_query_engine(docs)
    run_qa(engine, "告警数量是如何定义的？critical 告警怎么处理？")
    print("\n要点：docling 只跑在 Docker；应用侧用 httpx 调 API，不 pip install docling。")


if __name__ == "__main__":
    main()
