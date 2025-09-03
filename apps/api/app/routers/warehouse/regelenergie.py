#apps/api/app/routers/warehouse/regelenergie.py
from __future__ import annotations
from typing import Optional, Literal
from datetime import datetime
import glob
from fastapi import APIRouter, Query
from .utils import TR_GLOB, connect, rows

router = APIRouter()

@router.get("/regelenergie/tertiary")
def get_tertiary_regulation(
    start: Optional[datetime] = Query(None),
    end:   Optional[datetime] = Query(None),
    agg:   Literal["raw", "hour", "day"] = Query("raw"),
    limit: int = Query(1000, ge=1, le=100000),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    where, params = [], []
    if start is not None:
        where.append("timestamp >= CAST(? AS TIMESTAMP)"); params.append(start)
    if end is not None:
        where.append("timestamp <= CAST(? AS TIMESTAMP)"); params.append(end)
    wsql = f"WHERE {' AND '.join(where)}" if where else ""
    if not glob.glob(TR_GLOB):
        return []
    with connect() as con:
        if agg == "raw":
            sql = ("SELECT timestamp, total_called_mw, avg_price_eur_mwh "
                   f"FROM parquet_scan('{TR_GLOB}') {wsql} ORDER BY timestamp "
                   f"LIMIT {int(limit)} OFFSET {int(offset)}")
            return rows(con.execute(sql, params))
        ts_expr = "date_trunc('hour', timestamp)" if agg == "hour" else "date_trunc('day', timestamp)"
        sql = ("WITH base AS (SELECT * FROM parquet_scan('{TR_GLOB}') "
               f"{wsql}) SELECT {ts_expr} AS ts, "
               "SUM(total_called_mw) AS total_called_mw, "
               "CASE WHEN SUM(total_called_mw)=0 THEN NULL ELSE SUM(avg_price_eur_mwh * total_called_mw) / NULLIF(SUM(total_called_mw),0) END AS avg_price_eur_mwh "
               "FROM base GROUP BY 1 ORDER BY 1 "
               f"LIMIT {int(limit)} OFFSET {int(offset)}")
        return rows(con.execute(sql, params))


@router.get("/regelenergie/tertiary/latest_ts")
def get_tertiary_latest_ts() -> dict:
    if not glob.glob(TR_GLOB):
        return {"latest": None}
    with connect() as con:
        cur = con.execute(f"SELECT max(timestamp) AS latest FROM parquet_scan('{TR_GLOB}')")
        r = rows(cur)
        latest = r[0]["latest"].isoformat() if r and r[0].get("latest") else None
        return {"latest": latest}

