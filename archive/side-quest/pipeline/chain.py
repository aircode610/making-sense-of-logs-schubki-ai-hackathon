"""Wire the bricks into one LangChain pipeline and run it with tracing.

    {qid, job, question} -> Pattern -> Evidence -> Verdict -> Finding
Each step only adds its own key to the example dict (RunnablePassthrough.assign), so every trace row shows
exactly what that brick received and produced.
"""
from langchain_core.runnables import RunnableLambda, RunnablePassthrough

from pipeline import bricks
from pipeline.trace import TraceHandler


def build(ctx: bricks.Ctx):
    step = lambda fn, name: RunnableLambda(lambda x: fn(x, ctx)).with_config(run_name=name)  # noqa: E731
    return (RunnablePassthrough.assign(pattern=step(bricks.pattern_brick, "Pattern"))
            | RunnablePassthrough.assign(evidence=step(bricks.evidence_brick, "Evidence"))
            | RunnablePassthrough.assign(verdict=step(bricks.verdict_brick, "Verdict"))
            | RunnablePassthrough.assign(finding=step(bricks.finding_brick, "Finding")))


def run(chain, x: dict, ctx: bricks.Ctx, run_id: str, trace: bool = True) -> dict:
    cfg = {"callbacks": [TraceHandler(ctx.conn, ctx.schema, run_id, x["qid"])]} if trace else {}
    return chain.invoke(x, config=cfg)
