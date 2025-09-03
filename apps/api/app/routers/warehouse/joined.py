from __future__ import annotations
from typing import Optional, Literal
from datetime import datetime
import glob
from fastapi import APIRouter, Query
from .utils import joined_glob, select_joined_exprs, connect, rows

router = APIRouter()

@router.get("/joined/mfrr_lastprofile")
def get_joined_mfrr_lastprofile(
    agg: Literal["raw", "hour", "day"] = Query("hour"),
    start: Optional[datetime] = Query(None),
    end: Optional[datetime] = Query(None),
    columns: Optional[str] = Query(None, description="Komma-Liste von Last-Spalten (z.B. 'total_mw,Waschmaschine')"),
    limit: int = Query(1000, ge=1, le=100000),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    path = joined_glob(agg)
    if not glob.glob(path):
        return []
    where, params = [], []
    if start is not None:
        where.append("timestamp >= CAST(? AS TIMESTAMP)"); params.append(start)
    if end is not None:
        where.append("timestamp <= CAST(? AS TIMESTAMP)"); params.append(end)
    wsql = f"WHERE {' AND '.join(where)}" if where else ""
    exprs = select_joined_exprs(path, columns)
    dyn = ", ".join([f"{e} AS \"{alias}\"" for alias, e in exprs]) if exprs else ""
    mfr = "total_called_mw, avg_price_eur_mwh"
    sel = ", ".join([x for x in [dyn, mfr] if x]) or mfr
    sql = (f"SELECT timestamp AS ts, {sel} FROM parquet_scan('{path}') {wsql} "
           f"ORDER BY ts LIMIT {int(limit)} OFFSET {int(offset)}")
    with connect() as con:
        return rows(con.execute(sql, params))

