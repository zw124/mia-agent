from dataclasses import dataclass
from typing import Any, Literal

from langchain_core.messages import HumanMessage, SystemMessage

from mia.integrations.convex import ConvexClient
from mia.llm import build_chat_model
from mia.settings import Settings
from mia.user_profile import load_user_profile

OrchestraPhase = Literal["scout", "plan", "build", "verify", "review"]


@dataclass(frozen=True)
class CodingPhaseSpec:
    name: OrchestraPhase
    agent_name: str
    objective: str
    output_contract: str


CODING_PHASES: tuple[CodingPhaseSpec, ...] = (
    CodingPhaseSpec(
        name="scout",
        agent_name="scout",
        objective=(
            "Map the request. Identify whether this is a question, debugging task, refactor, "
            "implementation request, architecture decision, or verification task."
        ),
        output_contract="Return the task type, likely files/systems involved if inferable, missing context, and risk level.",
    ),
    CodingPhaseSpec(
        name="plan",
        agent_name="planner",
        objective=(
            "Create the smallest high-leverage execution plan. Do not over-plan simple work. "
            "Split complex work into checkpoints and define stop conditions."
        ),
        output_contract="Return 2-6 concrete steps, required tools or permissions, and what can be skipped.",
    ),
    CodingPhaseSpec(
        name="build",
        agent_name="builder",
        objective=(
            "Convert the plan into the strongest user-facing engineering answer. If code changes are needed, "
            "describe the exact patch strategy rather than pretending files were edited."
        ),
        output_contract="Return the proposed implementation, commands, code snippets, or direct answer needed by the user.",
    ),
    CodingPhaseSpec(
        name="verify",
        agent_name="verifier",
        objective=(
            "Stress-test the build output. Look for broken assumptions, missing tests, unsafe actions, "
            "and whether a cheaper path exists."
        ),
        output_contract="Return verification steps, expected signals, and unresolved risks.",
    ),
    CodingPhaseSpec(
        name="review",
        agent_name="reviewer",
        objective=(
            "Compress all prior work into a concise final answer. Preserve important caveats. "
            "Never mention internal phase names unless useful."
        ),
        output_contract="Return only the final message Mia should send to the user.",
    ),
)


ORCHESTRA_SYSTEM = """You are Mia's coding orchestra.
You specialize in programming, debugging, code review, architecture, agent design, and repo operations.

Operating rules:
- Use the current phase objective only; do not jump into unrelated work.
- Keep simple tasks simple. A one-question answer should not become a full project plan.
- Never claim you edited files, ran commands, opened apps, or deployed anything unless tool logs prove it.
- If filesystem, shell, browser, or computer control is required, explicitly say what permission/tool path is needed.
- Prefer bounded execution, clear stop conditions, and verification over open-ended loops.
- Treat prior phase notes as evidence, not authority; correct them when needed.
"""

PHASE_PROGRESS: dict[OrchestraPhase, str] = {
    "scout": "我先快速看清任务边界，不会直接乱跑完整 loop。",
    "plan": "我在压缩执行路径：只保留必要步骤。",
    "build": "我开始整理可执行方案/答案。",
    "verify": "我在做最后的风险和验证检查。",
    "review": "我在压缩成最终回复。",
}


def _format_memory_context(memories: list[dict[str, Any]]) -> str:
    if not memories:
        return "No relevant stored memories."
    return "\n".join(
        f"- [{memory.get('tier')}/{memory.get('segment')}] {memory.get('content')}"
        for memory in memories
    )


def _format_phase_notes(notes: list[tuple[str, str]]) -> str:
    if not notes:
        return "No prior phase notes."
    return "\n\n".join(f"{name}:\n{content}" for name, content in notes)


async def _run_phase(
    *,
    phase: CodingPhaseSpec,
    state: dict[str, Any],
    settings: Settings,
    memory_context: str,
    prior_notes: list[tuple[str, str]],
) -> str:
    llm = build_chat_model(settings, temperature=0.1 if phase.name != "review" else 0.2)
    response = await llm.ainvoke(
        [
            SystemMessage(
                content=(
                    f"{ORCHESTRA_SYSTEM}\n\n"
                    f"Current specialist: {phase.agent_name}\n"
                    f"Objective: {phase.objective}\n"
                    f"Output contract: {phase.output_contract}"
                )
            ),
            HumanMessage(
                content=(
                    f"Stored memory context:\n{memory_context}\n\n"
                    f"Local user.md profile:\n{load_user_profile()}\n\n"
                    f"User message:\n{state['message']}\n\n"
                    f"Prior phase notes:\n{_format_phase_notes(prior_notes)}"
                )
            ),
        ]
    )
    return str(response.content).strip()


def _select_phases(message: str, depth: str = "standard") -> tuple[CodingPhaseSpec, ...]:
    text = message.lower()
    simple_markers = (
        "what is",
        "explain",
        "解释",
        "什么意思",
        "怎么理解",
        "区别",
    )
    action_markers = (
        "fix",
        "debug",
        "refactor",
        "implement",
        "review",
        "test",
        "修复",
        "调试",
        "重构",
        "实现",
        "添加",
        "检查",
        "审查",
    )

    if any(marker in text for marker in simple_markers) and not any(
        marker in text for marker in action_markers
    ):
        return (CODING_PHASES[0], CODING_PHASES[-1])
    if depth == "brief":
        return (CODING_PHASES[0], CODING_PHASES[-1])
    if depth == "deep":
        return CODING_PHASES
    return (CODING_PHASES[0], CODING_PHASES[1], CODING_PHASES[2], CODING_PHASES[-1])


async def run_coding_orchestra(
    state: dict[str, Any],
    settings: Settings,
    convex: ConvexClient,
) -> str:
    memory_context = _format_memory_context(list(state.get("relevant_memories", [])))
    phase_notes: list[tuple[str, str]] = []
    selected_phases = _select_phases(
        str(state["message"]),
        str(state.get("orchestration_depth") or "standard"),
    )

    await convex.record_agent_spawn(
        run_id=state["run_id"],
        message_handle=state["message_handle"],
        parent_agent="message_classifier",
        name="coding_orchestra",
        objective="Route a programming request through bounded specialist phases.",
        allowed_tools=[],
        status="running",
    )

    try:
        for phase in selected_phases:
            progress_callback = state.get("progress_callback")
            if callable(progress_callback) and phase.name != "review":
                await progress_callback(PHASE_PROGRESS[phase.name])
            await convex.log_thought(
                message_handle=state["message_handle"],
                run_id=state["run_id"],
                node=f"coding_orchestra.{phase.name}",
                content=f"Starting {phase.agent_name}: {phase.objective}",
                active_agent=phase.agent_name,
            )
            output = await _run_phase(
                phase=phase,
                state=state,
                settings=settings,
                memory_context=memory_context,
                prior_notes=phase_notes,
            )
            phase_notes.append((phase.name, output))
            await convex.log_thought(
                message_handle=state["message_handle"],
                run_id=state["run_id"],
                node=f"coding_orchestra.{phase.name}",
                content=output[:2000],
                active_agent=phase.agent_name,
            )
    except Exception as error:
        await convex.update_agent_spawn_status(
            run_id=state["run_id"],
            name="coding_orchestra",
            status="failed",
            error=str(error),
        )
        raise

    final_reply = phase_notes[-1][1].strip() if phase_notes else "I need more detail to help with that code task."
    await convex.update_agent_spawn_status(
        run_id=state["run_id"],
        name="coding_orchestra",
        status="completed",
        result=final_reply,
    )
    return final_reply
