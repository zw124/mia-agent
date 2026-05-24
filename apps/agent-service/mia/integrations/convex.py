from typing import Any

import httpx

from mia.models import SendBlueWebhook
from mia.settings import Settings


class ConvexClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def _post(self, path: str, payload: dict[str, Any]) -> Any:
        if not self.settings.convex_site_url:
            raise RuntimeError("Missing CONVEX_SITE_URL")
        if not self.settings.mia_internal_secret:
            raise RuntimeError("Missing MIA_INTERNAL_SECRET")

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{self.settings.convex_site_url.rstrip('/')}{path}",
                headers={"x-mia-internal-secret": self.settings.mia_internal_secret},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("result", data)

    async def record_webhook_event(self, payload: SendBlueWebhook, *, ignored: bool) -> None:
        await self._post(
            "/internal/webhook-event",
            {"payload": payload.model_dump(by_alias=True), "ignored": ignored},
        )

    async def record_inbound_message(
        self,
        payload: SendBlueWebhook,
        *,
        session_id: str | None = None,
    ) -> bool:
        body: dict[str, Any] = {"payload": payload.model_dump(by_alias=True)}
        if session_id is not None:
            body["sessionId"] = session_id
        result = await self._post("/internal/inbound-message", body)
        return bool(result.get("accepted"))

    async def record_outbound_message(
        self,
        inbound: SendBlueWebhook,
        reply: str,
        sendblue_response: dict[str, Any],
        *,
        session_id: str | None = None,
    ) -> None:
        body: dict[str, Any] = {
            "inboundMessageHandle": inbound.message_handle,
            "toNumber": inbound.from_number or inbound.number,
            "content": reply,
            "sendblueResponse": sendblue_response,
        }
        if session_id is not None:
            body["sessionId"] = session_id
        await self._post("/internal/outbound-message", body)

    async def log_thought(
        self,
        *,
        message_handle: str,
        run_id: str | None,
        node: str,
        content: str,
        active_agent: str | None = None,
    ) -> None:
        await self._post(
            "/internal/thought-log",
            {
                "messageHandle": message_handle,
                "runId": run_id,
                "node": node,
                "content": content,
                "activeAgent": active_agent,
            },
        )

    async def start_agent_run(self, *, run_id: str, message_handle: str) -> None:
        await self._post(
            "/internal/agent-run/start",
            {"runId": run_id, "messageHandle": message_handle},
        )

    async def complete_agent_run(self, *, run_id: str, active_agent: str) -> None:
        await self._post(
            "/internal/agent-run/complete",
            {"runId": run_id, "activeAgent": active_agent},
        )

    async def fail_agent_run(self, *, run_id: str, error: str) -> None:
        await self._post(
            "/internal/agent-run/fail",
            {"runId": run_id, "error": error},
        )

    async def record_agent_spawn(
        self,
        *,
        run_id: str,
        message_handle: str,
        parent_agent: str,
        name: str,
        objective: str,
        allowed_tools: list[str],
        status: str = "planned",
    ) -> None:
        await self._post(
            "/internal/agent-spawn",
            {
                "runId": run_id,
                "messageHandle": message_handle,
                "parentAgent": parent_agent,
                "name": name,
                "objective": objective,
                "allowedTools": allowed_tools,
                "status": status,
            },
        )

    async def update_agent_spawn_status(
        self,
        *,
        run_id: str,
        name: str,
        status: str,
        result: str | None = None,
        error: str | None = None,
    ) -> None:
        await self._post(
            "/internal/agent-spawn/status",
            {
                "runId": run_id,
                "name": name,
                "status": status,
                "result": result,
                "error": error,
            },
        )

    async def upsert_memory(
        self,
        *,
        content: str,
        segment: str,
        source_message_handle: str,
        importance_score: float,
    ) -> None:
        await self._post(
            "/internal/memory",
            {
                "content": content,
                "segment": segment,
                "sourceMessageHandle": source_message_handle,
                "importanceScore": importance_score,
            },
        )

    async def relevant_memories(self, *, message: str, limit: int = 8) -> list[dict[str, Any]]:
        result = await self._post(
            "/internal/memories/relevant",
            {"message": message, "limit": limit},
        )
        return list(result.get("memories", []))

    async def recent_messages(
        self,
        *,
        participant: str | None = None,
        limit: int = 12,
    ) -> list[dict[str, Any]]:
        result = await self._post(
            "/internal/messages/recent",
            {"participant": participant, "limit": limit},
        )
        return list(result if isinstance(result, list) else result.get("messages", []))

    async def create_calendar_hold(
        self,
        *,
        title: str,
        day: str,
        time: str,
        source_message_handle: str,
    ) -> str:
        result = await self._post(
            "/internal/calendar/holds",
            {
                "title": title,
                "day": day,
                "time": time,
                "sourceMessageHandle": source_message_handle,
            },
        )
        return str(result["id"])

    async def list_calendar_holds(self, *, day: str) -> list[dict[str, Any]]:
        result = await self._post("/internal/calendar/day", {"day": day})
        return list(result.get("holds", []))

    async def create_pending_action(
        self,
        *,
        requester_number: str,
        message_handle: str,
        run_id: str | None,
        kind: str,
        summary: str,
        payload: dict[str, Any],
        risk: str = "approval_required",
    ) -> str:
        result = await self._post(
            "/internal/pending-actions/create",
            {
                "requesterNumber": requester_number,
                "messageHandle": message_handle,
                "runId": run_id,
                "kind": kind,
                "summary": summary,
                "payload": payload,
                "risk": risk,
            },
        )
        return str(result["code"])

    async def approve_pending_action(self, *, requester_number: str) -> dict[str, Any] | None:
        result = await self._post(
            "/internal/pending-actions/approve",
            {"requesterNumber": requester_number},
        )
        if not result.get("ok"):
            return {"error": result.get("reason", "not_found")}
        return result.get("action")

    async def complete_pending_action(self, *, code: str, requester_number: str, result: str) -> None:
        await self._post(
            "/internal/pending-actions/complete",
            {"code": code, "requesterNumber": requester_number, "result": result},
        )

    async def fail_pending_action(self, *, code: str, requester_number: str, error: str) -> None:
        await self._post(
            "/internal/pending-actions/fail",
            {"code": code, "requesterNumber": requester_number, "error": error},
        )

    async def list_court_candidate_memories(self) -> list[dict[str, Any]]:
        result = await self._post("/internal/memory-court/candidates", {})
        return list(result.get("memories", []))

    async def apply_memory_court_decisions(
        self,
        *,
        run_id: str,
        result: dict[str, Any],
    ) -> None:
        await self._post(
            "/internal/memory-court/apply",
            {
                "runId": run_id,
                "proposals": result.get("proposals", []),
                "adversarialRounds": result.get("adversarial_rounds", []),
                "judgeDecisions": result.get("judge_decisions", []),
            },
        )
