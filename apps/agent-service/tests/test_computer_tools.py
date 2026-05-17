from mia.tools.computer import build_computer_tools
from mia.tools.registry import OWNER_ONLY_TOOLS, tool_registry


def _tool_by_name(name: str):
    tools = build_computer_tools(
        requester_number="+15551110000",
        message_handle="msg-1",
        run_id="run-1",
    )
    return {tool.name: tool for tool in tools}[name]


async def test_computer_plan_creates_checkpoint_policy() -> None:
    tool = _tool_by_name("computer_plan")

    result = await tool.ainvoke(
        {
            "goal": "Open the browser and submit a form.",
            "current_observation": "Safari is frontmost.",
        }
    )

    assert "Goal: Open the browser and submit a form." in result
    assert "Observe the current screen" in result
    assert "Stop if the screen state does not match" in result


async def test_computer_action_preview_marks_risk_and_approval() -> None:
    tool = _tool_by_name("computer_action_preview")

    result = await tool.ainvoke(
        {
            "action": "type_text",
            "payload_json": '{"text":"hello"}',
        }
    )

    assert "action: type_text" in result
    assert "risk: medium" in result
    assert "requires explicit approval" in result


def test_high_quality_computer_tools_are_registered() -> None:
    registry = tool_registry(
        None,
        source_message_handle="msg-1",
        requester_number="+15551110000",
        run_id="run-1",
    )

    assert "computer_observe" in registry
    assert "computer_plan" in registry
    assert "computer_action_preview" in registry
    assert "workspace_status" in registry
    assert "workspace_diff" in registry
    assert "computer_observe" in OWNER_ONLY_TOOLS
    assert "workspace_status" in OWNER_ONLY_TOOLS
