#apps/api/app/routers/warehouse/utils.py
from __future__ import annotations

import os, glob
from typing import Any, List, Sequence, Optional, Literal
from datetime import datetime

import duckdb
from fastapi import HTTPException

# Root and common parquet locations
WAREHOUSE_ROOT = os.environ.get("WAREHOUSE_DATA_ROOT", "/app/data")

LP_GLOB = os.path.join(WAREHOUSE_ROOT, "curated/lastprofile/year=*/month=*/data.parquet")
TR_GLOB = os.path.join(WAREHOUSE_ROOT, "curated/market/regelenergie/year=*/month=*/data.parquet")
JOINED_BASE = os.path.join(WAREHOUSE_ROOT, "curated/joined/mfrr_lastprofile")
SURVEY_WIDE = os.path.join(WAREHOUSE_ROOT, "curated/survey/wide/data.parquet")


def connect() -> duckdb.DuckDBPyConnection:
    return duckdb.connect()


def rows(cur) -> List[dict[str, Any]]:
    desc: Sequence[Sequence[Any]] | None = cur.description
    if desc is None:
        return []
    cols = [str(d[0]) for d in desc]
    data = cur.fetchall() or []
    return [dict(zip(cols, r)) for r in data]


def list_columns(con: duckdb.DuckDBPyConnection, path: str) -> list[str]:
    cur = con.execute("SELECT * FROM parquet_scan(?) LIMIT 0", [path])
    desc = cur.description
    if not desc:
        return []
    return [str(d[0]) for d in desc]


def select_list_or_all(path_pattern: str, columns: Optional[str]) -> str:
    if not columns:
        return "*"
    req = [c.strip() for c in columns.split(",") if c.strip()]
    if not req:
        return "*"
    con = connect()
    try:
        valid = set(list_columns(con, path_pattern))
    finally:
        con.close()
    unknown = [c for c in req if c not in valid]
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown column(s): {unknown}")
    return ", ".join(req)


# Lastprofile helpers
LP_GROUP_ALIASES: dict[str, list[str]] = {
    "Geschirrspüler": ["Geschirrspüler"],
    "Backofen und Herd": ["Backofen und Herd"],
    "Fernseher und Entertainment-Systeme": ["Fernseher und Entertainment-Systeme"],
    "Bürogeräte": ["Bürogeräte"],
    "Waschmaschine": ["Waschmaschine"],
}


def build_lp_expressions(path_pattern: str, columns: Optional[str]) -> list[tuple[str, str]]:
    con = connect()
    try:
        valid = set(list_columns(con, path_pattern))
    finally:
        con.close()

    def q_ident(col: str) -> str:
        return '"' + col.replace('"', '""') + '"'

    def safe_num(col: str) -> str:
        return f"coalesce(try_cast({q_ident(col)} as DOUBLE), 0.0)"

    if not columns:
        numeric = [c for c in valid if c != "timestamp"]
        if not numeric:
            return []
        expr = " + ".join([safe_num(c) for c in numeric])
        return [("total", expr)]

    requested = [c.strip() for c in columns.split(",") if c.strip()]
    out: list[tuple[str, str]] = []
    unknown: list[str] = []
    for name in requested:
        if name in valid:
            out.append((name, safe_num(name)))
            continue
        if name in LP_GROUP_ALIASES:
            cols = [c for c in LP_GROUP_ALIASES[name] if c in valid]
            if cols:
                expr = " + ".join([safe_num(c) for c in cols])
                out.append((name, expr))
                continue
        unknown.append(name)
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown column/group(s): {unknown}")
    return out


def joined_glob(agg: str) -> str:
    return os.path.join(JOINED_BASE, f"agg={agg}", "year=*/month=*/data.parquet")


def select_joined_exprs(path_pattern: str, columns: Optional[str]) -> list[tuple[str, str]]:
    con = connect()
    try:
        valid = set(list_columns(con, path_pattern))
    finally:
        con.close()

    def q_ident(col: str) -> str:
        return '"' + col.replace('"', '""') + '"'

    if not columns:
        return [("total_mw", q_ident("total_mw"))] if "total_mw" in valid else []
    requested = [c.strip() for c in columns.split(",") if c.strip()]
    out: list[tuple[str, str]] = []
    unknown: list[str] = []
    for name in requested:
        if name in valid:
            out.append((name, q_ident(name)))
        else:
            unknown.append(name)
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown column(s): {unknown}")
    return out


# Survey helpers
SURVEY_ALIASES = {
    "age":    "try_cast(nullif(question_1_age__age, '') as integer)",
    "gender": "question_2_gender__gender",
}


