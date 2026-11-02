"""学习示例 6：LlamaIndex

目标：
- Document / VectorStoreIndex（内存）
- 检索 as_retriever
- 无云 Embedding 时用本地简单向量（不用外呼）

运行::

    uv run python -m gridmind.demo llamaindex
"""

from __future__ import annotations

from gridmind.demo._common import banner


def main() -> None:
    banner("6) LlamaIndex")

    from llama_index.core import Document, Settings, VectorStoreIndex
    from llama_index.core.embeddings import BaseEmbedding
    from llama_index.core.schema import TextNode

    class HashEmbedding(BaseEmbedding):
        """学习用本地 embedding，避免强依赖云 API。"""

        def _embed(self, text: str) -> list[float]:
            # 极简可重复向量：字符桶计数归一化
            vec = [0.0] * 32
            for ch in text.lower():
                vec[ord(ch) % 32] += 1.0
            norm = sum(v * v for v in vec) ** 0.5 or 1.0
            return [v / norm for v in vec]

        def _get_query_embedding(self, query: str) -> list[float]:
            return self._embed(query)

        def _get_text_embedding(self, text: str) -> list[float]:
            return self._embed(text)

        async def _aget_query_embedding(self, query: str) -> list[float]:
            return self._embed(query)

        async def _aget_text_embedding(self, text: str) -> list[float]:
            return self._embed(text)

    Settings.embed_model = HashEmbedding()
    # 本示例只做检索，不强制配置 LLM
    Settings.llm = None

    docs = [
        Document(text="告警数量口径：按 alarm_id 去重统计告警事件数。"),
        Document(text="主变温度传感器正常运行温度通常在 40°C～75°C。"),
        Document(text="MCP 用于把 IoT 工具以标准协议暴露给 Agent。"),
    ]
    index = VectorStoreIndex.from_documents(docs)
    retriever = index.as_retriever(similarity_top_k=2)
    query = "告警数量怎么统计？"
    nodes = retriever.retrieve(query)

    print(f"查询: {query}")
    for i, node in enumerate(nodes, 1):
        text = node.get_content() if hasattr(node, "get_content") else str(node)
        score = getattr(node, "score", None)
        print(f"  hit{i} score={score}: {text}")

    # 也展示 TextNode 切分概念
    node = TextNode(text=docs[0].text, id_="n1")
    print(f"\nTextNode id={node.node_id} chars={len(node.text)}")
    print("要点：LlamaIndex 擅长文档索引与检索；可与 LangGraph 的 rag 节点组合。")


if __name__ == "__main__":
    main()
