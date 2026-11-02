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


def test_query_nl2sql():
    resp = client.post(
        "/api/v1/query",
        json={"question": "查询当前在线设备数量", "use_llm": False},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "sql" in body
    assert isinstance(body["rows"], list)


def test_knowledge_documents():
    resp = client.get("/api/v1/knowledge/documents")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
