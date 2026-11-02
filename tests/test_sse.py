from fastapi.testclient import TestClient

from gridmind.main import app


client = TestClient(app)


def test_chat_stream_sse():
    with client.stream(
        "POST",
        "/api/v1/chat/stream",
        json={"message": "设备 DEV-001 当前状态是什么？", "session_id": "sse-test"},
    ) as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
        body = "".join(resp.iter_text())

    assert "event: status" in body
    assert "event: token" in body or "event: done" in body
    assert "event: done" in body
