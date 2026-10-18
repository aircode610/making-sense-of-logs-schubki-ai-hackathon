"""Export a recorded MCP session as ONE static HTML page (plan 017): the session report with its data, the Verify
result of every step (re-run now on the read-only role) and the Jev support baked in, so it opens without a server.

  uv run python scripts/export_report.py <session id> docs/investigation/report.html
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "mcp_server"))
import session  # noqa: E402


def main(sid: str, out: str) -> None:
    data = session.load(sid)
    ans = (data.get("report") or {}).get("answer") or ""
    data["numbers"] = session.numbers_check(ans, data["calls"]) if ans else []
    data["sections"] = session.sections(ans) if ans else []
    try:
        data["jev"] = session.jev_patterns(data["calls"])
    except Exception:  # noqa: BLE001
        data["jev"] = {}
    try:
        support = session.jev_section_support(sid, data["sections"], data["calls"]) if data["sections"] else []
    except Exception:  # noqa: BLE001
        support = []
    verify = {}
    for i in range(len(data["calls"])):
        try:
            verify[i] = session.verify(sid, i)
        except Exception as e:  # noqa: BLE001
            verify[i] = {"status": "error", "detail": str(e)[:300]}
    import jev_guide
    snap = json.dumps({"api": data, "verify": verify, "support": support, "jevq": jev_guide.guide()}, default=str).replace("</", "<\\/")
    html = (ROOT / "mcp_server/report.html").read_text()
    html = html.replace("<script>\nconst $", f"<script>window.SNAPSHOT = {snap};</script>\n<script>\nconst $", 1)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(html)
    ok = sum(v.get("status") == "match" for v in verify.values())
    print(f"{out}: {len(data['calls'])} steps, {ok} verified identical, "
          f"{sum(n['step'] is not None for n in data['numbers'])}/{len(data['numbers'])} numbers found in results")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
