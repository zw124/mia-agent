from typing import Any

from fastapi.testclient import TestClient

from mia.main import app, get_convex, get_sendblue, get_settings
from mia.settings import Settings


class ConvexStub:
    def __init__(self, accepted: bool = True):
        self.accepted = accepted
        self.started: list[dict[str, Any]] = []
        self.completed: list[dict[str, Any]] = []
        self.failed: list[dict[str, Any]] = []
        self.outbound: list[dict[str, Any]] = []

    async def record_webhook_event(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    async def record_inbound_message(self, *_args: Any, **_kwargs: Any) -> bool:
        return self.accepted

    async def relevant_memories(self, *_args: Any, **_kwargs: Any) -> list[dict[str, Any]]:
        return []

    async def approve_pending_action(self, **_kwargs: Any) -> dict[str, Any] | None:
        return None

    async def complete_pending_action(self, **_kwargs: Any) -> None:
        return None

    async def fail_pending_action(self, **_kwargs: Any) -> None:
        return None

    async def start_agent_run(self, **kwargs: Any) -> None:
        self.started.append(kwargs)

    async def complete_agent_run(self, **kwargs: Any) -> None:
        self.completed.append(kwargs)

    async def fail_agent_run(self, **kwargs: Any) -> None:
        self.failed.append(kwargs)

    async def record_outbound_message(self, *_args: Any, **kwargs: Any) -> None:
        self.outbound.append(kwargs)

    async def log_thought(self, **_kwargs: Any) -> None:
        return None


class SendBlueStub:
    def __init__(self, *, fail: bool = False) -> None:
        self.sent: list[dict[str, str]] = []
        self.typing: list[str] = []
        self.fail = fail

    async def send_typing_indicator(self, **kwargs: str) -> dict[str, str]:
        self.typing.append(kwargs["number"])
        return {"number": kwargs["number"], "status": "SENT"}

    async def send_message(self, **kwargs: str) -> dict[str, str]:
        if self.fail:
            raise RuntimeError("sendblue rejected credentials")
        self.sent.append(kwargs)
        return {"message_handle": "out-1", "status": "sent"}


class GraphStub:
    async def ainvoke(self, state: dict[str, Any]) -> dict[str, Any]:
        return {**state, "reply": "handled", "route": "direct_reply"}


def payload() -> dict[str, Any]:
    return {
        "content": "hello",
        "is_outbound": False,
        "message_handle": "in-1",
        "from_number": "+15551110000",
        "number": "+15551110000",
        "participants": [],
    }


def install_overrides(convex: ConvexStub, sendblue: SendBlueStub) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        OPENAI_API_KEY="key",
        OPENAI_BASE_URL="https://llm.test/v1",
        MODEL_NAME="model",
        SENDBLUE_WEBHOOK_SECRET="webhook-secret",
        MIA_INTERNAL_SECRET="internal",
        CONVEX_SITE_URL="https://convex.test",
    )
    app.dependency_overrides[get_convex] = lambda: convex
    app.dependency_overrides[get_sendblue] = lambda: sendblue


def test_sendblue_webhook_rejects_invalid_secret() -> None:
    install_overrides(ConvexStub(), SendBlueStub())
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post(
        "/webhooks/sendblue/receive",
        json=payload(),
        headers={"sb-signing-secret": "wrong"},
    )

    assert response.status_code == 401
    app.dependency_overrides.clear()


def test_sendblue_webhook_dedupes_before_agent_execution(monkeypatch) -> None:
    convex = ConvexStub(accepted=False)
    sendblue = SendBlueStub()
    install_overrides(convex, sendblue)
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post(
        "/webhooks/sendblue/receive",
        json=payload(),
        headers={"sb-signing-secret": "webhook-secret"},
    )

    assert response.status_code == 200
    assert response.json()["deduped"] is True
    assert sendblue.sent == []
    assert sendblue.typing == []
    assert convex.started == []
    app.dependency_overrides.clear()


def test_sendblue_webhook_runs_agent_and_sends_reply(monkeypatch) -> None:
    from mia import main

    convex = ConvexStub(accepted=True)
    sendblue = SendBlueStub()
    install_overrides(convex, sendblue)
    monkeypatch.setattr(main, "build_router_graph", lambda *_args, **_kwargs: GraphStub())
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post(
        "/webhooks/sendblue/receive",
        json=payload(),
        headers={"sb-signing-secret": "webhook-secret"},
    )

    assert response.status_code == 200
    assert response.json()["reply"] == "handled"
    assert sendblue.typing == ["+15551110000"]
    assert sendblue.sent == [{"number": "+15551110000", "content": "handled"}]
    assert len(convex.started) == 1
    assert convex.completed[0]["active_agent"] == "direct_reply"
    app.dependency_overrides.clear()


def test_sendblue_webhook_marks_run_failed_when_outbound_send_fails(monkeypatch) -> None:
    from mia import main

    convex = ConvexStub(accepted=True)
    sendblue = SendBlueStub(fail=True)
    install_overrides(convex, sendblue)
    monkeypatch.setattr(main, "build_router_graph", lambda *_args, **_kwargs: GraphStub())
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post(
        "/webhooks/sendblue/receive",
        json=payload(),
        headers={"sb-signing-secret": "webhook-secret"},
    )

    assert response.status_code == 500
    assert len(convex.failed) == 1
    assert convex.failed[0]["error"] == "sendblue rejected credentials"
    app.dependency_overrides.clear()
