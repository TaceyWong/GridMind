from fastapi import APIRouter, File, UploadFile

from gridmind.llm.gateway import get_llm_gateway
from gridmind.llm.prompts.answer import ANSWER_SYSTEM
from gridmind.llm.providers import ChatMessage
from gridmind.rag.retriever import get_knowledge_store
from gridmind.schemas.knowledge import (
    KnowledgeChatRequest,
    KnowledgeChatResponse,
    KnowledgeDocument,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
)

router = APIRouter(prefix="/knowledge", tags=["Knowledge"])


@router.post("/upload", description="Upload a text/markdown knowledge document.")
async def upload(file: UploadFile = File(...)) -> dict[str, str]:
    content = (await file.read()).decode("utf-8", errors="ignore")
    doc_id = get_knowledge_store().upsert_text(file.filename or "upload.txt", content)
    return {"doc_id": doc_id, "name": file.filename or "upload.txt"}


@router.post("/search", description="Hybrid search over knowledge base.")
async def search(request: KnowledgeSearchRequest) -> KnowledgeSearchResponse:
    hits = get_knowledge_store().hybrid_search(request.query, top_k=request.top_k)
    return KnowledgeSearchResponse(hits=hits)


@router.post("/chat", description="RAG chat with citations.")
async def knowledge_chat(request: KnowledgeChatRequest) -> KnowledgeChatResponse:
    store = get_knowledge_store()
    payload = await store.answer(request.message)
    gateway = get_llm_gateway()
    answer = payload["answer"]
    if gateway.default_provider != "mock" and payload.get("context"):
        result = await gateway.chat(
            [
                ChatMessage(role="system", content=ANSWER_SYSTEM),
                ChatMessage(
                    role="user",
                    content=f"问题：{request.message}\n\n上下文：\n{payload['context']}",
                ),
            ],
            provider=request.provider,
            model=request.model,
        )
        answer = result.content
    return KnowledgeChatResponse(answer=answer, sources=payload.get("sources", []))


@router.get("/documents", description="List ingested documents.")
async def documents() -> list[KnowledgeDocument]:
    docs = get_knowledge_store().list_documents()
    return [KnowledgeDocument(**d) for d in docs]
