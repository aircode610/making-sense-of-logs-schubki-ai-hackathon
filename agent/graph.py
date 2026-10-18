"""The agent (LangGraph). Same tools as Claude (our MCP server); the database searches and counts, the LLM explains.

              ┌─► gather_engineer ─┐
    route ────┼─► gather_lead ─────┼─► handover ─► composer ─► END
              └─► gather_manager ──┘               (compose ─► check ─► revise ≤ 1)

route      role given, else Jev picks it (calibrated choice in SereneDB; LLM fallback)
gather_*   one prebuilt ReAct agent per role (LangChain `create_agent`, the successor of LangGraph's
           `create_react_agent`): the role's tool subset + evidence recipe, parallel tool calls, middleware:
           CoverageMiddleware (role checklist: nudge back to the model while required evidence is missing) and
           ToolCallLimitMiddleware (caps tool calls per turn)
handover   every tool result envelope → evidence ledger keyed by evidence_id
composer   its own subgraph: compose (structured AnswerCard from the ledger only) → check (deterministic claim checker:
           numbers ⊂ cited results, forbidden claims, checklist) → one revision round

Baseline (the brief's reference design): `build_baseline` = `create_agent` with all tools and a plain role prompt.
"""
import asyncio
import json
import os
from typing import Annotated, Any, Literal, Optional, TypedDict

import psycopg
from langchain.agents import AgentState, create_agent
from langchain.agents.middleware import AgentMiddleware, ToolCallLimitMiddleware, hook_config
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.runtime import Runtime
from langgraph.types import Command
from pydantic import BaseModel
from typing_extensions import NotRequired

from agent import prompts
from agent.card import AnswerCard, Role
from agent.checker import check_card, feedback, ledger_json, missing_tools
from agent.support import jev_support

MAX_TOOL_CALLS = 14      # whole run: coverage stops nudging beyond this (plan 011: more atomic tools)
TURN_TOOL_CALLS = 12     # per gather turn (ToolCallLimitMiddleware run_limit resets on each nudge)
MAX_NUDGES = 2
MAX_REVISIONS = 1
# Per-role tool subsets (plan 011): atomic tools, each role sees only the ones its recipe uses (selection stays sharp).
ROLE_TOOLS = {
    "engineer": ["describe_corpus", "search_logs", "get_context", "suggest_terms", "facet", "rate_vs_baseline",
                 "value_outliers", "burst_timeline", "pattern_history", "spread", "precursors", "distinctive_terms",
                 "top_entities", "request_timeline"],
    "lead": ["describe_corpus", "top_patterns", "trend", "count_by", "rollup", "heatmap", "whats_new", "check_watchlist",
             "find_patterns", "similar_patterns", "co_occurrence", "periodicity", "search_logs"],
    "manager": ["describe_corpus", "priority_table", "reliability_trend", "team_risk", "rollup", "count_by",
                "top_patterns", "trend", "whats_new", "check_watchlist"],
}
# The baseline (brief's reference design) gets every read-only corpus tool; workspace / remote write tools excluded.
BASELINE_EXCLUDE = {"create_focus_index", "drop_focus_index", "remote_index", "explain_tool"}


def make_model():
    # Current Claude models take no custom temperature; determinism comes from the recipes + the checker, not sampling.
    return init_chat_model(os.environ.get("AGENT_MODEL", "anthropic:claude-sonnet-5-5"), max_tokens=8000)


def parse_envelope(msg: ToolMessage) -> Optional[dict]:
    """MCP tool results arrive as text blocks holding our JSON envelope."""
    content = msg.content
    text = "".join(b.get("text", "") for b in content if isinstance(b, dict)) if isinstance(content, list) else str(content)
    try:
        env = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    return env if isinstance(env, dict) and "evidence_id" in env else None


def tools_called(messages: list[AnyMessage]) -> list[str]:
    return [m.name for m in messages if isinstance(m, ToolMessage) and m.name]


# ---------------------------------------------------------------- gatherer: prebuilt ReAct agent + coverage middleware

class GatherState(AgentState):
    nudges: NotRequired[int]


class CoverageMiddleware(AgentMiddleware[GatherState]):
    """When the model stops calling tools while the role checklist still misses evidence, send it back once more."""
    state_schema = GatherState

    def __init__(self, role: str):
        super().__init__()
        self.role = role

    @hook_config(can_jump_to=["model"])
    def after_model(self, state: GatherState, runtime: Runtime) -> dict[str, Any] | None:
        last = state["messages"][-1]
        if not isinstance(last, AIMessage) or last.tool_calls:
            return None
        called = tools_called(state["messages"])
        missing = missing_tools(self.role, set(called))
        if not missing or state.get("nudges", 0) >= MAX_NUDGES or len(called) >= MAX_TOOL_CALLS:
            return None
        nudge = (f"The {self.role} recipe still needs evidence from: {', '.join(missing)}. "
                 f"Call it now (parallel calls allowed), then reply READY.")
        return {"messages": [HumanMessage(nudge)], "nudges": state.get("nudges", 0) + 1, "jump_to": "model"}


def build_gatherer(role: str, tools: list[BaseTool], model):
    by_name = {t.name: t for t in tools}
    system = prompts.GATHER_SYSTEM.format(recipe=prompts.RECIPES[role], corpus=prompts.corpus(), rules=prompts.RULES)
    return create_agent(model, [by_name[n] for n in ROLE_TOOLS[role] if n in by_name], system_prompt=system,
                        middleware=[CoverageMiddleware(role), ToolCallLimitMiddleware(run_limit=TURN_TOOL_CALLS)],
                        name=f"gather_{role}")


# ---------------------------------------------------------------- composer: compose → check → (revise) subgraph

class ComposerState(TypedDict, total=False):
    question: str
    role: Role
    ledger: dict[str, dict]
    tools_used: list[str]
    card: Optional[dict]
    check: Optional[dict]
    revisions: int


def build_composer(model):
    async def compose(state: ComposerState) -> dict:
        role = state["role"]
        system = prompts.COMPOSE_SYSTEM.format(role=role, role_card=prompts.ROLE_CARD[role])
        msgs = [SystemMessage(system),
                HumanMessage(f"Question: {state['question']}\n\nEvidence ledger:\n{ledger_json(state.get('ledger', {}))}")]
        if state.get("card") and state.get("check"):  # revision round
            msgs += [AIMessage(json.dumps(state["card"], ensure_ascii=False)),
                     HumanMessage("The claim checker rejected parts of this card. Fix exactly these and return the "
                                  "full corrected card:\n" + feedback(state["check"]))]
        card = await model.with_structured_output(AnswerCard, method="json_schema").ainvoke(msgs)
        return {"card": card.model_dump()}

    def check(state: ComposerState) -> Command[Literal["compose", "__end__"]]:
        report = check_card(state["card"], state.get("ledger", {}), state["role"], set(state.get("tools_used", [])))
        report["revision"] = state.get("revisions", 0)
        if not report["passed"] and state.get("revisions", 0) < MAX_REVISIONS:
            return Command(goto="compose", update={"check": report, "revisions": state.get("revisions", 0) + 1})
        # final card: per-fact Jev support probability (computed, shown next to each fact; plan 011)
        report["jev_support"] = jev_support(state["card"], state.get("ledger", {}))
        return Command(goto=END, update={"check": report})

    g = StateGraph(ComposerState)
    g.add_node("compose", compose)
    g.add_node("check", check)
    g.add_edge(START, "compose")
    g.add_edge("compose", "check")
    return g.compile(name="composer")


# ---------------------------------------------------------------- parent graph

class State(TypedDict, total=False):
    question: str
    role: Optional[Role]
    route: dict                                   # how the role was chosen (given / jev probabilities / llm)
    messages: Annotated[list[AnyMessage], add_messages]
    nudges: int
    ledger: dict[str, dict]                       # evidence_id → tool result envelope (sql, scope, totals, rows)
    tools_used: list[str]
    card: Optional[dict]
    check: Optional[dict]
    revisions: int


def jev_route(question: str) -> Optional[dict]:
    """Role via Jev (choice with calibrated probabilities), run inside SereneDB. Error dict if unavailable."""
    opts = ", ".join("{label: '%s', description: '%s'}" % (o["label"], o["description"].replace("'", "''"))
                     for o in prompts.ROUTE_OPTIONS)
    sql = (f"SELECT (r).choice AS choice, (r).confidence AS confidence, to_json((r).probabilities) AS probabilities "
           f"FROM (SELECT ai_system_one(%(q)s, '{prompts.ROUTE_QUESTION}', choice := [{opts}]) AS r)")
    try:
        with psycopg.connect(host=os.getenv("PGHOST", "localhost"), port=os.getenv("PGPORT", "7890"),
                             user=os.getenv("PGUSER", "postgres"), dbname=os.getenv("PGDATABASE", "postgres"),
                             autocommit=True) as c:
            choice, conf, probs = c.execute(sql, {"q": question}).fetchone()
    except Exception as e:  # noqa: BLE001 (any DB / API failure → fallback)
        return {"error": str(e)[:200]}
    probs = probs if isinstance(probs, list) else json.loads(probs)
    return {"source": "jev", "role": choice, "confidence": round(conf, 3),
            "probabilities": {p["value"]: round(p["probability"], 3) for p in probs}}


class RoleChoice(BaseModel):
    role: Role


def build_graph(tools: list[BaseTool], model=None):
    model = model or make_model()

    async def route(state: State) -> dict:
        if state.get("role"):
            return {"route": {"source": "given", "role": state["role"]}}
        r = await asyncio.to_thread(jev_route, state["question"])
        if r and r.get("role") in prompts.RECIPES:
            return {"role": r["role"], "route": r}
        llm = await model.with_structured_output(RoleChoice, method="json_schema").ainvoke(
            [SystemMessage(prompts.ROUTE_QUESTION + " " + json.dumps(prompts.ROUTE_OPTIONS)),
             HumanMessage(state["question"])])
        return {"role": llm.role, "route": {"source": "llm_fallback", "role": llm.role, "jev": r}}

    def to_gatherer(state: State) -> str:
        return f"gather_{state['role']}"

    def handover(state: State) -> dict:
        tool_msgs = [m for m in state["messages"] if isinstance(m, ToolMessage)]
        ledger = {env["evidence_id"]: env for env in map(parse_envelope, tool_msgs) if env}
        return {"ledger": ledger, "tools_used": tools_called(state["messages"])}

    g = StateGraph(State)
    g.add_node("route", route)
    for role in ROLE_TOOLS:
        g.add_node(f"gather_{role}", build_gatherer(role, tools, model))
        g.add_edge(f"gather_{role}", "handover")
    g.add_node("handover", handover)
    g.add_node("composer", build_composer(model))
    g.add_edge(START, "route")
    g.add_conditional_edges("route", to_gatherer, [f"gather_{r}" for r in ROLE_TOOLS])
    g.add_edge("handover", "composer")
    g.add_edge("composer", END)
    return g.compile(name="logs-agent")


def build_baseline(tools: list[BaseTool], role: str, model=None):
    """The brief's reference design: a ReAct agent with all tools and a role prompt, free-text answer."""
    tools = [t for t in tools if t.name not in BASELINE_EXCLUDE]
    return create_agent(model or make_model(), tools,
                        system_prompt=prompts.BASELINE_SYSTEM.format(role=role, corpus=prompts.corpus()),
                        name="baseline-react")
