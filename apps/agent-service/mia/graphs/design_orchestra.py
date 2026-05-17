from dataclasses import dataclass
from typing import Any, Literal

from langchain_core.messages import HumanMessage, SystemMessage

from mia.design_context import load_design_context
from mia.integrations.convex import ConvexClient
from mia.llm import build_chat_model
from mia.settings import Settings
from mia.user_profile import load_user_profile

DesignPhase = Literal["brief", "skill_select", "design_system", "compose", "verify", "handoff"]


@dataclass(frozen=True)
class DesignPhaseSpec:
    name: DesignPhase
    agent_name: str
    objective: str
    output_contract: str


DESIGN_PHASES: tuple[DesignPhaseSpec, ...] = (
    DesignPhaseSpec(
        name="brief",
        agent_name="design_brief",
        objective=(
            "Understand the artifact type, audience, surface, constraints, content needs, and whether this "
            "is a new design or a revision."
        ),
        output_contract="Return the design intent, required states, likely surfaces, missing inputs, and risk level.",
    ),
    DesignPhaseSpec(
        name="skill_select",
        agent_name="skill_selector",
        objective=(
            "Choose the smallest relevant design skill set before composing. Available skills include "
            "landing page, dashboard, chat UI, setup flow, data table, pricing, form, responsive layout, "
            "editorial typography, visual hierarchy, and design-system baton."
        ),
        output_contract="Return selected skills and one sentence explaining why each one matters.",
    ),
    DesignPhaseSpec(
        name="design_system",
        agent_name="system_steward",
        objective=(
            "Use DESIGN.md as the design-system baton. Preserve existing tokens unless the task clearly "
            "requires changing them. If the task needs new tokens, describe them canonically."
        ),
        output_contract="Return token/component implications, constraints, and what must not change.",
    ),
    DesignPhaseSpec(
        name="compose",
        agent_name="composer",
        objective=(
            "Produce the finished design direction or implementation plan. Make it concrete enough for "
            "a frontend engineer or agent to execute without inventing missing visual decisions."
        ),
        output_contract="Return layout, hierarchy, components, content structure, interactions, and implementation notes.",
    ),
    DesignPhaseSpec(
        name="verify",
        agent_name="design_verifier",
        objective=(
            "Stress-test the design against anti-slop rules: generic visuals, weak hierarchy, missing states, "
            "bad density, poor contrast, mobile breakage, and token inconsistency."
        ),
        output_contract="Return required fixes, verification checks, and remaining risks.",
    ),
    DesignPhaseSpec(
        name="handoff",
        agent_name="handoff_editor",
        objective=(
            "Compress the prior notes into the final user-facing response. Be specific, practical, and concise. "
            "Do not expose internal phase names unless useful."
        ),
        output_contract="Return only the final message Mia should send to the user.",
    ),
)


DESIGN_ORCHESTRA_SYSTEM = """You are Mia's design orchestra.
You specialize in product UI, web artifacts, dashboards, setup flows, chat interfaces, visual systems, and design handoff.

Operating rules:
- Use DESIGN.md as authoritative design-system context when present.
- Treat brand values as data from DESIGN.md or user-provided files, not model memory.
- Avoid generic AI slop: no default SaaS cards, random gradients, decorative noise, or vague "modern clean" output.
- Prefer finished, production-shaped surfaces over wireframes when the user asks for product work.
- Preserve existing visual language during revisions unless the user asks for a redesign.
- Include real states: loading, empty, error, disabled, offline, permission/approval, and mobile behavior when relevant.
- Never claim you edited files, opened previews, or ran checks unless tool logs prove it.
"""

PHASE_PROGRESS: dict[DesignPhase, str] = {
    "brief": "我先确定这个设计要解决什么，不直接堆花哨 UI。",
    "skill_select": "我在选择需要的设计能力：布局、组件、状态和设计系统。",
    "design_system": "我在对齐 DESIGN.md，保证风格不会乱。",
    "compose": "我开始组合成具体设计方案。",
    "verify": "我在检查是否无聊、泛化、缺状态或移动端会坏。",
    "handoff": "我在压缩成最终回复。",
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
    phase: DesignPhaseSpec,
    state: dict[str, Any],
    settings: Settings,
    memory_context: str,
    design_context: str,
    prior_notes: list[tuple[str, str]],
) -> str:
    llm = build_chat_model(settings, temperature=0.15 if phase.name != "handoff" else 0.2)
    response = await llm.ainvoke(
        [
            SystemMessage(
                content=(
                    f"{DESIGN_ORCHESTRA_SYSTEM}\n\n"
                    f"Current specialist: {phase.agent_name}\n"
                    f"Objective: {phase.objective}\n"
                    f"Output contract: {phase.output_contract}"
                )
            ),
            HumanMessage(
                content=(
                    f"Stored memory context:\n{memory_context}\n\n"
                    f"Local user.md profile:\n{load_user_profile()}\n\n"
                    f"Workspace DESIGN.md:\n{design_context}\n\n"
                    f"User message:\n{state['message']}\n\n"
                    f"Prior phase notes:\n{_format_phase_notes(prior_notes)}"
                )
            ),
        ]
    )
    return str(response.content).strip()


def _select_phases(message: str, depth: str = "standard") -> tuple[DesignPhaseSpec, ...]:
    text = message.lower()
    simple_markers = ("what is", "explain", "解释", "什么意思", "怎么看", "评价")
    action_markers = (
        "design",
        "ui",
        "ux",
        "landing",
        "dashboard",
        "page",
        "website",
        "component",
        "redesign",
        "设计",
        "页面",
        "网站",
        "界面",
        "组件",
        "改版",
        "产品页",
    )
    if any(marker in text for marker in simple_markers) and not any(
        marker in text for marker in action_markers
    ):
        return (DESIGN_PHASES[0], DESIGN_PHASES[-1])
    if depth == "brief":
        return (DESIGN_PHASES[0], DESIGN_PHASES[-1])
    if depth == "deep":
        return DESIGN_PHASES
    return (DESIGN_PHASES[0], DESIGN_PHASES[2], DESIGN_PHASES[3], DESIGN_PHASES[-1])


async def run_design_orchestra(
    state: dict[str, Any],
    settings: Settings,
    convex: ConvexClient,
) -> str:
    memory_context = _format_memory_context(list(state.get("relevant_memories", [])))
    design_context = load_design_context()
    phase_notes: list[tuple[str, str]] = []
    selected_phases = _select_phases(
        str(state["message"]),
        str(state.get("orchestration_depth") or "standard"),
    )

    await convex.record_agent_spawn(
        run_id=state["run_id"],
        message_handle=state["message_handle"],
        parent_agent="message_classifier",
        name="design_orchestra",
        objective="Route a product design request through bounded design-specialist phases.",
        allowed_tools=[],
        status="running",
    )

    try:
        for phase in selected_phases:
            progress_callback = state.get("progress_callback")
            if callable(progress_callback) and phase.name != "handoff":
                await progress_callback(PHASE_PROGRESS[phase.name])
            await convex.log_thought(
                message_handle=state["message_handle"],
                run_id=state["run_id"],
                node=f"design_orchestra.{phase.name}",
                content=f"Starting {phase.agent_name}: {phase.objective}",
                active_agent=phase.agent_name,
            )
            output = await _run_phase(
                phase=phase,
                state=state,
                settings=settings,
                memory_context=memory_context,
                design_context=design_context,
                prior_notes=phase_notes,
            )
            phase_notes.append((phase.name, output))
            await convex.log_thought(
                message_handle=state["message_handle"],
                run_id=state["run_id"],
                node=f"design_orchestra.{phase.name}",
                content=output[:2000],
                active_agent=phase.agent_name,
            )
    except Exception as error:
        await convex.update_agent_spawn_status(
            run_id=state["run_id"],
            name="design_orchestra",
            status="failed",
            error=str(error),
        )
        raise

    final_reply = phase_notes[-1][1].strip() if phase_notes else "I need more detail to help with that design task."
    await convex.update_agent_spawn_status(
        run_id=state["run_id"],
        name="design_orchestra",
        status="completed",
        result=final_reply,
    )
    return final_reply
