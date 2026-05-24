from dataclasses import dataclass, field
from typing import Any

import pytest
from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool

from mia.graphs.coding_orchestra import run_coding_orchestra
from mia.graphs.design_orchestra import run_design_orchestra
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

    async def complete_pending_action(self, **_kwargs: Any) -> None:
        return None

    async def fail_pending_action(self, **_kwargs: Any) -> None:
        return None

    async def record_agent_spawn(self, **kwargs: Any) -> None:
        self.thoughts.append({"agent_spawn": kwargs})

    async def update_agent_spawn_status(self, **kwargs: Any) -> None:
        self.thoughts.append({"agent_spawn_status": kwargs})


class SequenceLlm:
    def __init__(self, responses: list[AIMessage]):
        self.responses = responses
        self.bind_history: list[list[str]] = []
        self.bound_tool_names: list[str] = []
        self.invocations: list[list[Any]] = []

    def bind_tools(self, tools: list[Any]) -> "SequenceLlm":
        self.bound_tool_names = [tool.name for tool in tools]
        self.bind_history.append(self.bound_tool_names)
        return self

    async def ainvoke(self, _messages: list[Any]) -> AIMessage:
        self.invocations.append(_messages)
        if not self.responses:
            raise AssertionError("No fake LLM responses left")
        return self.responses.pop(0)


def settings() -> Settings:
    return Settings(
        OPENAI_API_KEY="key",
        OPENAI_BASE_URL="https://llm.test/v1",
        MODEL_NAME="model",
        OWNER_PHONE_NUMBER="+15551110000",
        TELEGRAM_OWNER_CHAT_ID="123",
    )


def base_state() -> router.MiaRouterState:
    return {
        "run_id": "run-1",
        "message": "Can you debug this Python function?",
        "relevant_memories": [
            {"tier": "long_term", "segment": "preferences", "content": "Prefers concise replies"}
        ],
        "from_number": "+15551110000",
        "sendblue_number": "+15552220000",
        "message_handle": "msg-1",
        "route": "",
        "sub_agent_name": "",
        "sub_agent_objective": "",
        "allowed_tools": [],
        "agent_result": "",
        "reply": "",
        "thoughts": [],
    }


@pytest.mark.asyncio
async def test_classifier_prefers_fast_reply_for_simple_message(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_llm = SequenceLlm(
        [
            AIMessage(
                content=(
                    '{"mode":"fast_reply","reason":"simple question","reply_style":"Reply briefly.",'
                    '"should_write_memory":false,"memory_content":"","memory_segment":"other",'
                    '"memory_importance":0.0,"task_complexity":"simple","task_name":"",'
                    '"task_objective":"","allowed_tools":[],"orchestration_depth":"standard"}'
                )
            )
        ]
    )
    monkeypatch.setattr(router, "build_chat_model", lambda *_args, **_kwargs: fake_llm)

    result = await router.classify_message(base_state(), settings(), ConvexSpy())

    assert result["mode"] == "fast_reply"
    assert result["allowed_tools"] == []
    assert fake_llm.bind_history == []
    assert "Local user.md profile:" in str(fake_llm.invocations[0][-1].content)


@pytest.mark.asyncio
async def test_classifier_repairs_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_llm = SequenceLlm(
        [
            AIMessage(content="Open Wikipedia in the browser."),
            AIMessage(
                content=(
                    '{"mode":"tool_task","reason":"needs browser control","reply_style":"Reply briefly.",'
                    '"should_write_memory":false,"memory_content":"","memory_segment":"other",'
                    '"memory_importance":0.0,"task_complexity":"simple","task_name":"browser_worker",'
                    '"task_objective":"Open https://www.wikipedia.org in the Mac browser.",'
                    '"allowed_tools":["open_url"],"orchestration_depth":"brief"}'
                )
            ),
        ]
    )
    monkeypatch.setattr(router, "build_chat_model", lambda *_args, **_kwargs: fake_llm)

    state = base_state()
    state["message"] = "帮我打开 Wikipedia"
    result = await router.classify_message(state, settings(), ConvexSpy())

    assert result["mode"] == "tool_task"
    assert result["task_name"] == "browser_worker"
    assert result["allowed_tools"] == ["open_url"]


@pytest.mark.asyncio
async def test_classifier_routes_programming_work_to_coding_orchestra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_llm = SequenceLlm(
        [
            AIMessage(
                content=(
                    '{"mode":"coding_orchestra","reason":"complex programming request",'
                    '"reply_style":"Reply clearly.","should_write_memory":false,'
                    '"memory_content":"","memory_segment":"other","memory_importance":0.0,'
                    '"task_complexity":"multi_step","task_name":"coding_orchestra",'
                    '"task_objective":"Improve the agent architecture.","allowed_tools":[],"orchestration_depth":"standard"}'
                )
            )
        ]
    )
    monkeypatch.setattr(router, "build_chat_model", lambda *_args, **_kwargs: fake_llm)

    state = base_state()
    state["message"] = "帮我重构这个 agent 的编程任务编排，避免无限 loop。"
    result = await router.classify_message(state, settings(), ConvexSpy())

    assert result["mode"] == "coding_orchestra"
    assert result["task_name"] == "coding_orchestra"
    assert result["allowed_tools"] == []
    assert result["task_complexity"] == "multi_step"
    assert result["orchestration_depth"] == "standard"


@pytest.mark.asyncio
async def test_classifier_routes_product_design_work_to_design_orchestra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_llm = SequenceLlm(
        [
            AIMessage(
                content=(
                    '{"mode":"design_orchestra","reason":"product UI design request",'
                    '"reply_style":"Reply clearly.","should_write_memory":false,'
                    '"memory_content":"","memory_segment":"other","memory_importance":0.0,'
                    '"task_complexity":"multi_step","task_name":"design_orchestra",'
                    '"task_objective":"Design a Cursor-like landing page.","allowed_tools":[],"orchestration_depth":"standard"}'
                )
            )
        ]
    )
    monkeypatch.setattr(router, "build_chat_model", lambda *_args, **_kwargs: fake_llm)

    state = base_state()
    state["message"] = "帮我设计一个像 Cursor 一样克制的产品网站首页。"
    result = await router.classify_message(state, settings(), ConvexSpy())

    assert result["mode"] == "design_orchestra"
    assert result["task_name"] == "design_orchestra"
    assert result["allowed_tools"] == []
    assert result["task_complexity"] == "multi_step"
    assert result["orchestration_depth"] == "standard"


@pytest.mark.asyncio
async def test_fast_reply_returns_final_message_without_composer(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_llm = SequenceLlm([AIMessage(content="Short answer.")])
    monkeypatch.setattr(router, "build_chat_model", lambda *_args, **_kwargs: fake_llm)

    reply = await router.fast_reply(base_state(), settings(), ConvexSpy(), reply_style="Reply briefly.")

    assert reply == "Short answer."
    assert fake_llm.bind_history == []


@pytest.mark.asyncio
async def test_tool_task_executes_single_round_for_simple_task(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_llm = SequenceLlm(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "propose_test_cases", "args": {"feature": "router"}, "id": "call_code"}
                ],
            ),
            AIMessage(content="Recommended tests are ready."),
        ]
    )
    monkeypatch.setattr(router, "build_chat_model", lambda *_args, **_kwargs: fake_llm)

    state = base_state()
    result = await router.execute_tool_task(
        state,
        settings(),
        ConvexSpy(),
        task_name="coding_worker",
        task_objective="Propose tests for the router bug.",
        allowed_tools=["propose_test_cases"],
        task_complexity="simple",
    )

    assert result == "Recommended tests are ready."
    assert fake_llm.bind_history == [["propose_test_cases"]]


@pytest.mark.asyncio
async def test_tool_task_allows_bounded_multi_step_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_llm = SequenceLlm(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "update_plan", "args": {"items": ["inspect", "test"]}, "id": "call_plan"}
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "session_status", "args": {}, "id": "call_status"}
                ],
            ),
            AIMessage(content="I inspected the issue and updated the plan."),
        ]
    )
    monkeypatch.setattr(router, "build_chat_model", lambda *_args, **_kwargs: fake_llm)

    state = base_state()
    result = await router.execute_tool_task(
        state,
        settings(),
        ConvexSpy(),
        task_name="coding_worker",
        task_objective="Inspect the issue and keep track of steps.",
        allowed_tools=["update_plan", "session_status"],
        task_complexity="multi_step",
    )

    assert result == "I inspected the issue and updated the plan."
    assert fake_llm.bind_history == [
        ["update_plan", "session_status"],
        ["update_plan", "session_status"],
        ["update_plan", "session_status"],
    ]


@pytest.mark.asyncio
async def test_computer_tool_worker_gets_larger_budget_and_full_browser_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_llm = SequenceLlm([AIMessage(content="I only opened Wikipedia.")])
    monkeypatch.setattr(router, "build_chat_model", lambda *_args, **_kwargs: fake_llm)

    state = base_state()
    state["message"] = "打开wikipedia 搜索algebra 点击最上面的选项"
    result = await router.execute_tool_task(
        state,
        settings(),
        ConvexSpy(),
        task_name="wikipedia_search_algebra",
        task_objective="Open Wikipedia, search algebra, confirm, and click the top result.",
        allowed_tools=["browser_task"],
        task_complexity="multi_step",
    )

    system_prompt = str(fake_llm.invocations[0][0].content)
    assert "maximum of 14 tool-use round" in system_prompt
    assert "click_screen" in system_prompt
    assert "type_text" in system_prompt
    assert "site='wikipedia', query='algebra'" in system_prompt
    assert "did not use its assigned tools" in result


@pytest.mark.asyncio
async def test_computer_worker_does_not_mark_homepage_only_as_complete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_browser_task(goal: str, site: str = "", query: str = "") -> str:
        return "Opened: https://www.wikipedia.org\nGoal: Open Wikipedia website"

    browser_tool = StructuredTool.from_function(
        coroutine=fake_browser_task,
        name="browser_task",
        description="fake browser task",
    )
    fake_llm = SequenceLlm(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "browser_task",
                        "args": {"goal": "Open Wikipedia website", "site": "wikipedia"},
                        "id": "call_browser",
                    }
                ],
            ),
            AIMessage(content="Done."),
        ]
    )
    monkeypatch.setattr(router, "build_chat_model", lambda *_args, **_kwargs: fake_llm)

    result = await router._run_tool_agent(
        state=base_state(),
        settings=settings(),
        convex=ConvexSpy(),
        node_name="wikipedia_search_algebra",
        task_objective="Open Wikipedia, search algebra, confirm, and click the top result.",
        tools=[browser_tool],
        task_complexity="multi_step",
    )

    assert result["completed"] is False
    assert "did not complete" in result["agent_result"]


@pytest.mark.asyncio
async def test_tool_task_must_use_assigned_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_llm = SequenceLlm([AIMessage(content="I did it without tools.")])
    monkeypatch.setattr(router, "build_chat_model", lambda *_args, **_kwargs: fake_llm)

    state = base_state()
    result = await router.execute_tool_task(
        state,
        settings(),
        ConvexSpy(),
        task_name="coding_worker",
        task_objective="Propose tests.",
        allowed_tools=["propose_test_cases"],
        task_complexity="simple",
    )

    assert "did not use its assigned tools" in result
    assert fake_llm.bind_history == [["propose_test_cases"]]


@pytest.mark.asyncio
async def test_handle_message_stores_memory_then_acknowledges(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_llm = SequenceLlm(
        [
            AIMessage(
                content=(
                    '{"mode":"memory_update","reason":"durable preference","reply_style":"Reply briefly.",'
                    '"should_write_memory":true,"memory_content":"User prefers concise replies.",'
                    '"memory_segment":"preferences","memory_importance":0.8,"task_complexity":"simple",'
                    '"task_name":"","task_objective":"","allowed_tools":[],"orchestration_depth":"standard"}'
                )
            )
        ]
    )
    monkeypatch.setattr(router, "build_chat_model", lambda *_args, **_kwargs: fake_llm)
    convex = ConvexSpy()

    result = await router.handle_message(base_state(), settings(), convex)

    assert result["route"] == "memory_update"
    assert result["reply"] == "我记住了。"
    assert convex.memories[0]["segment"] == "preferences"
    assert convex.memories[0]["content"] == "User prefers concise replies."


@pytest.mark.asyncio
async def test_handle_message_routes_to_coding_orchestra(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_llm = SequenceLlm(
        [
            AIMessage(
                content=(
                    '{"mode":"coding_orchestra","reason":"programming architecture work",'
                    '"reply_style":"Reply clearly.","should_write_memory":false,'
                    '"memory_content":"","memory_segment":"other","memory_importance":0.0,'
                    '"task_complexity":"multi_step","task_name":"coding_orchestra",'
                    '"task_objective":"Strengthen the coding agent.","allowed_tools":[],"orchestration_depth":"standard"}'
                )
            )
        ]
    )
    monkeypatch.setattr(router, "build_chat_model", lambda *_args, **_kwargs: fake_llm)

    async def fake_orchestra(state: dict[str, Any], *_args: Any, **_kwargs: Any) -> str:
        assert state["orchestration_depth"] == "standard"
        return "orchestrated answer"

    monkeypatch.setattr(router, "run_coding_orchestra", fake_orchestra)

    result = await router.handle_message(base_state(), settings(), ConvexSpy())

    assert result["route"] == "coding_orchestra"
    assert result["reply"] == "orchestrated answer"


@pytest.mark.asyncio
async def test_handle_message_routes_to_design_orchestra(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_llm = SequenceLlm(
        [
            AIMessage(
                content=(
                    '{"mode":"design_orchestra","reason":"product design work",'
                    '"reply_style":"Reply clearly.","should_write_memory":false,'
                    '"memory_content":"","memory_segment":"other","memory_importance":0.0,'
                    '"task_complexity":"multi_step","task_name":"design_orchestra",'
                    '"task_objective":"Improve the product UI.","allowed_tools":[],"orchestration_depth":"standard"}'
                )
            )
        ]
    )
    monkeypatch.setattr(router, "build_chat_model", lambda *_args, **_kwargs: fake_llm)

    async def fake_orchestra(state: dict[str, Any], *_args: Any, **_kwargs: Any) -> str:
        assert state["orchestration_depth"] == "standard"
        return "design answer"

    monkeypatch.setattr(router, "run_design_orchestra", fake_orchestra)

    result = await router.handle_message(base_state(), settings(), ConvexSpy())

    assert result["route"] == "design_orchestra"
    assert result["reply"] == "design answer"


@pytest.mark.asyncio
async def test_coding_orchestra_runs_bounded_specialists(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_llm = SequenceLlm(
        [
            AIMessage(content="scout notes"),
            AIMessage(content="plan notes"),
            AIMessage(content="build notes"),
            AIMessage(content="verify notes"),
            AIMessage(content="final coding answer"),
        ]
    )

    import mia.graphs.coding_orchestra as orchestra

    monkeypatch.setattr(orchestra, "build_chat_model", lambda *_args, **_kwargs: fake_llm)
    convex = ConvexSpy()
    state = base_state()
    state["message"] = "请完整 debug 并重构这个 agent loop。"
    state["orchestration_depth"] = "deep"  # type: ignore[typeddict-unknown-key]

    result = await run_coding_orchestra(state, settings(), convex)

    assert result == "final coding answer"
    assert "Local user.md profile:" in str(fake_llm.invocations[0][-1].content)
    assert [thought["node"] for thought in convex.thoughts if "node" in thought] == [
        "coding_orchestra.scout",
        "coding_orchestra.scout",
        "coding_orchestra.plan",
        "coding_orchestra.plan",
        "coding_orchestra.build",
        "coding_orchestra.build",
        "coding_orchestra.verify",
        "coding_orchestra.verify",
        "coding_orchestra.review",
        "coding_orchestra.review",
    ]


@pytest.mark.asyncio
async def test_design_orchestra_runs_bounded_design_specialists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_llm = SequenceLlm(
        [
            AIMessage(content="brief notes"),
            AIMessage(content="skill notes"),
            AIMessage(content="system notes"),
            AIMessage(content="compose notes"),
            AIMessage(content="verify notes"),
            AIMessage(content="final design answer"),
        ]
    )

    import mia.graphs.design_orchestra as orchestra

    monkeypatch.setattr(orchestra, "build_chat_model", lambda *_args, **_kwargs: fake_llm)
    convex = ConvexSpy()
    state = base_state()
    state["message"] = "请完整设计一个高质量 setup page 和 chat UI。"
    state["orchestration_depth"] = "deep"  # type: ignore[typeddict-unknown-key]

    result = await run_design_orchestra(state, settings(), convex)

    assert result == "final design answer"
    first_prompt = str(fake_llm.invocations[0][-1].content)
    assert "Local user.md profile:" in first_prompt
    assert "Workspace DESIGN.md:" in first_prompt
    assert "Mia Opencode Operator Design System" in first_prompt
    assert [thought["node"] for thought in convex.thoughts if "node" in thought] == [
        "design_orchestra.brief",
        "design_orchestra.brief",
        "design_orchestra.skill_select",
        "design_orchestra.skill_select",
        "design_orchestra.design_system",
        "design_orchestra.design_system",
        "design_orchestra.compose",
        "design_orchestra.compose",
        "design_orchestra.verify",
        "design_orchestra.verify",
        "design_orchestra.handoff",
        "design_orchestra.handoff",
    ]


def test_coding_tools_still_exposed() -> None:
    assert "propose_test_cases" in [tool.name for tool in CODING_TOOLS]


@pytest.mark.asyncio
async def test_owner_only_tools_allow_configured_telegram_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_llm = SequenceLlm([AIMessage(content="status ok")])
    monkeypatch.setattr(router, "build_chat_model", lambda *_args, **_kwargs: fake_llm)
    state = base_state()
    state["from_number"] = "telegram:123"

    result = await router.execute_tool_task(
        state,
        settings(),
        ConvexSpy(),
        task_name="status_worker",
        task_objective="Check workspace status.",
        allowed_tools=["workspace_status"],
        task_complexity="simple",
    )

    assert "did not use its assigned tools" in result


@pytest.mark.asyncio
async def test_owner_only_tools_allow_web_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_llm = SequenceLlm([AIMessage(content="status ok")])
    monkeypatch.setattr(router, "build_chat_model", lambda *_args, **_kwargs: fake_llm)
    state = base_state()
    state["from_number"] = "web-client"

    result = await router.execute_tool_task(
        state,
        settings(),
        ConvexSpy(),
        task_name="desktop_worker",
        task_objective="List desktop folders.",
        allowed_tools=["list_directory"],
        task_complexity="simple",
    )

    assert result != "I can't use owner-only tools from this sender."
    assert "did not use its assigned tools" in result
