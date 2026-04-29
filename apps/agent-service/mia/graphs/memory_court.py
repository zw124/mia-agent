import json
from typing import Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from mia.llm import build_chat_model
from mia.models import MEMORY_COURT_ACTIONS, AdversarialRound, CourtProposal, JudgeDecision
from mia.settings import Settings


class MemoryCourtState(TypedDict):
    run_id: str
    local_date: str
    memories: list[dict[str, Any]]
    proposals: list[dict[str, Any]]
    adversarial_rounds: list[dict[str, Any]]
    judge_decisions: list[dict[str, Any]]
    round: int


def _json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


async def consolidator(state: MemoryCourtState, settings: Settings) -> dict:
    candidates = [
        memory
        for memory in state["memories"]
        if memory.get("tier") != "permanent"
        and (memory.get("importanceScore", 1) < 0.35 or memory.get("decayRate", 0) > 0.25)
    ]
    llm = build_chat_model(settings)
    response = await llm.ainvoke(
        [
            SystemMessage(
                content=(
                    "You are Mia's Memory Court Consolidator. Find low-value or duplicate memories. "
                    "Permanent memories must not be deleted. Return strict JSON array of proposals. "
                    f"Each proposal fields: memory_ids, action({MEMORY_COURT_ACTIONS}), "
                    "proposed_content nullable, reason."
                )
            ),
            HumanMessage(content=_json_dump(candidates)),
        ]
    )
    try:
        raw = json.loads(str(response.content))
        proposals = [CourtProposal.model_validate(item).model_dump() for item in raw]
    except Exception:
        proposals = [
            CourtProposal(
                memory_ids=[str(memory["id"])],
                action="delete",
                proposed_content=None,
                reason="Low importance or high decay candidate selected by deterministic fallback.",
            ).model_dump()
            for memory in candidates
        ]
    return {"proposals": proposals}


async def adversarial_agent(state: MemoryCourtState, settings: Settings) -> dict:
    llm = build_chat_model(settings)
    response = await llm.ainvoke(
        [
            SystemMessage(
                content=(
                    "You are Mia's adversarial memory defender. For each proposal, argue whether "
                    "the memory should be kept. Return strict JSON array with fields: "
                    "proposal_index, argument, should_keep."
                )
            ),
            HumanMessage(
                content=_json_dump(
                    {
                        "round": state["round"] + 1,
                        "memories": state["memories"],
                        "proposals": state["proposals"],
                    }
                )
            ),
        ]
    )
    try:
        raw = json.loads(str(response.content))
        arguments = [AdversarialRound.model_validate(item).model_dump() for item in raw]
    except Exception:
        arguments = [
            AdversarialRound(
                proposal_index=index,
                argument="No strong preservation reason found by deterministic fallback.",
                should_keep=False,
            ).model_dump()
            for index, _proposal in enumerate(state["proposals"])
        ]
    return {
        "adversarial_rounds": state["adversarial_rounds"] + arguments,
        "round": state["round"] + 1,
    }


def should_continue_debate(state: MemoryCourtState) -> str:
    return "adversarial_agent" if state["round"] < 2 else "judge"


async def judge(state: MemoryCourtState, settings: Settings) -> dict:
    llm = build_chat_model(settings)
    response = await llm.ainvoke(
        [
            SystemMessage(
                content=(
                    "You are Mia's Memory Court judge. Decide final action for every proposal after "
                    "two adversarial rounds. Permanent memories must only be keep or manual_review. "
                    f"Return strict JSON array fields: memory_ids, action({MEMORY_COURT_ACTIONS}), "
                    "final_content nullable, reason."
                )
            ),
            HumanMessage(
                content=_json_dump(
                    {
                        "memories": state["memories"],
                        "proposals": state["proposals"],
                        "adversarial_rounds": state["adversarial_rounds"],
                    }
                )
            ),
        ]
    )
    try:
        raw = json.loads(str(response.content))
        decisions = [JudgeDecision.model_validate(item).model_dump() for item in raw]
    except Exception:
        decisions = [
            JudgeDecision(
                memory_ids=proposal["memory_ids"],
                action="manual_review" if proposal["action"] == "merge" else proposal["action"],
                final_content=proposal.get("proposed_content"),
                reason="Judge fallback adopted consolidator action except merges require review.",
            ).model_dump()
            for proposal in state["proposals"]
        ]
    return {"judge_decisions": decisions}


def build_memory_court_graph(settings: Settings):
    async def consolidator_node(state: MemoryCourtState) -> dict:
        return await consolidator(state, settings)

    async def adversarial_node(state: MemoryCourtState) -> dict:
        return await adversarial_agent(state, settings)

    async def judge_node(state: MemoryCourtState) -> dict:
        return await judge(state, settings)

    graph = StateGraph(MemoryCourtState)
    graph.add_node("consolidator", consolidator_node)
    graph.add_node("adversarial_agent", adversarial_node)
    graph.add_node("judge", judge_node)

    graph.add_edge(START, "consolidator")
    graph.add_edge("consolidator", "adversarial_agent")
    graph.add_conditional_edges(
        "adversarial_agent",
        should_continue_debate,
        {"adversarial_agent": "adversarial_agent", "judge": "judge"},
    )
    graph.add_edge("judge", END)
    return graph.compile()
