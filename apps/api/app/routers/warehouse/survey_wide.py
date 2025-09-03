#apps/api/app/routers/warehouse/survey_wide.py
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Query
import os
from .utils import SURVEY_WIDE, connect, rows, list_columns, SURVEY_ALIASES

router = APIRouter()

@router.get("/survey/wide")
def get_survey_wide(
    columns: Optional[str] = Query(None),
    respondent_id: Optional[str] = Query(None),
    gender: Optional[str]  = Query(None),
    min_age: Optional[int] = Query(None, ge=0),
    max_age: Optional[int] = Query(None, ge=0),
    limit: int = Query(1000, ge=1, le=100000),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    if not os.path.isfile(SURVEY_WIDE):
        return []
    select_list = _select_with_aliases(columns)

    age_expr = SURVEY_ALIASES["age"]
    gender_expr = SURVEY_ALIASES["gender"]
    where, params = [], []
    if respondent_id:
        where.append("respondent_id = ?"); params.append(respondent_id)
    if gender:
        where.append(f"lower({gender_expr}) = lower(?)"); params.append(gender)
    if min_age is not None:
        where.append(f"{age_expr} >= ?"); params.append(min_age)
    if max_age is not None:
        where.append(f"{age_expr} <= ?"); params.append(max_age)
    wsql = f"WHERE {' AND '.join(where)}" if where else ""
    sql = ("WITH base AS (SELECT * FROM parquet_scan(?)) "
           f"SELECT {select_list} FROM base {wsql} ORDER BY respondent_id "
           f"LIMIT {int(limit)} OFFSET {int(offset)}")
    with connect() as con:
        return rows(con.execute(sql, [SURVEY_WIDE] + params))


def _select_with_aliases(columns: Optional[str]) -> str:
    if not columns:
        return "*"
    req = [c.strip() for c in columns.split(",") if c.strip()]
    if not req:
        return "*"
    with connect() as con:
        valid = set(list_columns(con, SURVEY_WIDE))
    parts, unknown = [], []
    for c in req:
        if c in SURVEY_ALIASES:
            parts.append(f"{SURVEY_ALIASES[c]} AS {c}")
        elif c in valid:
            parts.append(c)
        else:
            unknown.append(c)
    if unknown:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Unknown column(s): {unknown}")
    return ", ".join(parts)


@router.get("/survey/wide/columns")
def get_survey_wide_columns() -> dict:
    if not os.path.isfile(SURVEY_WIDE):
        return {"columns": []}
    with connect() as con:
        return {"columns": list_columns(con, SURVEY_WIDE)}

