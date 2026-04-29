from dataclasses import dataclass, field
from typing import Any

import pytest
from langchain_core.messages import AIMessage

from mia.graphs import router
from mia.settings import Settings
from mia.tools.coding import CODING_TOOLS


@dataclass
class ConvexSpy:
    thoughts: list[dict[str, Any]] = field(default_factory=list)
    memories: list[dict[str, Any]] = field(default_factory=list)

    async def log_thought(self, **kwargs: Any) -> None:
        self.thoughts.append(kwargs)

    async def upsert_memory(self, **kwargs: Any) -> None:
        self.memories.append(kwargs)

    async def list_calendar_holds(self, *, day: str) -> list[dict[str, Any]]:
        return [{"title": "Focus", "day": day, "time": "09:00", "status": "tentative"}]

    async def create_calendar_hold(
        self,
        *,
        title: str,
        day: str,
        time: str,
        source_message_handle: str,
    ) -> str:
        return f"{source_message_handle}:{day}:{time}:{title}"

    async def create_pending_action(self, **_kwargs: Any) -> str:
        return "123456"

    async def record_agent_spawn(self, **kwargs: Any) -> None:
        self.thoughts.append({"agent_spawn": kwargs})

    async def update_agent_spawn_status(self, **kwargs: Any) -> None:
        self.thoughts.append({"agent_spawn_status": kwargs})


class FakeRouterLlm:
    bind_called = False

    async def ainvoke(self, _messages: list[Any]) -> AIMessage:
        return AIMessage(
            content=(
                '{"route":"dynamic_sub_agent","reason":"programming request",'
                '"sub_agent_name":"coding_worker","sub_agent_objective":"help with code",'
                '"allowed_tools":["propose_test_cases"]}'
            )
        )

    def bind_tools(self, _tools: list[Any]) -> "FakeRouterLlm":
        self.bind_called = True
        raise AssertionError("Parent router must never bind or execute tools")


class FakeRepairingRouterLlm:
    bind_called = False

    def __init__(self) -> None:
        self.calls = 0

    async def ainvoke(self, _messages: list[Any]) -> AIMessage:
        self.calls += 1
        if self.calls == 1:
            return AIMessage(content="I should open Wikipedia with a browser worker.")
        return AIMessage(
            content=(
                '{"route":"dynamic_sub_agent","reason":"needs computer control",'
                '"sub_agent_name":"browser_worker",'
                '"sub_agent_objective":"Open https://www.wikipedia.org in the Mac browser.",'
                '"allowed_tools":["open_url"]}'
            )
        )

    def bind_tools(self, _tools: list[Any]) -> "FakeRepairingRouterLlm":
        self.bind_called = True
        raise AssertionError("Parent router must never bind or execute tools")


class FakeToolCallingLlm:
    def __init__(self, recorder: list[list[str]], final_text: str):
        self.recorder = recorder
        self.final_text = final_text
        self.bound_tool_names: list[str] = []

    def bind_tools(self, tools: list[Any]) -> "FakeToolCallingLlm":
        self.bound_tool_names = [tool.name for tool in tools]
        self.recorder.append(self.bound_tool_names)
        return self

    async def ainvoke(self, _messages: list[Any]) -> AIMessage:
        if "list_calendar_events" in self.bound_tool_names:
            return AIMessage(
                content="",
                tool_calls=[
                    {"name": "list_calendar_events", "args": {"day": "today"}, "id": "call_calendar"}
                ],
            )
        if "propose_test_cases" in self.bound_tool_names:
            return AIMessage(
                content="",
                tool_calls=[
                    {"name": "propose_test_cases", "args": {"feature": "router"}, "id": "call_code"}
                ],
            )
        return AIMessage(content=self.final_text)


class FakeNoToolCallLlm:
    def __init__(self, recorder: list[list[str]]):
        self.recorder = recorder
        self.bound_tool_names: list[str] = []

    def bind_tools(self, tools: list[Any]) -> "FakeNoToolCallLlm":
        self.bound_tool_names = [tool.name for tool in tools]
        self.recorder.append(self.bound_tool_names)
        return self

    async def ainvoke(self, _messages: list[Any]) -> AIMessage:
        return AIMessage(content="I did it without calling a tool.")


def settings() -> Settings:
    return Settings(
        OPENAI_API_KEY="key",
        OPENAI_BASE_URL="https://llm.test/v1",
        MODEL_NAME="model",
        OWNER_PHONE_NUMBER="+15551110000",
    )


def base_state() -> router.MiaRouterState:
    return router.initial_router_state(
        run_id="run-1",
        message="Can you debug this Python function?",
        relevant_memories=[
            {"tier": "long_term", "segment": "preferences", "content": "Prefers concise replies"}
        ],
        from_number="+15551110000",
        sendblue_number="+15552220000",
        message_handle="msg-1",
    )


@pytest.mark.asyncio
async def test_parent_router_classifies_without_tool_binding(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_llm = FakeRouterLlm()
    monkeypatch.setattr(router, "build_chat_model", lambda *_args, **_kwargs: fake_llm)

    result = await router.parent_router(base_state(), settings(), ConvexSpy())

    assert result["route"] == "dynamic_sub_agent"
    assert result["sub_agent_name"] == "coding_worker"
    assert result["allowed_tools"] == ["propose_test_cases"]
    assert fake_llm.bind_called is False


@pytest.mark.asyncio
async def test_parent_router_repairs_invalid_json_without_keyword_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_llm = FakeRepairingRouterLlm()
    monkeypatch.setattr(router, "build_chat_model", lambda *_args, **_kwargs: fake_llm)

    state = base_state()
    state["message"] = "帮我打开 Wikipedia"
    result = await router.parent_router(state, settings(), ConvexSpy())

    assert result["route"] == "dynamic_sub_agent"
    assert result["sub_agent_name"] == "browser_worker"
    assert result["allowed_tools"] == ["open_url"]
    assert fake_llm.calls == 2
    assert fake_llm.bind_called is False


@pytest.mark.asyncio
async def test_calendar_agent_receives_only_calendar_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    bindings: list[list[str]] = []
    monkeypatch.setattr(
        router,
        "build_chat_model",
        lambda *_args, **_kwargs: FakeToolCallingLlm(bindings, "calendar final"),
    )

    state = base_state()
    state["sub_agent_name"] = "calendar_worker"
    state["sub_agent_objective"] = "check calendar"
    state["allowed_tools"] = ["list_calendar_events", "create_calendar_hold"]

    result = await router.dynamic_sub_agent(state, settings(), ConvexSpy())

    assert result["agent_result"] == "calendar final"
    assert bindings == [["list_calendar_events", "create_calendar_hold"]]
    assert not set(tool.name for tool in CODING_TOOLS).intersection(bindings[0])


@pytest.mark.asyncio
async def test_coding_agent_receives_only_coding_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    bindings: list[list[str]] = []
    monkeypatch.setattr(
        router,
        "build_chat_model",
        lambda *_args, **_kwargs: FakeToolCallingLlm(bindings, "coding final"),
    )

    state = base_state()
    state["sub_agent_name"] = "coding_worker"
    state["sub_agent_objective"] = "propose tests"
    state["allowed_tools"] = [tool.name for tool in CODING_TOOLS]

    result = await router.dynamic_sub_agent(state, settings(), ConvexSpy())

    assert result["agent_result"] == "coding final"
    assert bindings == [[tool.name for tool in CODING_TOOLS]]
    assert not {"list_calendar_events", "create_calendar_hold"}.intersection(bindings[0])


@pytest.mark.asyncio
async def test_tool_enabled_sub_agent_must_call_assigned_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    bindings: list[list[str]] = []
    monkeypatch.setattr(
        router,
        "build_chat_model",
        lambda *_args, **_kwargs: FakeNoToolCallLlm(bindings),
    )

    state = base_state()
    state["sub_agent_name"] = "coding_worker"
    state["sub_agent_objective"] = "propose tests"
    state["allowed_tools"] = ["propose_test_cases"]

    result = await router.dynamic_sub_agent(state, settings(), ConvexSpy())

    assert "did not call any assigned tool" in result["agent_result"]
    assert bindings == [["propose_test_cases"]]
