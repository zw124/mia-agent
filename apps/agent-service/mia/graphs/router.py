import json
from typing import Any, Literal, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph

from mia.integrations.convex import ConvexClient
from mia.llm import build_chat_model
from mia.models import parse_llm_json
from mia.settings import Settings
from mia.tools.registry import AVAILABLE_TOOL_NAMES, OWNER_ONLY_TOOLS, public_tool_descriptions, tool_registry

RouteName = Literal["direct_reply", "dynamic_sub_agent", "memory_update"]
VALID_ROUTES = {"direct_reply", "dynamic_sub_agent", "memory_update"}


class MiaRouterState(TypedDict):
    run_id: str
    message: str
    relevant_memories: list[dict[str, Any]]
    from_number: str
    sendblue_number: str | None
    message_handle: str
    route: RouteName
    sub_agent_name: str
    sub_agent_objective: str
    allowed_tools: list[str]
    agent_result: str
    reply: str
    thoughts: list[str]


ROUTER_SYSTEM = """You are Mia's parent router.
You cannot call tools and cannot solve specialist tasks.
Classify the user's iMessage into exactly one route:
- direct_reply: normal conversation or simple answer
- dynamic_sub_agent: a task needs tools or a specialist worker
- memory_update: durable facts or preferences Mia should remember
When route is dynamic_sub_agent, create a sub-agent specification but do not execute it.
Available tool names:
{tools}
Return strict JSON only:
{{"route":"...", "reason":"...", "sub_agent_name":"...", "sub_agent_objective":"...", "allowed_tools":["..."]}}."""


ROUTER_REPAIR_SYSTEM = """You repair Mia parent-router output.
Do not answer the user and do not execute the task.
Return strict JSON only with this schema:
{"route":"direct_reply|dynamic_sub_agent|memory_update","reason":"...","sub_agent_name":"...","sub_agent_objective":"...","allowed_tools":["..."]}
Only use tool names from the provided available tools.
For dynamic_sub_agent, allowed_tools must be non-empty and sub_agent_objective must describe the concrete delegated task."""


class RouterDecision(TypedDict):
    route: RouteName
    reason: str
    sub_agent_name: str
    sub_agent_objective: str
    allowed_tools: list[str]


def initial_router_state(
    *,
    run_id: str,
    message: str,
    relevant_memories: list[dict[str, Any]],
    from_number: str,
    sendblue_number: str | None,
    message_handle: str,
) -> MiaRouterState:
    return {
        "run_id": run_id,
        "message": message,
        "relevant_memories": relevant_memories,
        "from_number": from_number,
        "sendblue_number": sendblue_number,
        "message_handle": message_handle,
        "route": "direct_reply",
        "sub_agent_name": "",
        "sub_agent_objective": "",
        "allowed_tools": [],
        "agent_result": "",
        "reply": "",
        "thoughts": [],
    }


def memory_context(state: MiaRouterState) -> str:
    memories = state.get("relevant_memories", [])
    if not memories:
        return "No relevant stored memories."
    return "\n".join(
        f"- [{memory.get('tier')}/{memory.get('segment')}] {memory.get('content')}"
        for memory in memories
    )


def _validate_router_decision(parsed: dict[str, Any]) -> RouterDecision:
    route = str(parsed.get("route", "")).strip()
    if route not in VALID_ROUTES:
        raise ValueError(f"invalid route: {route}")

    reason = str(parsed.get("reason") or "classified").strip()
    allowed_tools = parsed.get("allowed_tools") or []
    if not isinstance(allowed_tools, list):
        raise ValueError("allowed_tools must be a list")

    normalized_tools: list[str] = []
    for tool in allowed_tools:
        tool_name = str(tool).strip()
        if not tool_name:
            continue
        if tool_name not in AVAILABLE_TOOL_NAMES:
            raise ValueError(f"unknown tool: {tool_name}")
        if tool_name not in normalized_tools:
            normalized_tools.append(tool_name)

    sub_agent_name = str(parsed.get("sub_agent_name") or "").strip()
    sub_agent_objective = str(parsed.get("sub_agent_objective") or "").strip()

    if route == "dynamic_sub_agent":
        if not normalized_tools:
            raise ValueError("dynamic_sub_agent requires at least one allowed tool")
        if not sub_agent_objective:
            raise ValueError("dynamic_sub_agent requires sub_agent_objective")
        if not sub_agent_name:
            sub_agent_name = "dynamic_worker"
    else:
        sub_agent_name = ""
        sub_agent_objective = ""
        normalized_tools = []

    return {
        "route": route,  # type: ignore[typeddict-item]
        "reason": reason or "classified",
        "sub_agent_name": sub_agent_name,
        "sub_agent_objective": sub_agent_objective,
        "allowed_tools": normalized_tools,
    }


async def _repair_router_decision(
    *,
    llm: Any,
    raw_content: Any,
    state: MiaRouterState,
) -> RouterDecision:
    response = await llm.ainvoke(
        [
            SystemMessage(content=ROUTER_REPAIR_SYSTEM),
            HumanMessage(
                content=(
                    f"Available tools:\n{public_tool_descriptions()}\n\n"
                    f"Stored memory context:\n{memory_context(state)}\n\n"
                    f"User message:\n{state['message']}\n\n"
                    f"Invalid router output:\n{raw_content}"
                )
            ),
        ]
    )
    return _validate_router_decision(parse_llm_json(response.content))


async def parent_router(state: MiaRouterState, settings: Settings, convex: ConvexClient) -> dict:
    llm = build_chat_model(settings)
    response = await llm.ainvoke(
        [
            SystemMessage(content=ROUTER_SYSTEM.format(tools=public_tool_descriptions())),
            HumanMessage(content=f"Stored memory context:\n{memory_context(state)}\n\nMessage:\n{state['message']}"),
        ]
    )
    try:
        decision = _validate_router_decision(parse_llm_json(response.content))
    except (json.JSONDecodeError, TypeError, ValueError):
        try:
            decision = await _repair_router_decision(llm=llm, raw_content=response.content, state=state)
            decision["reason"] = f"{decision['reason']} (router JSON repaired)"
        except (json.JSONDecodeError, TypeError, ValueError):
            decision = {
                "route": "direct_reply",
                "reason": "router output invalid after repair; no tool execution authorized",
                "sub_agent_name": "",
                "sub_agent_objective": "",
                "allowed_tools": [],
            }

    await convex.log_thought(
        message_handle=state["message_handle"],
        run_id=state["run_id"],
        node="parent_router",
        content=f"Route={decision['route']}. {decision['reason']}",
        active_agent="parent_router",
    )
    if decision["route"] == "dynamic_sub_agent":
        await convex.record_agent_spawn(
            run_id=state["run_id"],
            message_handle=state["message_handle"],
            parent_agent="parent_router",
            name=decision["sub_agent_name"],
            objective=decision["sub_agent_objective"],
            allowed_tools=decision["allowed_tools"],
            status="planned",
        )
    return {
        "route": decision["route"],
        "sub_agent_name": decision["sub_agent_name"],
        "sub_agent_objective": decision["sub_agent_objective"],
        "allowed_tools": decision["allowed_tools"],
        "thoughts": state["thoughts"] + [decision["reason"]],
    }


async def direct_reply(state: MiaRouterState, settings: Settings, convex: ConvexClient) -> dict:
    llm = build_chat_model(settings, temperature=0.2)
    response = await llm.ainvoke(
        [
            SystemMessage(
                content=(
                    "You are Mia. Reply warmly and concisely over iMessage. "
                    "If the user asks you to perform an external action, operate the computer, "
                    "read or write files, run terminal commands, or search the web, do not claim "
                    "that you completed it from this direct-reply node."
                )
            ),
            HumanMessage(content=f"Stored memory context:\n{memory_context(state)}\n\nMessage:\n{state['message']}"),
        ]
    )
    text = str(response.content)
    await convex.log_thought(
        message_handle=state["message_handle"],
        run_id=state["run_id"],
        node="direct_reply",
        content="Generated direct response.",
        active_agent="direct_reply",
    )
    return {"agent_result": text}


async def memory_update(state: MiaRouterState, settings: Settings, convex: ConvexClient) -> dict:
    llm = build_chat_model(settings)
    response = await llm.ainvoke(
        [
            SystemMessage(
                content=(
                    "Extract one durable memory from the message. Return strict JSON: "
                    '{"content":"...", "segment":"preferences|facts|tasks|relationships|projects|other", '
                    '"importanceScore":0.0}'
                )
            ),
            HumanMessage(content=f"Stored memory context:\n{memory_context(state)}\n\nMessage:\n{state['message']}"),
        ]
    )
    try:
        parsed = json.loads(str(response.content))
        content = str(parsed["content"])
        segment = str(parsed.get("segment", "other"))
        importance = float(parsed.get("importanceScore", 0.65))
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        content = state["message"]
        segment = "facts"
        importance = 0.55
    await convex.upsert_memory(
        content=content,
        segment=segment,
        source_message_handle=state["message_handle"],
        importance_score=importance,
    )
    await convex.log_thought(
        message_handle=state["message_handle"],
        run_id=state["run_id"],
        node="memory_update",
        content=f"Stored memory in segment={segment}.",
        active_agent="memory_update",
    )
    return {"agent_result": "我记住了。"}


async def dynamic_sub_agent(state: MiaRouterState, settings: Settings, convex: ConvexClient) -> dict:
    requested_tools = state.get("allowed_tools", [])
    name = state.get("sub_agent_name") or "dynamic_sub_agent"
    if not requested_tools:
        return {"agent_result": "I need a tool-enabled sub-agent specification before I can do that."}

    if any(tool in OWNER_ONLY_TOOLS for tool in requested_tools):
        if not settings.owner_phone_number or state["from_number"] != settings.owner_phone_number:
            await convex.log_thought(
                message_handle=state["message_handle"],
                run_id=state["run_id"],
                node="dynamic_sub_agent",
                content="Rejected owner-only tool request from non-owner number.",
                active_agent=state.get("sub_agent_name") or "dynamic_sub_agent",
            )
            await convex.update_agent_spawn_status(
                run_id=state["run_id"],
                name=name,
                status="blocked",
                error="Owner-only tool request from non-owner number.",
            )
            return {"agent_result": "I can't use owner-only tools from this phone number."}

    registry = tool_registry(
        convex,
        source_message_handle=state["message_handle"],
        requester_number=state["from_number"],
        run_id=state["run_id"],
        searxng_base_url=settings.searxng_base_url,
    )
    tools = [registry[name] for name in requested_tools if name in registry]
    missing = sorted(set(requested_tools) - set(registry))
    if missing:
        await convex.update_agent_spawn_status(
            run_id=state["run_id"],
            name=name,
            status="blocked",
            error=f"Unavailable tools: {', '.join(missing)}.",
        )
        return {"agent_result": f"I can't create that sub-agent because these tools are unavailable: {', '.join(missing)}."}

    objective = state.get("sub_agent_objective") or state["message"]
    await convex.update_agent_spawn_status(run_id=state["run_id"], name=name, status="running")
    if requested_tools == ["open_url"]:
        try:
            result = await registry["open_url"].ainvoke({"target": objective})
        except Exception as error:
            await convex.update_agent_spawn_status(
                run_id=state["run_id"],
                name=name,
                status="failed",
                error=str(error),
            )
            raise
        await convex.log_thought(
            message_handle=state["message_handle"],
            run_id=state["run_id"],
            node=name,
            content="Executed dynamic sub-agent with tool: open_url.",
            active_agent=name,
        )
        await convex.update_agent_spawn_status(
            run_id=state["run_id"],
            name=name,
            status="completed",
            result=str(result),
        )
        return {"agent_result": str(result)}

    try:
        result = await _run_tool_bound_agent(
            state=state,
            settings=settings,
            convex=convex,
            node_name=name,
            system_prompt=(
                f"You are Mia's temporary sub-agent named {name}. "
                f"Objective: {objective}. Use only the tools injected into this node. "
                "Report the concrete result succinctly."
            ),
            tools=tools,
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
        status="completed" if "did not call any assigned tool" not in result["agent_result"] else "blocked",
        result=result["agent_result"],
    )
    return result


async def _run_tool_bound_agent(
    *,
    state: MiaRouterState,
    settings: Settings,
    convex: ConvexClient,
    node_name: str,
    system_prompt: str,
    tools: list[BaseTool],
) -> dict:
    tool_map = {tool.name: tool for tool in tools}
    llm = build_chat_model(settings, temperature=0.1).bind_tools(tools)
    ai_message = await llm.ainvoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Stored memory context:\n{memory_context(state)}\n\nMessage:\n{state['message']}"),
        ]
    )
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Stored memory context:\n{memory_context(state)}\n\nMessage:\n{state['message']}"),
        ai_message,
    ]
    tool_calls = getattr(ai_message, "tool_calls", []) or []
    if not tool_calls:
        await convex.log_thought(
            message_handle=state["message_handle"],
            run_id=state["run_id"],
            node=node_name,
            content=f"Sub-agent was assigned tools but made no tool call: {', '.join(tool_map)}.",
            active_agent=node_name,
        )
        return {
            "agent_result": (
                "I created the sub-agent, but it did not call any assigned tool, "
                "so I did not mark the task completed."
            )
        }

    executed_tools: list[str] = []
    invalid_tools: list[str] = []
    for call in tool_calls:
        tool_name = call["name"]
        if tool_name not in tool_map:
            invalid_tools.append(tool_name)
            continue
        result = await tool_map[tool_name].ainvoke(call.get("args", {}))
        messages.append(ToolMessage(content=str(result), tool_call_id=call["id"]))
        executed_tools.append(tool_name)
    if not executed_tools:
        await convex.log_thought(
            message_handle=state["message_handle"],
            run_id=state["run_id"],
            node=node_name,
            content=f"Sub-agent requested unauthorized tools only: {', '.join(invalid_tools)}.",
            active_agent=node_name,
        )
        return {"agent_result": "The sub-agent requested tools it was not allowed to use, so I stopped it."}

    final = await build_chat_model(settings, temperature=0.1).ainvoke(messages)
    await convex.log_thought(
        message_handle=state["message_handle"],
        run_id=state["run_id"],
        node=node_name,
        content=f"Executed with isolated tools: {', '.join(executed_tools)}.",
        active_agent=node_name,
    )
    return {"agent_result": str(final.content)}


async def compose_reply(state: MiaRouterState, settings: Settings, convex: ConvexClient) -> dict:
    if state["route"] == "memory_update":
        reply = state["agent_result"]
    else:
        llm = build_chat_model(settings, temperature=0.2)
        response = await llm.ainvoke(
            [
                SystemMessage(
                    content=(
                        "You are Mia's response composer. Convert the agent result into a concise "
                        "iMessage reply. Do not mention internal routing."
                    )
                ),
                HumanMessage(
                    content=(
                        f"Stored memory context:\n{memory_context(state)}\n\n"
                        f"User: {state['message']}\nAgent result: {state['agent_result']}"
                    )
                ),
            ]
        )
        reply = str(response.content)
    await convex.log_thought(
        message_handle=state["message_handle"],
        run_id=state["run_id"],
        node="compose_reply",
        content="Composed outbound iMessage.",
        active_agent=None,
    )
    return {"reply": reply}


def route_from_parent(state: MiaRouterState) -> str:
    return state["route"]


def build_router_graph(settings: Settings, convex: ConvexClient):
    async def parent_router_node(state: MiaRouterState) -> dict:
        return await parent_router(state, settings, convex)

    async def direct_reply_node(state: MiaRouterState) -> dict:
        return await direct_reply(state, settings, convex)

    async def dynamic_sub_agent_node(state: MiaRouterState) -> dict:
        return await dynamic_sub_agent(state, settings, convex)

    async def memory_update_node(state: MiaRouterState) -> dict:
        return await memory_update(state, settings, convex)

    async def compose_reply_node(state: MiaRouterState) -> dict:
        return await compose_reply(state, settings, convex)

    graph = StateGraph(MiaRouterState)
    graph.add_node("parent_router", parent_router_node)
    graph.add_node("direct_reply", direct_reply_node)
    graph.add_node("dynamic_sub_agent", dynamic_sub_agent_node)
    graph.add_node("memory_update", memory_update_node)
    graph.add_node("compose_reply", compose_reply_node)

    graph.add_edge(START, "parent_router")
    graph.add_conditional_edges(
        "parent_router",
        route_from_parent,
        {
            "direct_reply": "direct_reply",
            "dynamic_sub_agent": "dynamic_sub_agent",
            "memory_update": "memory_update",
        },
    )
    for node in ["direct_reply", "dynamic_sub_agent", "memory_update"]:
        graph.add_edge(node, "compose_reply")
    graph.add_edge("compose_reply", END)
    return graph.compile()
