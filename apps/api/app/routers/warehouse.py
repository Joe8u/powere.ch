# apps/api/app/routers/warehouse.py
from __future__ import annotations

import os
from datetime import datetime
import glob
from typing import Literal, Optional, Any, List, Sequence

import duckdb
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/warehouse", tags=["warehouse"])

# Basisverzeichnis (wird in Docker via env gesetzt, z.B. /app/data)
WAREHOUSE_ROOT = os.environ.get("WAREHOUSE_DATA_ROOT", "/app/data")

# Parquet-Pfade (Hive-Partitionierung year=/month=)
LP_GLOB = os.path.join(WAREHOUSE_ROOT, "curated/lastprofile/year=*/month=*/data.parquet")
TR_GLOB = os.path.join(WAREHOUSE_ROOT, "curated/market/regelenergie/year=*/month=*/data.parquet")
SURVEY_WIDE = os.path.join(WAREHOUSE_ROOT, "curated/survey/wide/data.parquet")


# ----------------------------- kleine Utils -----------------------------
def _connect() -> duckdb.DuckDBPyConnection:
    return duckdb.connect()

def _rows(cur) -> List[dict[str, Any]]:
    """
    Wandelt das aktuelle Result-Set (falls vorhanden) in eine Liste von Dicts um.
    Laut DB-API kann cursor.description None sein, wenn kein Result-Set vorliegt.
    """
    desc: Sequence[Sequence[Any]] | None = cur.description
    if desc is None:
        return []
    cols = [str(d[0]) for d in desc]
    data = cur.fetchall() or []
    return [dict(zip(cols, row)) for row in data]

def _list_columns_for_parquet(con: duckdb.DuckDBPyConnection, path: str) -> list[str]:
    """
    Liefert Spaltennamen eines Parquet-Files (ohne Zeilen zu laden).
    """
    cur = con.execute("SELECT * FROM parquet_scan(?) LIMIT 0", [path])
    desc = cur.description
    if desc is None:
        return []
    return [str(d[0]) for d in desc]

def _select_list_or_all(path_pattern: str, columns: Optional[str]) -> str:
    """
    Validiert eine optionale Komma-Liste von Spalten gegen das Schema des Parquet-Datasets.
    """
    if not columns:
        return "*"
    requested = [c.strip() for c in columns.split(",") if c.strip()]
    if not requested:
        return "*"

    con = _connect()
    try:
        valid = set(_list_columns_for_parquet(con, path_pattern))
    finally:
        con.close()

    unknown = [c for c in requested if c not in valid]
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown column(s): {unknown}")

    # sicher, weil wir nur verifizierte Namen durchlassen
    return ", ".join(requested)

# Aliases/Gruppen für Lastprofile (aggregierte Kategorien)
LP_GROUP_ALIASES: dict[str, list[str]] = {
    "Geschirrspüler": ["Geschirrspüler"],
    "Backofen und Herd": ["Backofen und Herd"],
    "Fernseher und Entertainment-Systeme": ["Fernseher und Entertainment-Systeme"],
    "Bürogeräte": ["Bürogeräte"],
    "Waschmaschine": ["Waschmaschine"],
}

def _build_lp_expressions(path_pattern: str, columns: Optional[str]) -> list[tuple[str, str]]:
    """
    Liefert Liste von (alias, expr) für Lastprofile:
    - Wenn Spaltennamen existieren → direkte Spalten
    - Wenn Name ein Gruppen-Alias ist → SUM(COALESCE(col,0) ...) als alias
    - Wenn keine columns übergeben → 'total' = SUM aller numerischen Spalten (außer timestamp)
    """
    con = _connect()
    try:
        valid = set(_list_columns_for_parquet(con, path_pattern))
    finally:
        con.close()

    def q_ident(col: str) -> str:
        # doppelte Anführungszeichen im Namen escapen und als Identifier quoten
        return '"' + col.replace('"', '""') + '"'

    def safe_num(col: str) -> str:
        # robust: Spalten als DOUBLE casten, fehlende Werte als 0.0
        return f"coalesce(try_cast({q_ident(col)} as DOUBLE), 0.0)"

    if not columns:
        # Fallback: Summe aller Spalten als 'total'
        numeric_cols = [c for c in valid if c != "timestamp"]
        if not numeric_cols:
            return []
        expr = " + ".join([safe_num(c) for c in numeric_cols])
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

# Aliases für das Survey-Wide Parquet (freundliche Kurz-Spaltennamen)
SURVEY_ALIASES = {
    "age":    "try_cast(nullif(question_1_age__age, '') as integer)",
    "gender": "question_2_gender__gender",
}

def _select_with_aliases(path_pattern: str, columns: Optional[str], aliases: dict[str, str]) -> str:
    """
    Wie _select_list_or_all, aber unterstützt Aliases -> erzeugt "expr AS alias".
    """
    if not columns:
        return "*"
    requested = [c.strip() for c in columns.split(",") if c.strip()]
    if not requested:
        return "*"

    con = _connect()
    try:
        valid = set(_list_columns_for_parquet(con, path_pattern))
    finally:
        con.close()

    parts, unknown = [], []
    for c in requested:
        if c in aliases:
            parts.append(f"{aliases[c]} AS {c}")
        elif c in valid:
            parts.append(c)
        else:
            unknown.append(c)

    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown column(s): {unknown}")
    return ", ".join(parts)


# ----------------------------- Endpoints -----------------------------

@router.get("/ping")
def ping() -> dict:
    return {"ok": True, "root": WAREHOUSE_ROOT}


@router.get("/lastprofile")
def get_lastprofile(
    year: Optional[int] = Query(None, ge=2000, le=2100),
    month: Optional[int] = Query(None, ge=1, le=12),
    columns: Optional[str] = Query(None, description="Kommagetrennte Spaltenliste; Standard: *"),
    limit: int = Query(1000, ge=1, le=100000),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    """
    Liefert Lastprofile (15-Min) aus Parquet-Partitionen (year=/month=/…).
    Optionale Filter: year, month.
    """
    # Robustheit: Falls keine Dateien vorhanden sind, leer zurückgeben statt Exception
    if not glob.glob(LP_GLOB):
        return []
    select_list = _select_list_or_all(LP_GLOB, columns)

    where: list[str] = []
    params: list[object] = []
    if year is not None:
        where.append("year = ?")
        params.append(year)
    if month is not None:
        where.append("month = ?")
        params.append(month)

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    sql = (
        f"SELECT {select_list} "
        f"FROM parquet_scan('{LP_GLOB}') "
        f"{where_sql} "
        f"ORDER BY timestamp "
        f"LIMIT {int(limit)} OFFSET {int(offset)}"
    )

    con = _connect()
    try:
        cur = con.execute(sql, params)
        return _rows(cur)
    finally:
        con.close()


@router.get("/lastprofile/columns")
def get_lastprofile_columns() -> dict:
    if not glob.glob(LP_GLOB):
        return {"columns": [], "groups": list(LP_GROUP_ALIASES.keys())}
    con = _connect()
    try:
        cols = _list_columns_for_parquet(con, LP_GLOB)
        cols = [c for c in cols if c != "timestamp"]
        return {"columns": cols, "groups": list(LP_GROUP_ALIASES.keys())}
    finally:
        con.close()


@router.get("/lastprofile/series")
def get_lastprofile_series(
    start: Optional[datetime] = Query(None),
    end:   Optional[datetime] = Query(None),
    agg:   Literal["raw", "hour", "day"] = Query("raw"),
    columns: Optional[str] = Query(None, description="Komma-Liste: Spalten oder Gruppen-Namen"),
    limit: int = Query(1000, ge=1, le=100000),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    if not glob.glob(LP_GLOB):
        return []

    where: list[str] = []
    params: list[object] = []
    if start is not None:
        where.append("timestamp >= CAST(? AS TIMESTAMP)")
        params.append(start)
    if end is not None:
        where.append("timestamp <= CAST(? AS TIMESTAMP)")
        params.append(end)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    exprs = _build_lp_expressions(LP_GLOB, columns)
    if not exprs:
        return []

    con = _connect()
    try:
        if agg == "raw":
            select_exprs = ", ".join([f"{e} AS \"{alias}\"" for alias, e in exprs])
            sql = (
                f"SELECT timestamp AS ts, {select_exprs} "
                f"FROM parquet_scan('{LP_GLOB}') "
                f"{where_sql} "
                f"ORDER BY ts "
                f"LIMIT {int(limit)} OFFSET {int(offset)}"
            )
            cur = con.execute(sql, params)
            return _rows(cur)

        ts_expr = "date_trunc('hour', timestamp)" if agg == "hour" else "date_trunc('day', timestamp)"
        # Aggregation: Durchschnittliche Leistung pro Aggregationsintervall
        aggs = ", ".join([f"AVG({e}) AS \"{alias}\"" for alias, e in exprs])
        sql = (
            "WITH base AS ("
            f"  SELECT * FROM parquet_scan('{LP_GLOB}') {where_sql}"
            ") "
            "SELECT "
            f"  {ts_expr} AS ts, {aggs} "
            "FROM base "
            "GROUP BY 1 "
            "ORDER BY 1 "
            f"LIMIT {int(limit)} OFFSET {int(offset)}"
        )
        cur = con.execute(sql, params)
        return _rows(cur)
    finally:
        con.close()


@router.get("/regelenergie/tertiary")
def get_tertiary_regulation(
    start: Optional[datetime] = Query(None),
    end:   Optional[datetime] = Query(None),
    agg:   Literal["raw", "hour", "day"] = Query("raw"),
    limit: int = Query(1000, ge=1, le=100000),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    """
    mFRR (tertiary regulation):
    - raw  : 15-Minuten-Ebene
    - hour : zu Stunde aggregiert
    - day  : zu Tag aggregiert (gewichteter Preis)
    Optionaler Zeitraumfilter: start/end (inklusive).
    """
    where: list[str] = []
    params: list[object] = []
    if start is not None:
        where.append("timestamp >= CAST(? AS TIMESTAMP)")
        params.append(start)
    if end is not None:
        where.append("timestamp <= CAST(? AS TIMESTAMP)")
        params.append(end)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    # Robustheit: Falls keine Dateien vorhanden sind, leer zurückgeben statt Exception
    if not glob.glob(TR_GLOB):
        return []

    con = _connect()
    try:
        if agg == "raw":
            sql = (
                "SELECT timestamp, total_called_mw, avg_price_eur_mwh "
                f"FROM parquet_scan('{TR_GLOB}') "
                f"{where_sql} "
                "ORDER BY timestamp "
                f"LIMIT {int(limit)} OFFSET {int(offset)}"
            )
            cur = con.execute(sql, params)
            return _rows(cur)

        ts_expr = "date_trunc('hour', timestamp)" if agg == "hour" else "date_trunc('day', timestamp)"
        sql = (
            "WITH base AS ("
            f"  SELECT * FROM parquet_scan('{TR_GLOB}') {where_sql}"
            ") "
            "SELECT "
            f"  {ts_expr} AS ts, "
            "  SUM(total_called_mw) AS total_called_mw, "
            "  CASE WHEN SUM(total_called_mw) = 0 THEN NULL "
            "       ELSE SUM(avg_price_eur_mwh * total_called_mw) / NULLIF(SUM(total_called_mw),0) "
            "  END AS avg_price_eur_mwh "
            "FROM base "
            "GROUP BY 1 "
            "ORDER BY 1 "
            f"LIMIT {int(limit)} OFFSET {int(offset)}"
        )
        cur = con.execute(sql, params)
        return _rows(cur)
    finally:
        con.close()


@router.get("/regelenergie/tertiary/latest_ts")
def get_tertiary_latest_ts() -> dict:
    if not glob.glob(TR_GLOB):
        return {"latest": None}
    con = _connect()
    try:
        cur = con.execute(f"SELECT max(timestamp) AS latest FROM parquet_scan('{TR_GLOB}')")
        rows = _rows(cur)
        latest = rows[0]["latest"].isoformat() if rows and rows[0].get("latest") else None
        return {"latest": latest}
    finally:
        con.close()


@router.get("/survey/wide")
def get_survey_wide(
    columns: Optional[str] = Query(None, description="Kommagetrennte Spaltenliste; Standard: *"),
    respondent_id: Optional[str] = Query(None, description="exakte respondent_id"),
    gender: Optional[str]  = Query(None, description="Filter: exakt (case-insensitive), z.B. 'female'"),
    min_age: Optional[int] = Query(None, ge=0, description="Filter: Mindestalter"),
    max_age: Optional[int] = Query(None, ge=0, description="Filter: Höchstalter"),
    limit: int = Query(1000, ge=1, le=100000),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    # Robustheit: Wenn die Parquet-Datei lokal (noch) nicht vorhanden ist,
    # liefere leeres Ergebnis statt 500-Fehler.
    if not os.path.isfile(SURVEY_WIDE):
        return []
    select_list = _select_with_aliases(SURVEY_WIDE, columns, SURVEY_ALIASES)

    age_expr    = SURVEY_ALIASES["age"]
    gender_expr = SURVEY_ALIASES["gender"]

    where, params = [], []
    if respondent_id:
        where.append("respondent_id = ?")
        params.append(respondent_id)
    if gender:
        where.append(f"lower({gender_expr}) = lower(?)")
        params.append(gender)
    if min_age is not None:
        where.append(f"{age_expr} >= ?")
        params.append(min_age)
    if max_age is not None:
        where.append(f"{age_expr} <= ?")
        params.append(max_age)

    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    sql = (
        "WITH base AS (SELECT * FROM parquet_scan(?)) "
        f"SELECT {select_list} FROM base "
        f"{where_sql} "
        "ORDER BY respondent_id "
        f"LIMIT {int(limit)} OFFSET {int(offset)}"
    )
    con = _connect()
    try:
        cur = con.execute(sql, [SURVEY_WIDE] + params)
        return _rows(cur)
    finally:
        con.close()


@router.get("/survey/wide/columns")
def get_survey_wide_columns() -> dict:
    if not os.path.isfile(SURVEY_WIDE):
        return {"columns": []}
    con = _connect()
    try:
        return {"columns": _list_columns_for_parquet(con, SURVEY_WIDE)}
    finally:
        con.close()

# --- joined mFRR × Lastprofile ---------------------------------------------
JOINED_BASE = os.path.join(WAREHOUSE_ROOT, "curated/joined/mfrr_lastprofile")

@router.get("/joined/mfrr_lastprofile")
def get_joined_mfrr_lastprofile(
    agg: Literal["raw", "hour", "day"] = Query("hour"),
    year: Optional[int] = Query(None, ge=2000, le=2100),
    month: Optional[int] = Query(None, ge=1, le=12),
    columns: Optional[str] = Query(None, description="Kommagetrennte Spaltenliste; Standard: *"),
    limit: int = Query(1000, ge=1, le=100000),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    y = str(year) if year is not None else "*"
    m = f"{month:02d}" if month is not None else "*"
    path = f"{JOINED_BASE}/agg={agg}/year={y}/month={m}/data.parquet"

    con = _connect()
    try:
        cols = _list_columns_for_parquet(con, path)
        select_list = "*"
        if columns:
            want = [c.strip() for c in columns.split(",") if c.strip()]
            unknown = [c for c in want if c not in cols]
            if unknown:
                raise HTTPException(status_code=400, detail=f"Unknown column(s): {unknown}")
            select_list = ", ".join(want)

        sql = (
            f"SELECT {select_list} "
            f"FROM parquet_scan(?) "
            f"ORDER BY 1 "
            f"LIMIT {int(limit)} OFFSET {int(offset)}"
        )
        cur = con.execute(sql, [path])
        return _rows(cur)
    finally:
        con.close()