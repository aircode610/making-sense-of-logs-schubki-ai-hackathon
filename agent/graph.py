"""The agent (LangGraph). Same tools as Claude (our MCP server); the database searches and counts, the LLM explains.

    route ─► gather ⇄ tools ─► coverage ─► compose ─► check ─► END
                ▲                  │          ▲         │
                └── nudge (≤ 2) ───┘          └─ revise ┘ (≤ 1)

route     role given, else Jev picks it (calibrated choice in SereneDB; LLM fallback)
gather    LLM with the role's tool subset + recipe; parallel tool calls
tools     runs the calls concurrently; every result envelope goes into the evidence ledger by evidence_id
coverage  deterministic role checklist (which tools must have run); missing → nudge back to gather
compose   LLM writes the AnswerCard (structured output) from the ledger only
check     deterministic claim checker (numbers ⊂ cited results, forbidden claims, checklist) → one revision round

Baseline (the brief's reference design): `build_baseline` = LangChain `create_agent` with the same tools.
"""
import asyncio
import json
import os
from typing import Annotated, Any, Literal, Optional, TypedDict

import psycopg
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Command
from pydantic import BaseModel

from agent import prompts
from agent.card import AnswerCard, Role
from agent.checker import check_card, feedback, ledger_json, missing_tools

MAX_TOOL_CALLS = 10
MAX_NUDGES = 2
MAX_REVISIONS = 1
ROLE_TOOLS = {
    "engineer": ["search_logs", "get_context", "count_by", "trend"],
    "lead": ["top_patterns", "trend", "count_by", "search_logs"],
    "manager": ["priority_table", "count_by", "top_patterns", "trend"],
}


def merge(a: dict, b: dict) -> dict:
    return {**(a or {}), **(b or {})}


class State(TypedDict, total=False):
    question: str
    role: Optional[Role]
    route: dict                                   # how the role was chosen (given / jev probabilities / llm)
    messages: Annotated[list[AnyMessage], add_messages]
    ledger: Annotated[dict[str, dict], merge]     # evidence_id → tool result envelope (sql, scope, totals, rows)
    tool_calls: int
    nudges: int
    card: Optional[dict]
    check: Optional[dict]
    revisions: int


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


def jev_route(question: str) -> Optional[dict]:
    """Role via Jev (choice with calibrated probabilities), run inside SereneDB. None if unavailable."""
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
    by_name = {t.name: t for t in tools}

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

    async def gather(state: State) -> dict:
        role = state["role"]
        llm = model.bind_tools([by_name[n] for n in ROLE_TOOLS[role] if n in by_name])
        system = prompts.GATHER_SYSTEM.format(recipe=prompts.RECIPES[role], corpus=prompts.CORPUS, rules=prompts.RULES)
        ai = await llm.ainvoke([SystemMessage(system)] + state["messages"])
        return {"messages": [ai]}

    async def run_tools(state: State) -> dict:
        calls = state["messages"][-1].tool_calls
        used = state.get("tool_calls", 0)
        allowed, refused = calls[: max(0, MAX_TOOL_CALLS - used)], calls[max(0, MAX_TOOL_CALLS - used):]

        async def one(call) -> ToolMessage:
            tool = by_name.get(call["name"])
            if tool is None:
                return ToolMessage(f"Unknown tool {call['name']}", tool_call_id=call["id"], status="error")
            try:
                return await tool.ainvoke({**call, "type": "tool_call"})
            except Exception as e:  # noqa: BLE001 (tool error → shown to the model, run continues)
                return ToolMessage(f"Tool error: {e}", tool_call_id=call["id"], name=call["name"], status="error")

        results = list(await asyncio.gather(*(one(c) for c in allowed)))
        results += [ToolMessage("Tool budget used up: answer with the evidence you have.", tool_call_id=c["id"],
                                name=c["name"], status="error") for c in refused]
        ledger = {env["evidence_id"]: env for env in map(parse_envelope, results) if env}
        return {"messages": results, "ledger": ledger, "tool_calls": used + len(allowed)}

    def after_gather(state: State) -> Literal["tools", "coverage"]:
        last = state["messages"][-1]
        return "tools" if isinstance(last, AIMessage) and last.tool_calls else "coverage"

    def coverage(state: State) -> Command[Literal["gather", "compose"]]:
        used = {ev["tool"] for ev in state.get("ledger", {}).values()}
        missing = missing_tools(state["role"], used)
        if missing and state.get("nudges", 0) < MAX_NUDGES and state.get("tool_calls", 0) < MAX_TOOL_CALLS:
            nudge = (f"The {state['role']} recipe still needs evidence from: {', '.join(missing)}. "
                     f"Call it now (parallel calls allowed), then reply READY.")
            return Command(goto="gather", update={"messages": [HumanMessage(nudge)], "nudges": state.get("nudges", 0) + 1})
        return Command(goto="compose")

    async def compose(state: State) -> dict:
        role = state["role"]
        system = prompts.COMPOSE_SYSTEM.format(role=role, role_card=prompts.ROLE_CARD[role])
        human = f"Question: {state['question']}\n\nEvidence ledger:\n{ledger_json(state.get('ledger', {}))}"
        msgs = [SystemMessage(system), HumanMessage(human)]
        if state.get("card") and state.get("check"):  # revision round
            msgs += [AIMessage(json.dumps(state["card"], ensure_ascii=False)),
                     HumanMessage("The claim checker rejected parts of this card. Fix exactly these and return the "
                                  "full corrected card:\n" + feedback(state["check"]))]
        card = await model.with_structured_output(AnswerCard, method="json_schema").ainvoke(msgs)
        return {"card": card.model_dump()}

    def check(state: State) -> Command[Literal["compose", "__end__"]]:
        used = {ev["tool"] for ev in state.get("ledger", {}).values()}
        report = check_card(state["card"], state.get("ledger", {}), state["role"], used)
        report["revision"] = state.get("revisions", 0)
        if not report["passed"] and state.get("revisions", 0) < MAX_REVISIONS:
            return Command(goto="compose", update={"check": report, "revisions": state.get("revisions", 0) + 1})
        return Command(goto=END, update={"check": report})

    g = StateGraph(State)
    g.add_node("route", route)
    g.add_node("gather", gather)
    g.add_node("tools", run_tools)
    g.add_node("coverage", coverage)
    g.add_node("compose", compose)
    g.add_node("check", check)
    g.add_edge(START, "route")
    g.add_edge("route", "gather")
    g.add_conditional_edges("gather", after_gather)
    g.add_edge("tools", "gather")
    g.add_edge("compose", "check")
    return g.compile(name="logs-agent")


def build_baseline(tools: list[BaseTool], role: str, model=None):
    """The brief's reference design: a ReAct agent with the same tools and a role prompt, free-text answer."""
    return create_agent(model or make_model(), tools, system_prompt=prompts.BASELINE_SYSTEM.format(role=role),
                        name="baseline-react")
