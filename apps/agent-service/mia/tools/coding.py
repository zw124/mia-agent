from langchain_core.tools import tool


CURRENT_PLAN: list[str] = []


@tool
def explain_code_request(request: str) -> str:
    """Break down a programming request into concise implementation steps."""
    cleaned = request.strip()
    return f"Implementation outline for: {cleaned}"


@tool
def propose_test_cases(feature: str) -> str:
    """Propose focused test cases for a coding feature or bug fix."""
    return f"Recommended tests: happy path, validation failure, edge input, and regression for {feature}."


@tool
def update_plan(items: list[str]) -> str:
    """Replace Mia's lightweight in-memory task plan for the current agent process."""
    CURRENT_PLAN.clear()
    CURRENT_PLAN.extend(item.strip() for item in items if item.strip())
    if not CURRENT_PLAN:
        return "Plan cleared."
    return "\n".join(f"{index + 1}. {item}" for index, item in enumerate(CURRENT_PLAN))


@tool
def session_status() -> str:
    """Return lightweight status for the current Mia agent process."""
    if not CURRENT_PLAN:
        return "Mia agent process is running. No active lightweight plan."
    return "Mia agent process is running.\nCurrent plan:\n" + "\n".join(
        f"{index + 1}. {item}" for index, item in enumerate(CURRENT_PLAN)
    )


@tool
def agents_list() -> str:
    """Describe Mia's available agent roles."""
    return "\n".join(
        [
            "parent_router: classifies iMessage requests and creates sub-agent specs.",
            "dynamic_sub_agent: receives a restricted tool set and executes the delegated task.",
            "memory_update: extracts durable memories into Convex.",
            "memory_court: nightly consolidator, adversarial defender, and judge workflow.",
        ]
    )


@tool
def tools_inventory() -> str:
    """List the tool names currently registered for Mia dynamic sub-agents."""
    from mia.tools.registry import AVAILABLE_TOOL_NAMES

    return "\n".join(sorted(AVAILABLE_TOOL_NAMES))


CODING_TOOLS = [
    explain_code_request,
    propose_test_cases,
    update_plan,
    session_status,
    agents_list,
    tools_inventory,
]
