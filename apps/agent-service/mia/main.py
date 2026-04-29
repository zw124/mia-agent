import asyncio
import contextlib
import uuid

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status

from mia.graphs.memory_court import build_memory_court_graph
from mia.graphs.router import build_router_graph, initial_router_state
from mia.integrations.convex import ConvexClient
from mia.integrations.sendblue import SendBlueClient
from mia.models import SendBlueWebhook
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
    if is_auto_approve_on_message(payload.content):
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

    if is_auto_approve_off_message(payload.content):
        await send_typing_indicator_once(sendblue=sendblue, number=from_number)
        if not settings.owner_phone_number or from_number != settings.owner_phone_number:
            reply = "I can only change auto approve from the owner number."
        else:
            disable_auto_approve(from_number)
            reply = auto_approve_status(from_number)
        outbound = await sendblue.send_message(number=from_number, content=reply)
        await convex.record_outbound_message(payload, reply, outbound)
        return {"ok": True, "reply": reply, "route": "auto_approve_off"}

    if is_approval_message(payload.content):
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
    try:
        relevant_memories = await convex.relevant_memories(message=payload.content)
        graph = build_router_graph(settings, convex)
        result = await graph.ainvoke(
            initial_router_state(
                run_id=run_id,
                message=payload.content,
                relevant_memories=relevant_memories,
                from_number=payload.from_number or payload.number,
                sendblue_number=payload.sendblue_number or payload.to_number,
                message_handle=payload.message_handle,
            )
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
