from __future__ import annotations

import tempfile

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


def _configure(monkeypatch) -> None:
    monkeypatch.setenv("WEB_ACCESS_TOKEN", "test-token")
    monkeypatch.setenv("MOCK_AI", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("BIRTH_CALENDAR", "solar")
    monkeypatch.setenv("BIRTH_DATE", "1990-01-01")
    monkeypatch.setenv("BIRTH_TIME", "08:00")
    monkeypatch.setenv("BIRTH_PLACE", "北京")
    monkeypatch.setenv("BIRTH_GENDER", "male")
    monkeypatch.setenv("DAILY_PUSH_CRON", "0 8 * * *")
    monkeypatch.setenv("DATA_DIR", tempfile.mkdtemp(prefix="fortune-tests-"))
    get_settings.cache_clear()


def test_health(monkeypatch) -> None:
    _configure(monkeypatch)
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ask_auth(monkeypatch) -> None:
    _configure(monkeypatch)
    with TestClient(app) as client:
        response = client.post("/api/ask", json={"question": "我今天适合谈合作吗？"})
    assert response.status_code == 401


def test_ask_success(monkeypatch) -> None:
    _configure(monkeypatch)
    with TestClient(app) as client:
        response = client.post(
            "/api/ask",
            json={"question": "我今天适合谈合作吗？"},
            headers={"Authorization": "Bearer test-token"},
        )
    assert response.status_code == 200
    data = response.json()
    assert "仅供个人参考" in data["answer"]
    assert data["date"]


def test_push_now_success_with_mocked_dingtalk(monkeypatch) -> None:
    _configure(monkeypatch)
    monkeypatch.setenv("DINGTALK_WEBHOOK", "https://example.com/robot?access_token=test")
    get_settings.cache_clear()

    import app.scheduler as scheduler_module

    monkeypatch.setattr(scheduler_module, "send_markdown", lambda *args, **kwargs: {"errcode": 0})
    with TestClient(app) as client:
        response = client.post("/api/push-now", headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 200
    assert response.json()["status"] == "sent"


def test_fortune_page_hides_mismatched_profile(monkeypatch) -> None:
    _configure(monkeypatch)
    from app.storage import save_last_fortune

    settings = get_settings()
    save_last_fortune(settings, {"date": "2026-07-17", "content": "OLD_PROFILE_RESULT", "context": {}})

    monkeypatch.setenv("BIRTH_DATE", "1991-02-02")
    get_settings.cache_clear()
    with TestClient(app) as client:
        response = client.get("/fortune?token=test-token")
    assert response.status_code == 200
    assert "OLD_PROFILE_RESULT" not in response.text
    assert "lastContent" in response.text


def test_extract_openai_text_accepts_plain_string_response() -> None:
    from app.ai import _extract_openai_text

    assert _extract_openai_text("直接返回的文本") == "直接返回的文本"


def test_extract_openai_text_accepts_dict_response() -> None:
    from app.ai import _extract_openai_text

    response = {"choices": [{"message": {"content": "字典格式回答"}}]}
    assert _extract_openai_text(response) == "字典格式回答"


def test_extract_openai_text_accepts_object_response() -> None:
    from app.ai import _extract_openai_text

    class Message:
        content = "对象格式回答"

    class Choice:
        message = Message()

    class Response:
        choices = [Choice()]

    assert _extract_openai_text(Response()) == "对象格式回答"


def test_extract_openai_text_accepts_sse_stream_string() -> None:
    from app.ai import _extract_openai_text

    response = '\n'.join([
        'data: {"choices":[{"delta":{"content":"第一段"}}]}',
        'data: {"choices":[{"delta":{"content":"第二段"}}]}',
        'data: [DONE]',
    ])
    assert _extract_openai_text(response) == "第一段第二段"


def test_extract_openai_text_rejects_empty_sse_stream_string() -> None:
    import pytest

    from app.ai import AIResponseError, _extract_openai_text

    response = '\n'.join([
        'data: {"choices":[],"usage":{"completion_tokens":0}}',
        'data: [DONE]',
    ])
    with pytest.raises(AIResponseError):
        _extract_openai_text(response)


def test_fortune_page_declares_ios_icon(monkeypatch) -> None:
    _configure(monkeypatch)
    with TestClient(app) as client:
        response = client.get("/fortune?token=test-token")
    assert response.status_code == 200
    assert 'rel="apple-touch-icon"' in response.text
    assert '/static/icons/apple-touch-icon.png' in response.text
    assert '/manifest.webmanifest?token=test-token' in response.text


def test_manifest_and_icon(monkeypatch) -> None:
    _configure(monkeypatch)
    with TestClient(app) as client:
        manifest = client.get("/manifest.webmanifest?token=test-token")
        icon = client.get("/static/icons/apple-touch-icon.png")
    assert manifest.status_code == 200
    assert manifest.headers["content-type"].startswith("application/manifest+json")
    data = manifest.json()
    assert data["short_name"] == "\u8fd0\u52bf"
    assert data["start_url"] == "/fortune?token=test-token"
    assert any(item["src"] == "/static/icons/icon-512.png" for item in data["icons"])
    assert icon.status_code == 200
    assert icon.headers["content-type"] == "image/png"
