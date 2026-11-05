from __future__ import annotations

import threading
from pathlib import Path

import duckdb

from .config import DB_PATH

_lock = threading.RLock()
_con: duckdb.DuckDBPyConnection | None = None


def connect(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(DB_PATH), read_only=read_only)


def set_connection(con: duckdb.DuckDBPyConnection) -> None:
    global _con
    _con = con


def get_con() -> duckdb.DuckDBPyConnection:
    global _con
    if _con is None:
        with _lock:
            if _con is None:
                if not Path(DB_PATH).exists():
                    raise RuntimeError("Database is not available at the configured path.")
                _con = duckdb.connect(str(DB_PATH), read_only=True)
    return _con


def execute(sql: str, params: list | tuple | None = None):
    with _lock:
        con = get_con()
        if params is None:
            return con.execute(sql)
        return con.execute(sql, params)


def fetchall(sql: str, params: list | tuple | None = None) -> list[dict]:
    rel = execute(sql, params)
    cols = [c[0] for c in rel.description]
    return [dict(zip(cols, row)) for row in rel.fetchall()]


def fetchone(sql: str, params: list | tuple | None = None) -> dict | None:
    rows = fetchall(sql, params)
    return rows[0] if rows else None
