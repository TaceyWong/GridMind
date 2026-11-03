from fastapi.testclient import TestClient

from gridmind.main import app


client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["message"] == "OK"


def test_chat_degraded():
    resp = client.post("/api/v1/chat", json={"message": "告警等级是如何定义的？"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["message"]
    assert body["route"] in {"rag", "nl2sql", "mcp", "hybrid"}


def test_query_nl2sql_requires_llm():
    resp = client.post(
        "/api/v1/query",
        json={"question": "查询当前在线设备数量"},
    )
    # 无 LLM_API_KEY 时问数必须失败，不再回退模板
    assert resp.status_code == 503
    assert "LLM" in resp.json()["detail"]


def test_knowledge_documents():
    resp = client.get("/api/v1/knowledge/documents")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
