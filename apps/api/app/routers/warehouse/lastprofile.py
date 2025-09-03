#apps/api/app/routers/warehouse/lastprofile.py
from __future__ import annotations
from typing import Optional, Literal, List
from datetime import datetime
import glob
from fastapi import APIRouter, Query
from .utils import LP_GLOB, connect, rows, select_list_or_all, build_lp_expressions, list_columns, LP_GROUP_ALIASES

router = APIRouter()

@router.get("/lastprofile")
def get_lastprofile(
    year: Optional[int] = Query(None, ge=2000, le=2100),
    month: Optional[int] = Query(None, ge=1, le=12),
    columns: Optional[str] = Query(None),
    limit: int = Query(1000, ge=1, le=100000),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    if not glob.glob(LP_GLOB):
        return []
    select_list = select_list_or_all(LP_GLOB, columns)
    where, params = [], []
    if year is not None:
        where.append("year = ?"); params.append(year)
    if month is not None:
        where.append("month = ?"); params.append(month)
    wsql = f"WHERE {' AND '.join(where)}" if where else ""
    sql = (f"SELECT {select_list} FROM parquet_scan('{LP_GLOB}') {wsql} "
           f"ORDER BY timestamp LIMIT {int(limit)} OFFSET {int(offset)}")
    with connect() as con:
        return rows(con.execute(sql, params))


@router.get("/lastprofile/columns")
def get_lastprofile_columns() -> dict:
    if not glob.glob(LP_GLOB):
        return {"columns": [], "groups": list(LP_GROUP_ALIASES.keys())}
    with connect() as con:
        cols = [c for c in list_columns(con, LP_GLOB) if c != "timestamp"]
    return {"columns": cols, "groups": list(LP_GROUP_ALIASES.keys())}


@router.get("/lastprofile/series")
def get_lastprofile_series(
    start: Optional[datetime] = Query(None),
    end:   Optional[datetime] = Query(None),
    agg:   Literal["raw", "hour", "day"] = Query("raw"),
    columns: Optional[str] = Query(None),
    limit: int = Query(1000, ge=1, le=100000),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    if not glob.glob(LP_GLOB):
        return []
    where, params = [], []
    if start is not None:
        where.append("timestamp >= CAST(? AS TIMESTAMP)"); params.append(start)
    if end is not None:
        where.append("timestamp <= CAST(? AS TIMESTAMP)"); params.append(end)
    wsql = f"WHERE {' AND '.join(where)}" if where else ""
    exprs = build_lp_expressions(LP_GLOB, columns)
    if not exprs:
        return []
    with connect() as con:
        if agg == "raw":
            sel = ", ".join([f"{e} AS \"{alias}\"" for alias, e in exprs])
            sql = (f"SELECT timestamp AS ts, {sel} FROM parquet_scan('{LP_GLOB}') {wsql} "
                   f"ORDER BY ts LIMIT {int(limit)} OFFSET {int(offset)}")
            return rows(con.execute(sql, params))
        ts_expr = "date_trunc('hour', timestamp)" if agg == "hour" else "date_trunc('day', timestamp)"
        aggs = ", ".join([f"AVG({e}) AS \"{alias}\"" for alias, e in exprs])
        sql = ("WITH base AS (SELECT * FROM parquet_scan('{LP_GLOB}') "
               f"{wsql}) SELECT {ts_expr} AS ts, {aggs} FROM base GROUP BY 1 ORDER BY 1 "
               f"LIMIT {int(limit)} OFFSET {int(offset)}")
        return rows(con.execute(sql, params))
