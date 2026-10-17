"""Tiny SereneDB helpers (Postgres wire protocol via psycopg)."""
import psycopg
from psycopg.rows import dict_row

from pipeline import config


def connect() -> psycopg.Connection:
    return psycopg.connect(config.DB_DSN, autocommit=True, row_factory=dict_row)


def query(conn, sql: str, schema: str, **params) -> list[dict]:
    """Runs a query from pipeline/queries.py. `{s}` in the SQL is replaced by the schema name."""
    return conn.execute(sql.format(s=schema), params).fetchall()


def exec_(conn, sql: str) -> None:
    conn.execute(sql)
