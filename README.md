# Making Sense of Logs — the right insights for the right people

SchubKI National AI Hackathon 2026 · SereneDB challenge · Team: Amirali, Konark.

> **SereneDB counts, Jev judges, the LLM explains — and every sentence is checked against the query that produced it.**

🚧 Work in progress (hackathon running 17–18 Oct 2026). This README is filled in as the prototype comes together.

## Workflow
Question → evidence (SereneDB full-text search + aggregations, via MCP tools) → recommendation (agent), for three roles:
**engineer** (what failed, where, what happened around it), **team lead** (what recurs, how often, which teams),
**manager** (what to prioritise and why, from measured frequency and spread only).

## Setup (clean checkout)
Requirements: Docker, Python 3.12, [`uv`](https://docs.astral.sh/uv/), `psql`.
```bash
cp .env.example .env                     # fill in keys
./scripts/download_data.sh               # BGL + OpenStack (~770 MB) into data/raw/
docker compose up -d                     # SereneDB on localhost:7890
psql -h localhost -p 7890 -U postgres -d postgres -f docker/init.sql   # first start only
./docker/secrets.sh                      # after every start: registers AI keys in SereneDB
uv venv --python 3.12 && uv pip install -r requirements.txt
```
Load, MCP server, agent and UI: _coming soon_.

## Data
Loghub **BGL** (4,747,963 lines, 214.7 days) and **OpenStack** (207,820 lines). See [`data/README.md`](data/README.md).
Ownership table (fictional): [`data/ownership.csv`](data/ownership.csv).

## Tools
_Coming soon_ (purpose, inputs, outputs of each MCP tool).

## Worked investigation
_Coming soon._

## Known limitations
_Coming soon._

## Citation
Zhu et al., *Loghub: A Large Collection of System Log Datasets for AI-driven Log Analytics*, ISSRE 2023.
Oliner & Stearley, *What Supercomputers Say: A Study of Five System Logs*, DSN 2007.
