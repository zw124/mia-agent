from typing import Any

import pytest

from mia.tools import composio
from mia.tools.registry import AVAILABLE_TOOL_NAMES, tool_registry


class ConvexStub:
    def __init__(self) -> None:
        self.actions: list[dict[str, Any]] = []

    async def create_pending_action(self, **kwargs: Any) -> str:
        self.actions.append(kwargs)
        return "123456"


@pytest.mark.asyncio
async def test_composio_tools_are_registered() -> None:
    registry = tool_registry(
        ConvexStub(),
        source_message_handle="msg-1",
        requester_number="+1555",
        composio_enabled=True,
    )

    assert "composio_search" in registry
    assert "composio_whoami" in registry
    assert "composio_link" in registry
    assert "composio_schema" in registry
    assert "composio_dry_run" in registry
    assert "composio_execute" in registry
    assert "composio_run" in registry
    assert "composio_run" in AVAILABLE_TOOL_NAMES


@pytest.mark.asyncio
async def test_composio_execute_requests_approval() -> None:
    convex = ConvexStub()
    registry = tool_registry(
        convex,
        source_message_handle="msg-1",
        requester_number="+1555",
        composio_enabled=True,
    )

    result = await registry["composio_execute"].ainvoke(
        {"slug": "GITHUB_GET_THE_AUTHENTICATED_USER", "payload": {}}
    )

    assert "Reply approve" in result
    assert convex.actions[0]["kind"] == "composio_execute"


@pytest.mark.asyncio
async def test_composio_run_requests_approval() -> None:
    convex = ConvexStub()
    registry = tool_registry(
        convex,
        source_message_handle="msg-1",
        requester_number="+1555",
        composio_enabled=True,
    )

    result = await registry["composio_run"].ainvoke(
        {"script": 'const me = await execute("GITHUB_GET_THE_AUTHENTICATED_USER"); console.log(me);'}
    )

    assert "Reply approve" in result
    assert convex.actions[0]["kind"] == "composio_run"


def test_execute_composio_pending_action_handles_run(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_run(args: list[str], *, timeout: int = 60) -> str:
        assert args == ["run", "console.log(1)"]
        assert timeout == 180
        return "ok"

    monkeypatch.setattr(composio, "_run_composio", fake_run)

    result = composio.execute_composio_pending_action(
        {"kind": "composio_run", "payload": {"script": "console.log(1)"}}
    )

    assert result == "ok"
