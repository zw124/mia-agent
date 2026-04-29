from mia.tools.registry import (
    AVAILABLE_TOOL_NAMES,
    TOOL_DESCRIPTIONS,
    public_tool_descriptions,
    tool_registry,
)


class ConvexDummy:
    pass


def test_tool_metadata_matches_registry() -> None:
    registry = tool_registry(ConvexDummy(), source_message_handle="msg-1")

    assert AVAILABLE_TOOL_NAMES == set(TOOL_DESCRIPTIONS)
    assert set(registry) == AVAILABLE_TOOL_NAMES


def test_public_tool_descriptions_use_metadata_order() -> None:
    expected = "\n".join(
        f"- {name}: {description}" for name, description in TOOL_DESCRIPTIONS.items()
    )

    assert public_tool_descriptions() == expected
