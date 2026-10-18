"""CLI for the loader (plan 016), the same code the MCP server's load_logs tool runs.

  uv run python -m loader load bgl openstack       the base corpus (download per the brief + our loaders + Jev)
  uv run python -m loader load ~/logs/app.log --name myapp [--year 2024]   any file: format auto-detected (lnav)
  uv run python -m loader remove myapp
  uv run python -m loader reload [names…]          drop and rebuild everything (load/reload.sh calls this)
  uv run python -m loader status
"""
import argparse
import json
import sys

from loader import core


def main() -> int:
    ap = argparse.ArgumentParser(prog="python -m loader", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("load", help="load datasets (catalog names) or log files")
    p.add_argument("sources", nargs="+")
    p.add_argument("--name", help="dataset name (one file only)")
    p.add_argument("--year", type=int, help="year for formats that log none")
    p.add_argument("--no-judge", action="store_true", help="skip live Jev judging of new data")
    p.add_argument("--confirm-large", action="store_true")
    r = sub.add_parser("remove")
    r.add_argument("name")
    rl = sub.add_parser("reload")
    rl.add_argument("names", nargs="*")
    sub.add_parser("status")
    a = ap.parse_args()
    if a.cmd == "load":
        if a.name and len(a.sources) > 1:
            ap.error("--name needs exactly one source")
        ok = True
        for s in a.sources:
            rep = core.load(s, a.name, a.year, "never" if a.no_judge else "auto", a.confirm_large)
            print(json.dumps(rep, indent=1, default=str))
            ok &= bool(rep.get("ok"))
        return 0 if ok else 2
    c = core.connect()
    if a.cmd == "remove":
        core.remove(c, a.name)
    elif a.cmd == "reload":
        core.reload(a.names or None)
    else:
        core.ensure_schema(c)
        print(json.dumps({"datasets": core.loaded(c), "secrets": sorted(core.jev.secrets(c)),
                          "version": c.execute("SELECT version()").fetchone()[0]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
