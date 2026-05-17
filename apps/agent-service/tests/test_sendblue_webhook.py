from typing import Any

from fastapi.testclient import TestClient

from mia.main import app, get_convex, get_sendblue, get_settings, get_telegram
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


class TelegramStub:
    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []

    async def send_message(self, **kwargs: str) -> dict[str, str]:
        self.sent.append(kwargs)
        return {"ok": True, "result": {"message_id": 10}}


class HandlerStub:
    async def __call__(self, state: dict[str, Any], *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {**state, "reply": "handled", "route": "fast_reply"}


def payload() -> dict[str, Any]:
    return {
        "content": "hello",
        "is_outbound": False,
        "message_handle": "in-1",
        "from_number": "+15551110000",
        "number": "+15551110000",
        "participants": [],
    }


def voice_payload() -> dict[str, Any]:
    data = payload()
    data.update(
        {
            "content": "",
            "message_handle": "voice-1",
            "media_url": "https://media.test/voice.m4a",
            "message_type": "audio",
        }
    )
    return data


def install_overrides(
    convex: ConvexStub,
    sendblue: SendBlueStub,
    telegram: TelegramStub | None = None,
) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        OPENAI_API_KEY="key",
        OPENAI_BASE_URL="https://llm.test/v1",
        MODEL_NAME="model",
        SENDBLUE_WEBHOOK_SECRET="webhook-secret",
        MIA_INTERNAL_SECRET="internal",
        CONVEX_SITE_URL="https://convex.test",
        TELEGRAM_BOT_TOKEN="tg-token",
        TELEGRAM_WEBHOOK_SECRET="telegram-secret",
        TELEGRAM_OWNER_CHAT_ID="123",
        TELEGRAM_ALLOWED_CHAT_IDS="123",
    )
    app.dependency_overrides[get_convex] = lambda: convex
    app.dependency_overrides[get_sendblue] = lambda: sendblue
    if telegram is not None:
        app.dependency_overrides[get_telegram] = lambda: telegram


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
    monkeypatch.setattr(main, "handle_message", HandlerStub())
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
    assert convex.completed[0]["active_agent"] == "fast_reply"
    app.dependency_overrides.clear()


def test_sendblue_webhook_marks_run_failed_when_outbound_send_fails(monkeypatch) -> None:
    from mia import main

    convex = ConvexStub(accepted=True)
    sendblue = SendBlueStub(fail=True)
    install_overrides(convex, sendblue)
    monkeypatch.setattr(main, "handle_message", HandlerStub())
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


def test_sendblue_webhook_exposes_progress_callback(monkeypatch) -> None:
    from mia import main

    class ProgressHandler:
        async def __call__(self, state: dict[str, Any], *_args: Any, **_kwargs: Any) -> dict[str, Any]:
            await state["progress_callback"]("我在看任务边界。")
            return {**state, "reply": "handled", "route": "coding_orchestra"}

    convex = ConvexStub(accepted=True)
    sendblue = SendBlueStub()
    install_overrides(convex, sendblue)
    monkeypatch.setattr(main, "handle_message", ProgressHandler())
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post(
        "/webhooks/sendblue/receive",
        json=payload(),
        headers={"sb-signing-secret": "webhook-secret"},
    )

    assert response.status_code == 200
    assert sendblue.sent == [
        {"number": "+15551110000", "content": "我在看任务边界。"},
        {"number": "+15551110000", "content": "handled"},
    ]
    app.dependency_overrides.clear()


def test_sendblue_webhook_transcribes_voice_message(monkeypatch) -> None:
    from mia import main

    class TranscriptHandler:
        async def __call__(self, state: dict[str, Any], *_args: Any, **_kwargs: Any) -> dict[str, Any]:
            assert state["message"] == "帮我看一下这个项目"
            return {**state, "reply": "voice handled", "route": "fast_reply"}

    async def fake_transcribe(*_args: Any, **_kwargs: Any) -> str:
        return "帮我看一下这个项目"

    convex = ConvexStub(accepted=True)
    sendblue = SendBlueStub()
    install_overrides(convex, sendblue)
    monkeypatch.setattr(main, "handle_message", TranscriptHandler())
    monkeypatch.setattr(main, "transcribe_audio_payload", fake_transcribe)
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post(
        "/webhooks/sendblue/receive",
        json=voice_payload(),
        headers={"sb-signing-secret": "webhook-secret"},
    )

    assert response.status_code == 200
    assert response.json()["reply"] == "voice handled"
    assert sendblue.sent == [
        {"number": "+15551110000", "content": "已收到语音，我听到的是：帮我看一下这个项目"},
        {"number": "+15551110000", "content": "voice handled"},
    ]
    app.dependency_overrides.clear()


def telegram_payload(text: str = "hello", chat_id: int = 123) -> dict[str, Any]:
    return {
        "update_id": 77,
        "message": {
            "message_id": 5,
            "date": 1,
            "chat": {"id": chat_id, "type": "private"},
            "from": {"id": chat_id, "is_bot": False, "first_name": "Owner"},
            "text": text,
        },
    }


def test_telegram_webhook_runs_agent_and_sends_reply(monkeypatch) -> None:
    from mia import main

    convex = ConvexStub(accepted=True)
    sendblue = SendBlueStub()
    telegram = TelegramStub()
    install_overrides(convex, sendblue, telegram)
    monkeypatch.setattr(main, "handle_message", HandlerStub())
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post(
        "/webhooks/telegram/receive",
        json=telegram_payload(),
        headers={"x-telegram-bot-api-secret-token": "telegram-secret"},
    )

    assert response.status_code == 200
    assert response.json()["reply"] == "handled"
    assert telegram.sent == [{"chat_id": "123", "content": "handled"}]
    assert convex.completed[0]["active_agent"] == "fast_reply"
    app.dependency_overrides.clear()


def test_telegram_webhook_blocks_unallowed_chat() -> None:
    convex = ConvexStub(accepted=True)
    sendblue = SendBlueStub()
    telegram = TelegramStub()
    install_overrides(convex, sendblue, telegram)
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post(
        "/webhooks/telegram/receive",
        json=telegram_payload(chat_id=999),
        headers={"x-telegram-bot-api-secret-token": "telegram-secret"},
    )

    assert response.status_code == 200
    assert response.json()["ignored"] == "telegram_chat_not_allowed"
    assert telegram.sent == []
    app.dependency_overrides.clear()
