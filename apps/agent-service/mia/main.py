import asyncio
import contextlib
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
import httpx

from mia.graphs.memory_court import build_memory_court_graph
from mia.graphs.router import handle_message
from mia.integrations.convex import ConvexClient
from mia.integrations.sendblue import SendBlueClient
from mia.integrations.telegram import TelegramClient
from mia.models import SendBlueWebhook, TelegramWebhook
from mia.settings import Settings, get_settings
from mia.tools.computer import (
    auto_approve_status,
    disable_auto_approve,
    enable_auto_approve,
    execute_pending_action,
)

app = FastAPI(title="Mia Agent Service", version="0.1.0")

APPROVAL_PHRASES = {
    "approve",
    "approved",
    "yes approve",
    "yes",
    "y",
    "ok",
    "okay",
    "sure",
    "do it",
    "go ahead",
    "同意",
    "批准",
    "可以",
}
AUTO_APPROVE_ON_PHRASES = {
    "auto approve",
    "autoapprove",
    "turn on auto approve",
    "enable auto approve",
    "自动approve",
    "自动批准",
    "开启自动批准",
}
AUTO_APPROVE_OFF_PHRASES = {
    "stop auto approve",
    "disable auto approve",
    "turn off auto approve",
    "auto approve off",
    "关闭自动批准",
    "停止自动批准",
}

ProgressCallback = Callable[[str], Awaitable[None]]


def normalize_command_text(content: str) -> str:
    return " ".join(content.strip().lower().split())


def is_approval_message(content: str) -> bool:
    normalized = normalize_command_text(content)
    return normalized in APPROVAL_PHRASES or normalized.startswith("approve ")


def is_auto_approve_on_message(content: str) -> bool:
    normalized = normalize_command_text(content)
    return normalized in AUTO_APPROVE_ON_PHRASES


def is_auto_approve_off_message(content: str) -> bool:
    normalized = normalize_command_text(content)
    return normalized in AUTO_APPROVE_OFF_PHRASES


def looks_like_audio_payload(payload: SendBlueWebhook) -> bool:
    message_type = (payload.message_type or "").lower()
    media_url = (payload.media_url or "").lower()
    if "audio" in message_type or "voice" in message_type:
        return True
    return any(media_url.endswith(ext) for ext in (".m4a", ".mp3", ".wav", ".aac", ".ogg", ".webm"))


async def transcribe_audio_payload(payload: SendBlueWebhook, settings: Settings) -> str:
    if not payload.media_url or not settings.openai_api_key or not settings.openai_base_url:
        return ""
    base_url = settings.openai_base_url.rstrip("/")
    endpoint = f"{base_url}/audio/transcriptions"
    headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
    async with httpx.AsyncClient(timeout=60) as client:
        media_response = await client.get(payload.media_url)
        media_response.raise_for_status()
        files = {
            "file": (
                "imessage-audio.m4a",
                media_response.content,
                media_response.headers.get("content-type", "audio/mp4"),
            )
        }
        data = {"model": settings.transcription_model}
        response = await client.post(endpoint, headers=headers, data=data, files=files)
        response.raise_for_status()
        body = response.json()
    text = body.get("text")
    return text.strip() if isinstance(text, str) else ""


async def send_typing_indicator_once(*, sendblue: SendBlueClient, number: str | None) -> None:
    if not number or not hasattr(sendblue, "send_typing_indicator"):
        return
    try:
        await sendblue.send_typing_indicator(number=number)
    except Exception:
        return


async def typing_indicator_pulse(
    *,
    sendblue: SendBlueClient,
    number: str,
    stop: asyncio.Event,
    interval_seconds: float = 4.0,
) -> None:
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval_seconds)
            return
        except asyncio.TimeoutError:
            await send_typing_indicator_once(sendblue=sendblue, number=number)


async def start_typing_indicator(
    *,
    sendblue: SendBlueClient,
    number: str | None,
) -> tuple[asyncio.Event | None, asyncio.Task[None] | None]:
    if not number:
        return None, None
    await send_typing_indicator_once(sendblue=sendblue, number=number)
    stop = asyncio.Event()
    task = asyncio.create_task(
        typing_indicator_pulse(sendblue=sendblue, number=number, stop=stop),
        name=f"sendblue-typing-{number}",
    )
    return stop, task


async def stop_typing_indicator(
    stop: asyncio.Event | None,
    task: asyncio.Task[None] | None,
) -> None:
    if not stop or not task:
        return
    stop.set()
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


async def send_progress_message(
    *,
    sendblue: SendBlueClient,
    convex: ConvexClient,
    inbound: SendBlueWebhook,
    number: str | None,
    content: str,
) -> None:
    if not number or not content.strip():
        return
    try:
        outbound = await sendblue.send_message(number=number, content=content.strip())
        await convex.record_outbound_message(inbound, content.strip(), outbound)
    except Exception:
        return


async def approve_latest_action(
    *,
    convex: ConvexClient,
    requester_number: str,
) -> str:
    action = await convex.approve_pending_action(requester_number=requester_number)
    if not action:
        return "No pending action to approve."
    if action.get("error") == "multiple":
        return (
            "There is more than one pending action. Ask me to retry after clearing older requests."
        )
    if action.get("error"):
        return "No pending action to approve."
    try:
        result = execute_pending_action(action)
        await convex.complete_pending_action(
            code=action["code"],
            requester_number=requester_number,
            result=result,
        )
        return f"Approved and completed:\n{result[:1200]}"
    except Exception as exc:
        await convex.fail_pending_action(
            code=action["code"],
            requester_number=requester_number,
            error=str(exc),
        )
        return f"Approved, but execution failed: {exc}"


def get_convex(settings: Settings = Depends(get_settings)) -> ConvexClient:
    return ConvexClient(settings)


def get_sendblue(settings: Settings = Depends(get_settings)) -> SendBlueClient:
    return SendBlueClient(settings)


def get_telegram(settings: Settings = Depends(get_settings)) -> TelegramClient:
    return TelegramClient(settings)


@app.get("/health")
async def health(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    llm_status = (
        "configured"
        if all([settings.openai_api_key, settings.openai_base_url, settings.model_name])
        else "missing"
    )
    return {"status": "ok", "llm": llm_status}


@app.post("/webhooks/sendblue/receive")
async def receive_sendblue(
    payload: SendBlueWebhook,
    sb_signing_secret: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
    convex: ConvexClient = Depends(get_convex),
    sendblue: SendBlueClient = Depends(get_sendblue),
) -> dict[str, object]:
    if settings.sendblue_webhook_secret and sb_signing_secret != settings.sendblue_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook secret"
        )

    if payload.is_outbound:
        await convex.record_webhook_event(payload, ignored=True)
        return {"ok": True, "ignored": "outbound"}

    accepted = await convex.record_inbound_message(payload)
    if not accepted:
        return {"ok": True, "deduped": True}

    from_number = payload.from_number or payload.number
    message_content = payload.content
    if payload.media_url and looks_like_audio_payload(payload):
        await send_typing_indicator_once(sendblue=sendblue, number=from_number)
        transcript = await transcribe_audio_payload(payload, settings)
        if transcript:
            message_content = transcript
            await send_progress_message(
                sendblue=sendblue,
                convex=convex,
                inbound=payload,
                number=from_number,
                content=f"已收到语音，我听到的是：{transcript[:500]}",
            )
        elif not message_content.strip():
            reply = "我收到了语音，但现在没能转写出来。请再发一次，或者直接发文字。"
            outbound = await sendblue.send_message(number=from_number, content=reply)
            await convex.record_outbound_message(payload, reply, outbound)
            return {"ok": True, "reply": reply, "route": "voice_transcription_failed"}

    if is_auto_approve_on_message(message_content):
        await send_typing_indicator_once(sendblue=sendblue, number=from_number)
        if not settings.owner_phone_number or from_number != settings.owner_phone_number:
            reply = "I can only change auto approve from the owner number."
        else:
            enable_auto_approve(from_number)
            reply = auto_approve_status(from_number)
            approved = await approve_latest_action(convex=convex, requester_number=from_number)
            if not approved.startswith("No pending action"):
                reply = f"{reply}\n\n{approved}"
        outbound = await sendblue.send_message(number=from_number, content=reply)
        await convex.record_outbound_message(payload, reply, outbound)
        return {"ok": True, "reply": reply, "route": "auto_approve_on"}

    if is_auto_approve_off_message(message_content):
        await send_typing_indicator_once(sendblue=sendblue, number=from_number)
        if not settings.owner_phone_number or from_number != settings.owner_phone_number:
            reply = "I can only change auto approve from the owner number."
        else:
            disable_auto_approve(from_number)
            reply = auto_approve_status(from_number)
        outbound = await sendblue.send_message(number=from_number, content=reply)
        await convex.record_outbound_message(payload, reply, outbound)
        return {"ok": True, "reply": reply, "route": "auto_approve_off"}

    if is_approval_message(message_content):
        await send_typing_indicator_once(sendblue=sendblue, number=from_number)
        if not settings.owner_phone_number or from_number != settings.owner_phone_number:
            reply = "I can only accept approvals from the owner number."
        else:
            reply = await approve_latest_action(convex=convex, requester_number=from_number)
        outbound = await sendblue.send_message(number=from_number, content=reply)
        await convex.record_outbound_message(payload, reply, outbound)
        return {"ok": True, "reply": reply, "route": "approval"}

    run_id = str(uuid.uuid4())
    await convex.start_agent_run(run_id=run_id, message_handle=payload.message_handle)
    typing_stop, typing_task = await start_typing_indicator(sendblue=sendblue, number=from_number)

    progress_sent = 0

    async def progress_callback(update: str) -> None:
        nonlocal progress_sent
        if progress_sent >= 3:
            return
        progress_sent += 1
        await send_progress_message(
            sendblue=sendblue,
            convex=convex,
            inbound=payload,
            number=from_number,
            content=update,
        )

    try:
        relevant_memories = await convex.relevant_memories(message=message_content)
        result = await handle_message(
            {
                "run_id": run_id,
                "message": message_content,
                "relevant_memories": relevant_memories,
                "from_number": payload.from_number or payload.number,
                "sendblue_number": payload.sendblue_number or payload.to_number,
                "message_handle": payload.message_handle,
                "route": "direct_reply",
                "sub_agent_name": "",
                "sub_agent_objective": "",
                "allowed_tools": [],
                "agent_result": "",
                "reply": "",
                "thoughts": [],
                "progress_callback": progress_callback,
            },
            settings,
            convex,
        )
    except Exception as exc:
        await stop_typing_indicator(typing_stop, typing_task)
        await convex.fail_agent_run(run_id=run_id, error=str(exc))
        raise

    reply = result["reply"]
    try:
        outbound = await sendblue.send_message(
            number=payload.from_number or payload.number, content=reply
        )
        await convex.record_outbound_message(payload, reply, outbound)
        await convex.complete_agent_run(run_id=run_id, active_agent=result["route"])
    except Exception as exc:
        await convex.log_thought(
            message_handle=payload.message_handle,
            run_id=run_id,
            node="sendblue_outbound",
            content=f"Failed to send outbound iMessage: {exc}",
            active_agent=None,
        )
        await convex.fail_agent_run(run_id=run_id, error=str(exc))
        raise
    finally:
        await stop_typing_indicator(typing_stop, typing_task)
    return {"ok": True, "reply": reply, "route": result["route"]}


def _telegram_allowed(settings: Settings, chat_id: str) -> bool:
    allowed = {
        item.strip()
        for item in settings.telegram_allowed_chat_ids.split(",")
        if item.strip()
    }
    if settings.telegram_owner_chat_id:
        allowed.add(settings.telegram_owner_chat_id.strip())
    return not allowed or chat_id in allowed


def _telegram_synthetic_payload(payload: TelegramWebhook) -> tuple[SendBlueWebhook, str, str]:
    message = payload.message or payload.edited_message
    if not message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Telegram message")
    content = message.text or message.caption or ""
    chat_id = str(message.chat.id)
    message_handle = f"telegram:{chat_id}:{message.message_id}:{payload.update_id}"
    return (
        SendBlueWebhook(
            content=content,
            is_outbound=False,
            message_handle=message_handle,
            from_number=f"telegram:{chat_id}",
            number=f"telegram:{chat_id}",
            to_number="telegram:bot",
            message_type="telegram",
            participants=[f"telegram:{chat_id}"],
            service="telegram",
        ),
        chat_id,
        content,
    )


@app.post("/webhooks/telegram/receive")
async def receive_telegram(
    payload: TelegramWebhook,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
    convex: ConvexClient = Depends(get_convex),
    telegram: TelegramClient = Depends(get_telegram),
) -> dict[str, object]:
    if (
        settings.telegram_webhook_secret
        and x_telegram_bot_api_secret_token != settings.telegram_webhook_secret
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Telegram webhook secret"
        )

    synthetic, chat_id, message_content = _telegram_synthetic_payload(payload)
    if not _telegram_allowed(settings, chat_id):
        await convex.record_webhook_event(synthetic, ignored=True)
        return {"ok": True, "ignored": "telegram_chat_not_allowed"}

    accepted = await convex.record_inbound_message(synthetic)
    if not accepted:
        return {"ok": True, "deduped": True}

    if is_approval_message(message_content):
        if settings.telegram_owner_chat_id and chat_id != settings.telegram_owner_chat_id:
            reply = "I can only accept approvals from the configured Telegram owner chat."
        else:
            reply = await approve_latest_action(
                convex=convex,
                requester_number=f"telegram:{chat_id}",
            )
        outbound = await telegram.send_message(chat_id=chat_id, content=reply)
        await convex.record_outbound_message(synthetic, reply, outbound)
        return {"ok": True, "reply": reply, "route": "approval"}

    run_id = str(uuid.uuid4())
    await convex.start_agent_run(run_id=run_id, message_handle=synthetic.message_handle)
    progress_sent = 0

    async def progress_callback(update: str) -> None:
        nonlocal progress_sent
        if progress_sent >= 3:
            return
        progress_sent += 1
        try:
            outbound = await telegram.send_message(chat_id=chat_id, content=update)
            await convex.record_outbound_message(synthetic, update, outbound)
        except Exception:
            return

    try:
        relevant_memories = await convex.relevant_memories(message=message_content)
        result = await handle_message(
            {
                "run_id": run_id,
                "message": message_content,
                "relevant_memories": relevant_memories,
                "from_number": f"telegram:{chat_id}",
                "sendblue_number": None,
                "message_handle": synthetic.message_handle,
                "route": "direct_reply",
                "sub_agent_name": "",
                "sub_agent_objective": "",
                "allowed_tools": [],
                "agent_result": "",
                "reply": "",
                "thoughts": [],
                "progress_callback": progress_callback,
            },
            settings,
            convex,
        )
    except Exception as exc:
        await convex.fail_agent_run(run_id=run_id, error=str(exc))
        raise

    reply = result["reply"]
    try:
        outbound = await telegram.send_message(chat_id=chat_id, content=reply)
        await convex.record_outbound_message(synthetic, reply, outbound)
        await convex.complete_agent_run(run_id=run_id, active_agent=result["route"])
    except Exception as exc:
        await convex.fail_agent_run(run_id=run_id, error=str(exc))
        raise
    return {"ok": True, "reply": reply, "route": result["route"]}


@app.post("/internal/memory-court/run")
async def run_memory_court(
    request: Request,
    x_mia_internal_secret: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
    convex: ConvexClient = Depends(get_convex),
) -> dict[str, object]:
    if not settings.mia_internal_secret or x_mia_internal_secret != settings.mia_internal_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid internal secret"
        )

    body = await request.json()
    run_id = body.get("runId")
    local_date = body.get("localDate")
    if not isinstance(run_id, str) or not run_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing runId")
    if not isinstance(local_date, str) or not local_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing localDate")
    memories = await convex.list_court_candidate_memories()
    graph = build_memory_court_graph(settings)
    result = await graph.ainvoke(
        {
            "run_id": run_id,
            "local_date": local_date,
            "memories": memories,
            "proposals": [],
            "adversarial_rounds": [],
            "judge_decisions": [],
            "round": 0,
        }
    )
    await convex.apply_memory_court_decisions(run_id=run_id, result=result)
    return {"ok": True, "runId": run_id, "decisions": len(result["judge_decisions"])}
