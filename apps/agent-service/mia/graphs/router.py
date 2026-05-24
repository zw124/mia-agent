import json
import re
from typing import Any, Literal, NotRequired, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool

from mia.integrations.convex import ConvexClient
from mia.graphs.coding_orchestra import run_coding_orchestra
from mia.graphs.design_orchestra import run_design_orchestra
from mia.llm import build_chat_model
from mia.settings import Settings
from mia.tools.registry import (
    AVAILABLE_TOOL_NAMES,
    OWNER_ONLY_TOOLS,
    public_tool_descriptions,
    tool_registry,
)
from mia.user_profile import load_user_profile

ExecutionMode = Literal["fast_reply", "memory_update", "tool_task", "coding_orchestra", "design_orchestra"]
TaskComplexity = Literal["simple", "multi_step"]
OrchestrationDepth = Literal["brief", "standard", "deep"]

COMPUTER_TOOL_NAMES = {
    "browser_task",
    "open_url",
    "computer_observe",
    "screenshot_desktop",
    "click_screen",
    "type_text",
    "press_key",
    "scroll",
}

PASSIVE_COMPUTER_TOOLS = {
    "computer_observe",
    "screenshot_desktop",
    "get_frontmost_app",
    "list_running_apps",
}

COMPLEX_COMPUTER_TOOLKIT = [
    "computer_plan",
    "computer_observe",
    "browser_task",
    "click_screen",
    "type_text",
    "press_key",
    "scroll",
]


class MiaRouterState(TypedDict):
    run_id: str
    message: str
    relevant_memories: list[dict[str, Any]]
    from_number: str
    sendblue_number: str | None
    message_handle: str
    route: str
    sub_agent_name: str
    sub_agent_objective: str
    allowed_tools: list[str]
    agent_result: str
    reply: str
    thoughts: list[str]
    conversation_context: NotRequired[list[dict[str, Any]]]


class MessageDecision(TypedDict):
    mode: ExecutionMode
    reason: str
    reply_style: str
    should_write_memory: bool
    memory_content: str
    memory_segment: str
    memory_importance: float
    task_complexity: TaskComplexity
    task_name: str
    task_objective: str
    allowed_tools: list[str]
    orchestration_depth: OrchestrationDepth


DECISION_SYSTEM = """You are Mia's message orchestrator.
Decide whether the incoming iMessage should use:
- fast_reply: direct conversational answer with no tool execution
- memory_update: store a durable memory and send a short acknowledgement
- coding_orchestra: bounded specialist routing for programming, debugging, code review, architecture, or agent-design work
- design_orchestra: bounded design-specialist routing for product UI, UX, websites, dashboards, visual systems, and design critique
- tool_task: create a tool-using worker task

Rules:
- Prefer fast_reply by default.
- Use memory_update only when the main user intent is to tell Mia a durable preference, fact, task, relationship, or project detail worth storing.
- Use coding_orchestra for software engineering work that benefits from scout/plan/build/verify/review thinking but does not yet require direct external tool execution.
- Use design_orchestra for UI/UX, product pages, landing pages, dashboards, chat interfaces, setup flows, design systems, visual polish, or design critique that benefits from design taste/context.
- Use tool_task only when the user is clearly asking for an external action, structured retrieval, file/computer operation, search, or another tool-dependent task.
- Do not escalate simple questions into tool_task.
- Do not use coding_orchestra for casual chat, scheduling, memory-only updates, or non-technical questions.
- Do not use design_orchestra for casual visual opinions if a short direct answer is enough.
- For computer-use requests, prefer a staged tool_task with computer_plan and computer_observe before click_screen/type_text/press_key unless the user asked for one obvious atomic action.
- For browser navigation/search tasks, prefer browser_task before low-level click_screen/type_text actions. Preserve the full end-to-end browser objective, including search terms and "click/open top result"; do not reduce it to only opening the homepage.
- For tool_task, choose the minimal allowed_tools needed.
- orchestration_depth controls coding_orchestra/design_orchestra cost:
  - brief: answer or design through the smallest specialist path
  - standard: enough phases for useful quality without slow full review
  - deep: full specialist pass only when the request is high-stakes, broad, production-grade, ambiguous, or explicitly asks for exhaustive work
- Decide orchestration_depth from intent, risk, ambiguity, and expected output quality. Do not rely only on keywords.
- reply_style should describe how the final reply should sound for fast_reply.

Available tool names:
{tools}

Return strict JSON only:
{{
  "mode":"fast_reply|memory_update|tool_task|coding_orchestra|design_orchestra",
  "reason":"...",
  "reply_style":"...",
  "should_write_memory":true,
  "memory_content":"...",
  "memory_segment":"preferences|facts|tasks|relationships|projects|other",
  "memory_importance":0.0,
  "task_complexity":"simple|multi_step",
  "task_name":"...",
  "task_objective":"...",
  "allowed_tools":["..."],
  "orchestration_depth":"brief|standard|deep"
}}"""


DECISION_REPAIR_SYSTEM = """You repair Mia orchestrator output.
Return strict JSON only using this schema:
{
  "mode":"fast_reply|memory_update|tool_task|coding_orchestra|design_orchestra",
  "reason":"...",
  "reply_style":"...",
  "should_write_memory":true,
  "memory_content":"...",
  "memory_segment":"preferences|facts|tasks|relationships|projects|other",
  "memory_importance":0.0,
  "task_complexity":"simple|multi_step",
  "task_name":"...",
  "task_objective":"...",
  "allowed_tools":["..."],
  "orchestration_depth":"brief|standard|deep"
}
Only use listed tool names. Prefer fast_reply unless coding_orchestra, design_orchestra, or tool_task is clearly required."""


def memory_context(state: MiaRouterState) -> str:
    memories = state.get("relevant_memories", [])
    if not memories:
        return "No relevant stored memories."
    return "\n".join(
        f"- [{memory.get('tier')}/{memory.get('segment')}] {memory.get('content')}"
        for memory in memories
    )


def conversation_context(state: MiaRouterState) -> str:
    messages = state.get("conversation_context", [])
    if not messages:
        return "No recent conversation context."

    ordered = list(reversed(messages))[-12:]
    rows: list[str] = []
    for message in ordered:
        direction = message.get("direction")
        role = "user" if direction == "inbound" else "mia"
        content = str(message.get("content") or "").strip()
        if not content:
            continue
        rows.append(f"- {role}: {content[:1200]}")
    return "\n".join(rows) if rows else "No recent conversation context."


def _load_json(content: Any) -> dict[str, Any]:
    text = str(content).strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3:
            text = "\n".join(lines[1:-1]).strip()
    return json.loads(text)


def _clamp_importance(value: Any, fallback: float = 0.6) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = fallback
    return max(0.0, min(1.0, numeric))


def _normalize_tools(raw_tools: Any) -> list[str]:
    if not isinstance(raw_tools, list):
        raise ValueError("allowed_tools must be a list")
    normalized: list[str] = []
    for tool in raw_tools:
        name = str(tool).strip()
        if not name:
            continue
        if name not in AVAILABLE_TOOL_NAMES:
            raise ValueError(f"unknown tool: {name}")
        if name not in normalized:
            normalized.append(name)
    return normalized


def _validate_decision(parsed: dict[str, Any]) -> MessageDecision:
    mode = str(parsed.get("mode", "")).strip()
    if mode not in {"fast_reply", "memory_update", "tool_task", "coding_orchestra", "design_orchestra"}:
        raise ValueError(f"invalid mode: {mode}")

    reason = str(parsed.get("reason") or "classified").strip()
    reply_style = str(parsed.get("reply_style") or "Reply briefly and clearly.").strip()
    should_write_memory = bool(parsed.get("should_write_memory", False))
    memory_segment = str(parsed.get("memory_segment") or "other").strip()
    if memory_segment not in {"preferences", "facts", "tasks", "relationships", "projects", "other"}:
        memory_segment = "other"
    memory_content = str(parsed.get("memory_content") or "").strip()
    memory_importance = _clamp_importance(parsed.get("memory_importance"), 0.6)
    task_complexity = str(parsed.get("task_complexity") or "simple").strip()
    if task_complexity not in {"simple", "multi_step"}:
        task_complexity = "simple"
    task_name = str(parsed.get("task_name") or "").strip()
    task_objective = str(parsed.get("task_objective") or "").strip()
    allowed_tools = _normalize_tools(parsed.get("allowed_tools") or [])
    orchestration_depth = str(parsed.get("orchestration_depth") or "standard").strip()
    if orchestration_depth not in {"brief", "standard", "deep"}:
        orchestration_depth = "standard"

    if mode == "tool_task":
        if not allowed_tools:
            raise ValueError("tool_task requires at least one allowed tool")
        if not task_objective:
            raise ValueError("tool_task requires task_objective")
        if not task_name:
            task_name = "tool_worker"
    elif mode == "coding_orchestra":
        task_name = "coding_orchestra"
        task_objective = task_objective or "Route the programming request through bounded specialist phases."
        allowed_tools = []
        task_complexity = "multi_step"
    elif mode == "design_orchestra":
        task_name = "design_orchestra"
        task_objective = task_objective or "Route the product design request through bounded design-specialist phases."
        allowed_tools = []
        task_complexity = "multi_step"
    else:
        task_name = ""
        task_objective = ""
        allowed_tools = []
        task_complexity = "simple"
        orchestration_depth = "brief"

    if mode == "memory_update":
        should_write_memory = True
        if not memory_content:
            memory_content = ""
    elif not should_write_memory:
        memory_content = ""

    return {
        "mode": mode,  # type: ignore[typeddict-item]
        "reason": reason or "classified",
        "reply_style": reply_style or "Reply briefly and clearly.",
        "should_write_memory": should_write_memory,
        "memory_content": memory_content,
        "memory_segment": memory_segment,
        "memory_importance": memory_importance,
        "task_complexity": task_complexity,  # type: ignore[typeddict-item]
        "task_name": task_name,
        "task_objective": task_objective,
        "allowed_tools": allowed_tools,
        "orchestration_depth": orchestration_depth,  # type: ignore[typeddict-item]
    }


def _looks_incomplete_browser_task(objective: str, executed_tools: list[str], last_tool_result: str) -> bool:
    objective_lower = objective.lower()
    needs_search_or_selection = any(
        marker in objective_lower
        for marker in (
            "search",
            "搜索",
            "top result",
            "top option",
            "first result",
            "最上",
            "第一个",
            "confirm",
            "确认",
            "click",
            "点击",
        )
    )
    if not needs_search_or_selection:
        return False
    active_tools = [tool for tool in executed_tools if tool not in PASSIVE_COMPUTER_TOOLS]
    if not active_tools:
        return True
    if active_tools == ["browser_task"]:
        result_lower = last_tool_result.lower()
        objective_words = [
            word
            for word in re.findall(r"[a-zA-Z0-9]+", objective_lower)
            if len(word) > 3 and word not in {"open", "click", "search", "confirm", "result", "wikipedia"}
        ]
        result_has_query = any(word in result_lower for word in objective_words)
        result_has_search_url = "special:search" in result_lower or "/wiki/" in result_lower
        return not (result_has_query or result_has_search_url)
    return False


def _parse_xml_tool_calls(content: Any) -> list[dict[str, Any]]:
    text = str(content or "")
    calls: list[dict[str, Any]] = []
    for index, match in enumerate(re.finditer(r"<tool_call>(.*?)</tool_call>", text, flags=re.DOTALL)):
        raw = match.group(1).strip()
        if not raw:
            continue
        name_match = re.match(r"([A-Za-z_][A-Za-z0-9_]*)", raw)
        if not name_match:
            continue
        args: dict[str, Any] = {}
        for arg_match in re.finditer(
            r"<arg_key>(.*?)</arg_key>\s*<arg_value>(.*?)</arg_value>",
            raw,
            flags=re.DOTALL,
        ):
            key = arg_match.group(1).strip()
            value = arg_match.group(2).strip()
            if key:
                args[key] = value
        calls.append({
            "id": f"xml-tool-{index}",
            "name": name_match.group(1),
            "args": args,
            "source": "xml",
        })
    return calls


async def _repair_decision(*, llm: Any, raw_content: Any, state: MiaRouterState) -> MessageDecision:
    response = await llm.ainvoke(
        [
            SystemMessage(content=DECISION_REPAIR_SYSTEM),
            HumanMessage(
                content=(
                    f"Local user.md profile:\n{load_user_profile()}\n\n"
                    f"Available tools:\n{public_tool_descriptions()}\n\n"
                    f"Stored memory context:\n{memory_context(state)}\n\n"
                    f"Recent conversation context:\n{conversation_context(state)}\n\n"
                    f"User message:\n{state['message']}\n\n"
                    f"Invalid orchestrator output:\n{raw_content}"
                )
            ),
        ]
    )
    return _validate_decision(_load_json(response.content))


async def classify_message(state: MiaRouterState, settings: Settings, convex: ConvexClient) -> MessageDecision:
    llm = build_chat_model(settings, temperature=0)
    response = await llm.ainvoke(
        [
            SystemMessage(content=DECISION_SYSTEM.format(tools=public_tool_descriptions())),
            HumanMessage(
                content=(
                    f"Local user.md profile:\n{load_user_profile()}\n\n"
                    f"Stored memory context:\n{memory_context(state)}\n\n"
                    f"Recent conversation context:\n{conversation_context(state)}\n\n"
                    f"Message:\n{state['message']}"
                )
            ),
        ]
    )
    try:
        decision = _validate_decision(_load_json(response.content))
    except (json.JSONDecodeError, TypeError, ValueError):
        try:
            decision = await _repair_decision(llm=llm, raw_content=response.content, state=state)
            decision["reason"] = f"{decision['reason']} (decision repaired)"
        except (json.JSONDecodeError, TypeError, ValueError):
            decision = {
                "mode": "fast_reply",
                "reason": "decision invalid after repair; defaulted to direct reply",
                "reply_style": "Reply briefly and clearly.",
                "should_write_memory": False,
                "memory_content": "",
                "memory_segment": "other",
                "memory_importance": 0.0,
                "task_complexity": "simple",
                "task_name": "",
                "task_objective": "",
                "allowed_tools": [],
                "orchestration_depth": "brief",
            }

    await convex.log_thought(
        message_handle=state["message_handle"],
        run_id=state["run_id"],
        node="message_classifier",
        content=f"Mode={decision['mode']}. {decision['reason']}",
        active_agent="message_classifier",
    )
    return decision


async def maybe_store_memory(
    *,
    state: MiaRouterState,
    convex: ConvexClient,
    decision: MessageDecision,
) -> None:
    if not decision["should_write_memory"]:
        return
    content = decision["memory_content"].strip() or state["message"].strip()
    if not content:
        return
    await convex.upsert_memory(
        content=content,
        segment=decision["memory_segment"],
        source_message_handle=state["message_handle"],
        importance_score=decision["memory_importance"],
    )
    await convex.log_thought(
        message_handle=state["message_handle"],
        run_id=state["run_id"],
        node="memory_writer",
        content=f"Stored memory in segment={decision['memory_segment']}.",
        active_agent="memory_writer",
    )


async def fast_reply(state: MiaRouterState, settings: Settings, convex: ConvexClient, *, reply_style: str) -> str:
    llm = build_chat_model(settings, temperature=0.2)
    response = await llm.ainvoke(
        [
            SystemMessage(
                content=(
                    "You are Mia replying over iMessage. "
                    f"{reply_style} "
                    "Answer directly. Do not mention internal routing, tools, or background workflows. "
                    "If the request needs external actions you cannot do from this direct path, say so plainly."
                )
            ),
            HumanMessage(
                content=(
                    f"Local user.md profile:\n{load_user_profile()}\n\n"
                    f"Stored memory context:\n{memory_context(state)}\n\n"
                    f"Recent conversation context:\n{conversation_context(state)}\n\n"
                    f"Message:\n{state['message']}"
                )
            ),
        ]
    )
    reply = str(response.content).strip()
    await convex.log_thought(
        message_handle=state["message_handle"],
        run_id=state["run_id"],
        node="fast_reply",
        content="Generated direct iMessage reply.",
        active_agent="fast_reply",
    )
    return reply


async def memory_reply(state: MiaRouterState, convex: ConvexClient) -> str:
    await convex.log_thought(
        message_handle=state["message_handle"],
        run_id=state["run_id"],
        node="memory_reply",
        content="Acknowledged memory update.",
        active_agent="memory_reply",
    )
    return "我记住了。"


async def execute_tool_task(
    state: MiaRouterState,
    settings: Settings,
    convex: ConvexClient,
    *,
    task_name: str,
    task_objective: str,
    allowed_tools: list[str],
    task_complexity: TaskComplexity,
) -> str:
    requested_tools = list(dict.fromkeys(allowed_tools))
    if task_complexity == "multi_step" and any(tool in COMPUTER_TOOL_NAMES for tool in requested_tools):
        requested_tools = list(dict.fromkeys([*requested_tools, *COMPLEX_COMPUTER_TOOLKIT]))

    if any(tool in OWNER_ONLY_TOOLS for tool in requested_tools):
        owner_identities = {
            identity
            for identity in (
                settings.owner_phone_number,
                f"telegram:{settings.telegram_owner_chat_id}" if settings.telegram_owner_chat_id else "",
                "web-client",
            )
            if identity
        }
        if state["from_number"] not in owner_identities:
            await convex.log_thought(
                message_handle=state["message_handle"],
                run_id=state["run_id"],
                node="tool_task",
                content="Rejected owner-only tool request from non-owner number.",
                active_agent=task_name or "tool_task",
            )
            await convex.record_agent_spawn(
                run_id=state["run_id"],
                message_handle=state["message_handle"],
                parent_agent="message_classifier",
                name=task_name or "tool_task",
                objective=task_objective,
                allowed_tools=requested_tools,
                status="blocked",
            )
            return "I can't use owner-only tools from this sender."

    registry = tool_registry(
        convex,
        source_message_handle=state["message_handle"],
        requester_number=state["from_number"],
        run_id=state["run_id"],
        searxng_base_url=settings.searxng_base_url,
        composio_enabled=settings.composio_enabled,
    )
    tools = [registry[name] for name in requested_tools if name in registry]
    missing = sorted(set(requested_tools) - set(registry))
    if missing:
        await convex.record_agent_spawn(
            run_id=state["run_id"],
            message_handle=state["message_handle"],
            parent_agent="message_classifier",
            name=task_name or "tool_task",
            objective=task_objective,
            allowed_tools=requested_tools,
            status="blocked",
        )
        return f"I can't create that tool task because these tools are unavailable: {', '.join(missing)}."

    name = task_name or "tool_task"
    await convex.record_agent_spawn(
        run_id=state["run_id"],
        message_handle=state["message_handle"],
        parent_agent="message_classifier",
        name=name,
        objective=task_objective,
        allowed_tools=requested_tools,
        status="running",
    )
    try:
        result = await _run_tool_agent(
            state=state,
            settings=settings,
            convex=convex,
            node_name=name,
            task_objective=task_objective,
            tools=tools,
            task_complexity=task_complexity,
        )
    except Exception as error:
        await convex.update_agent_spawn_status(
            run_id=state["run_id"],
            name=name,
            status="failed",
            error=str(error),
        )
        raise

    await convex.update_agent_spawn_status(
        run_id=state["run_id"],
        name=name,
        status="completed" if result["completed"] else "blocked",
        result=result["agent_result"],
    )
    return result["agent_result"]


async def _run_tool_agent(
    *,
    state: MiaRouterState,
    settings: Settings,
    convex: ConvexClient,
    node_name: str,
    task_objective: str,
    tools: list[BaseTool],
    task_complexity: TaskComplexity,
) -> dict[str, Any]:
    tool_map = {tool.name: tool for tool in tools}
    tool_list = ", ".join(tool_map)
    step_budget = 1 if task_complexity == "simple" else 3
    is_computer_task = any(name in tool_map for name in COMPUTER_TOOL_NAMES)
    if is_computer_task:
        step_budget = max(step_budget, 14)
    system_prompt = (
        f"You are Mia's tool worker named {node_name}. "
        f"Objective: {task_objective}. "
        f"You may only use these tools: {tool_list}. "
        f"This task has a maximum of {step_budget} tool-use round(s). "
        "Prefer the shortest path to a correct result. "
        "For complex computer-use tasks, decompose the objective into checkpoints and keep acting until the final user-visible state is reached. "
        "Complete the entire objective, not just the first sub-step. "
        "Observation and screenshots are not completion; they are checkpoints. "
        "After each computer/browser tool result, inspect whether the current screen state satisfies the full objective; if not, use the next low-level action tool. "
        "If a computer action returns an approval or macOS assistive-access error, stop and report that exact blocker instead of claiming completion. "
        "For browser search/navigation requests, pass the full goal and search query to browser_task when possible. "
        "For example, if asked to open Wikipedia, search algebra, and open the top result, call browser_task with site='wikipedia', query='algebra', and the full goal. "
        "Use structured tool calls when available. "
        "If your provider cannot emit native tool calls, emit exactly one XML call like "
        "<tool_call>browser_task<arg_key>goal</arg_key><arg_value>Open Wikipedia, search algebra, and open the top result</arg_value><arg_key>site</arg_key><arg_value>wikipedia</arg_value><arg_key>query</arg_key><arg_value>algebra</arg_value></tool_call>. "
        "If the task can be answered after tool output, provide the final user-facing result plainly."
    )
    messages: list[Any] = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=(
                f"Local user.md profile:\n{load_user_profile()}\n\n"
                f"Stored memory context:\n{memory_context(state)}\n\n"
                f"Recent conversation context:\n{conversation_context(state)}\n\n"
                f"Message:\n{state['message']}"
            )
        ),
    ]
    executed_tools: list[str] = []
    last_tool_result = ""

    for step in range(step_budget):
        llm = build_chat_model(settings, temperature=0.1).bind_tools(tools)
        ai_message = await llm.ainvoke(messages)
        messages.append(ai_message)
        tool_calls = getattr(ai_message, "tool_calls", []) or []
        if not tool_calls:
            tool_calls = _parse_xml_tool_calls(ai_message.content)

        if not tool_calls:
            text = str(ai_message.content).strip()
            if not executed_tools:
                await convex.log_thought(
                    message_handle=state["message_handle"],
                    run_id=state["run_id"],
                    node=node_name,
                    content=f"Tool worker stopped without using assigned tools: {tool_list}.",
                    active_agent=node_name,
                )
                return {
                    "completed": False,
                    "agent_result": (
                        "I created the tool task, but it did not use its assigned tools, "
                        "so I did not mark the task completed."
                    ),
                }
            await convex.log_thought(
                message_handle=state["message_handle"],
                run_id=state["run_id"],
                node=node_name,
                content=f"Completed after {step} tool round(s).",
                active_agent=node_name,
            )
            if is_computer_task and (
                not [tool for tool in executed_tools if tool not in PASSIVE_COMPUTER_TOOLS]
                or _looks_incomplete_browser_task(task_objective, executed_tools, last_tool_result)
            ):
                await convex.log_thought(
                    message_handle=state["message_handle"],
                    run_id=state["run_id"],
                    node=f"{node_name}.incomplete",
                    content="Computer-use worker stopped before completing the full browser action objective.",
                    active_agent=node_name,
                )
                return {
                    "completed": False,
                    "agent_result": (
                        "I observed the screen, but I did not complete the requested computer-use action, "
                        "so I did not mark it done."
                    ),
                }
            return {"completed": True, "agent_result": text}

        invalid_tools: list[str] = []
        for call in tool_calls:
            tool_name = call["name"]
            if tool_name not in tool_map:
                invalid_tools.append(tool_name)
                continue
            await convex.log_thought(
                message_handle=state["message_handle"],
                run_id=state["run_id"],
                node=f"tool_call:{tool_name}",
                content=f"Calling {tool_name} with {json.dumps(call.get('args', {}), ensure_ascii=False)}",
                active_agent=node_name,
            )
            result = await tool_map[tool_name].ainvoke(call.get("args", {}))
            last_tool_result = str(result)
            await convex.log_thought(
                message_handle=state["message_handle"],
                run_id=state["run_id"],
                node=f"tool_result:{tool_name}",
                content=last_tool_result[:1600],
                active_agent=node_name,
            )
            if call.get("source") == "xml":
                messages.append(HumanMessage(content=f"Tool result for {tool_name}:\n{last_tool_result}"))
            else:
                messages.append(ToolMessage(content=last_tool_result, tool_call_id=call["id"]))
            executed_tools.append(tool_name)

        if invalid_tools and not executed_tools:
            await convex.log_thought(
                message_handle=state["message_handle"],
                run_id=state["run_id"],
                node=node_name,
                content=f"Tool worker requested unauthorized tools only: {', '.join(invalid_tools)}.",
                active_agent=node_name,
            )
            return {
                "completed": False,
                "agent_result": "The tool worker requested tools it was not allowed to use, so I stopped it."
            }

    final = await build_chat_model(settings, temperature=0.1).ainvoke(messages)
    final_text = str(final.content).strip()
    if "<tool_call>" in final_text and last_tool_result:
        final_text = last_tool_result
    await convex.log_thought(
        message_handle=state["message_handle"],
        run_id=state["run_id"],
        node=node_name,
        content=f"Completed with bounded tool loop using: {', '.join(executed_tools)}.",
        active_agent=node_name,
    )
    if is_computer_task and (
        not [tool for tool in executed_tools if tool not in PASSIVE_COMPUTER_TOOLS]
        or _looks_incomplete_browser_task(task_objective, executed_tools, last_tool_result)
    ):
        await convex.log_thought(
            message_handle=state["message_handle"],
            run_id=state["run_id"],
            node=f"{node_name}.incomplete",
            content="Computer-use worker exhausted its budget before completing the full browser action objective.",
            active_agent=node_name,
        )
        return {
            "completed": False,
            "agent_result": (
                "I opened or observed the browser, but I did not complete the requested search/selection action."
            ),
        }
    return {
        "completed": bool(executed_tools),
        "agent_result": final_text,
    }


async def handle_message(state: MiaRouterState, settings: Settings, convex: ConvexClient) -> dict[str, Any]:
    decision = await classify_message(state, settings, convex)
    await maybe_store_memory(state=state, convex=convex, decision=decision)

    if decision["mode"] == "memory_update":
        reply = await memory_reply(state, convex)
        route = "memory_update"
    elif decision["mode"] == "tool_task":
        reply = await execute_tool_task(
            state,
            settings,
            convex,
            task_name=decision["task_name"],
            task_objective=decision["task_objective"],
            allowed_tools=decision["allowed_tools"],
            task_complexity=decision["task_complexity"],
        )
        route = "tool_task"
    elif decision["mode"] == "coding_orchestra":
        state["orchestration_depth"] = decision["orchestration_depth"]  # type: ignore[typeddict-unknown-key]
        reply = await run_coding_orchestra(state, settings, convex)
        route = "coding_orchestra"
    elif decision["mode"] == "design_orchestra":
        state["orchestration_depth"] = decision["orchestration_depth"]  # type: ignore[typeddict-unknown-key]
        reply = await run_design_orchestra(state, settings, convex)
        route = "design_orchestra"
    else:
        reply = await fast_reply(
            state,
            settings,
            convex,
            reply_style=decision["reply_style"],
        )
        route = "fast_reply"

    return {
        "route": route,
        "reply": reply,
        "decision": decision,
    }
