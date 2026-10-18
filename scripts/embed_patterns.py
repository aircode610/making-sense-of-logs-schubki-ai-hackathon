"""Embed every pattern template with ai_embed INSIDE SereneDB (plan 011) and store the vectors in the repo.

  .venv/bin/python scripts/embed_patterns.py        → data/pattern_vectors.parquet (committed)
  .venv/bin/python scripts/embed_patterns.py <ds>   → data/pattern_vectors_<ds>.parquet (plan 057: one dataset only,
                                                       e.g. after scripts/ingest.sh; the shared file stays untouched)
load/97_pattern_vectors.sql loads it into the `pattern_index` search table (text + IVF vector index), so semantic tools
work from a clean checkout without a key; only find_patterns(mode='semantic') embeds the QUERY text live.
Model: gemini-embedding-001 at 768 dimensions (OpenAI-compatible secret `gemini`, ./docker/secrets.sh). ~1.6k
templates = ~16 embedding requests (100 texts per request), a few seconds. Text embedded = 'component: template'.
"""
import os
import sys
import time
from pathlib import Path

import psycopg
import pyarrow as pa
import pyarrow.parquet as pq
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parent.parent
MODEL, DIM = "gemini-embedding-001", 768


def main(datasets: list[str]) -> None:
    env = os.environ.get
    with psycopg.connect(host=env("PGHOST", "localhost"), port=env("PGPORT", "7890"), user=env("PGUSER", "postgres"),
                         dbname=env("PGDATABASE", "postgres"), autocommit=True, row_factory=dict_row) as c:
        c.execute("SET sdb_scan_split = 'never'")
        t0 = time.time()
        # literal list (a bound list in = ANY(...) fails in SereneDB); names are checked against the registry
        known = {r["dataset"] for r in c.execute("SELECT dataset FROM datasets").fetchall()}
        if set(datasets) - known:
            sys.exit(f"unknown dataset(s): {sorted(set(datasets) - known)}")
        where = ("WHERE dataset IN (" + ", ".join("'" + d + "'" for d in datasets) + ") ") if datasets else ""
        rows = c.execute(
            f"SELECT dataset, component, template, pattern_id, "
            f"ai_embed(coalesce(component, '') || ': ' || template, '{MODEL}', 'gemini', {DIM}) AS emb "
            f"FROM patterns {where}ORDER BY dataset, pattern_id").fetchall()
        bad = [r for r in rows if not r["emb"] or len(r["emb"]) != DIM]
        if bad:
            sys.exit(f"{len(bad)} templates without a {DIM}-dim embedding")
        table = pa.table({"dataset": [r["dataset"] for r in rows], "component": [r["component"] for r in rows],
                          "template": [r["template"] for r in rows], "pattern_id": [r["pattern_id"] for r in rows],
                          "emb": pa.array([list(map(float, r["emb"])) for r in rows], type=pa.list_(pa.float32()))})
        out = ROOT / ("data/pattern_vectors.parquet" if not datasets else f"data/pattern_vectors_{'_'.join(datasets)}.parquet")
        pq.write_table(table, out, compression="zstd")
        print(f"{len(rows)} templates embedded with {MODEL} ({DIM} dims) in {time.time() - t0:.1f} s → "
              f"{out.relative_to(ROOT)} ({out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main(sys.argv[1:])
