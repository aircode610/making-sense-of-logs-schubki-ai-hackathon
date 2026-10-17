"""Run each golden fact's reference SQL once and store the value in the question file (plan 009).
Usage: .venv/bin/python eval/build_golden.py eval/dev_questions.yaml   (re-run only after a data reload changes counts)"""
import sys
from pathlib import Path

import psycopg
import yaml


def main(path: str) -> None:
    qs = yaml.safe_load(Path(path).read_text())
    with psycopg.connect("host=localhost port=7890 user=postgres dbname=postgres", autocommit=True) as c:
        for q in qs:
            for g in q.get("golden", []):
                v = c.execute(g["sql"]).fetchone()[0]
                g["value"] = v
                print(f"{q['id']:<7} {g['fact'][:70]:<70} = {v}")
    Path(path).write_text(Path(path).read_text().split("\n- id:")[0] + "\n" +
                          yaml.safe_dump(qs, sort_keys=False, allow_unicode=True, width=200))


if __name__ == "__main__":
    main(sys.argv[1])
