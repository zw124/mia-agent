from typing import Any

from fastapi.testclient import TestClient

from mia.main import app, get_convex, get_settings
from mia.settings import Settings


class FailingConvex:
    async def record_inbound_message(self, *_args: Any, **_kwargs: Any) -> bool:
        raise RuntimeError("convex unauthorized")


class HandlerStub:
    async def __call__(self, state: dict[str, Any], *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {**state, "reply": "handled without persistence", "route": "fast_reply"}


def install_overrides(convex: object) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        OPENAI_API_KEY="key",
        OPENAI_BASE_URL="https://llm.test/v1",
        MODEL_NAME="model",
        MIA_INTERNAL_SECRET="internal",
        CONVEX_SITE_URL="https://convex.test",
    )
    app.dependency_overrides[get_convex] = lambda: convex


def test_web_chat_requires_convex_persistence() -> None:
    install_overrides(FailingConvex())
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post("/web/chat", json={"message": "What is the time"})

    assert response.status_code == 503
    body = response.json()
    assert "Convex persistence unavailable" in body["detail"]
    app.dependency_overrides.clear()


def test_web_chat_does_not_run_agent_when_convex_is_unavailable(monkeypatch) -> None:
    from mia import main

    install_overrides(FailingConvex())
    monkeypatch.setattr(main, "handle_message", HandlerStub())
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post("/web/chat", json={"message": "hello"})

    assert response.status_code == 503
    body = response.json()
    assert "Convex persistence unavailable" in body["detail"]
    app.dependency_overrides.clear()
