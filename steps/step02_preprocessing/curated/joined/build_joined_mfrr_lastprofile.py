#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Join: Lastprofile (curated) × mFRR (curated) → joined Parquet
Schreibt drei Aggregationen: raw (15min), hour, day

Partitions:
  data/curated/joined/mfrr_lastprofile/agg=<raw|hour|day>/year=YYYY/month=MM/data.parquet

Run-Beispiele:
  python steps/step02_preprocessing/curated/joined/build_joined_mfrr_lastprofile.py --year 2024
  python ... --year 2024 --aggs raw hour
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path
import pandas as pd
from typing import Optional
import numpy as np

# ---------- helpers ----------

def find_repo_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / ".git").exists() or ((p / "apps").is_dir() and (p / "data").is_dir()):
            return p
    return start.parents[-1]


def read_month_parquet(base: Path, year: int, month: int) -> Optional[pd.DataFrame]:
    """Liest genau eine Monats-Parquet-Partition (year=YYYY/month=MM/data.parquet)."""
    p = base / f"year={year}" / f"month={month:02d}" / "data.parquet"
    if not p.exists():
        return None
    df = pd.read_parquet(p)
    if "timestamp" not in df.columns:
        raise ValueError(f"'timestamp' fehlt in {p}")
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    if df["timestamp"].isna().any():
        raise ValueError(f"Ungültige timestamps in {p}")
    return df


def write_partition(df: pd.DataFrame, out_base: Path, agg: str, year: int, month: int) -> Path:
    out_dir = out_base / f"agg={agg}" / f"year={year}" / f"month={month:02d}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "data.parquet"
    df.to_parquet(out_file, index=False, engine="pyarrow", compression="snappy")
    return out_file


def aggregate_weighted(df: pd.DataFrame, freq: str) -> pd.DataFrame:
    """
    Aggregation auf 'h' (hour) oder 'D' (day).
    - Lastspalten (alle außer mFRR und timestamp/year/month): Summe
    - total_called_mw: Summe
    - avg_price_eur_mwh: mengen-gewichteter Mittel (sum(pxq)/sum(w))
    """
    df = df.copy().set_index("timestamp").sort_index()

    known_mfrr = {"total_called_mw", "avg_price_eur_mwh"}
    value_cols = [c for c in df.columns if c not in known_mfrr and c not in ("year", "month")]

    # Summenteil (Haushalts-Last + total_called_mw)
    sum_part = df[value_cols + ["total_called_mw"]].resample(freq).sum(min_count=1)

    # gewichteter Preis: sum(pxq)/sum(w)
    tmp = df[["avg_price_eur_mwh", "total_called_mw"]].copy()
    tmp["pxq"] = tmp["avg_price_eur_mwh"] * tmp["total_called_mw"]

    grp = tmp.resample(freq).sum(min_count=1)
    pxq_sum = grp["pxq"]
    w_sum   = grp["total_called_mw"].replace(0, np.nan)   # Division durch 0 vermeiden

    weighted = pxq_sum / w_sum
    weighted = weighted.replace([np.inf, -np.inf], np.nan)

    price = weighted.to_frame("avg_price_eur_mwh")

    out = sum_part.join(price, how="left").reset_index()
    out["year"]  = out["timestamp"].dt.year.astype("int16")
    out["month"] = out["timestamp"].dt.month.astype("int8")
    return out


# ---------- main ----------

def main() -> int:
    ap = argparse.ArgumentParser(description="Join curated lastprofile × mFRR (tertiary) → joined Parquet (raw/hour/day).")
    ap.add_argument("--year", type=int, default=2024, help="Jahr (Default: 2024)")
    ap.add_argument("--last-base", type=str, default="data/curated/lastprofile", help="Basisordner Lastprofile (Hive)")
    ap.add_argument("--mfrr-base", type=str, default="data/curated/market/regelenergie", help="Basisordner mFRR (Hive)")
    ap.add_argument("--out-base", type=str, default="data/curated/joined/mfrr_lastprofile", help="Output-Basisordner")
    ap.add_argument("--aggs", nargs="+", default=["raw","hour","day"], choices=["raw","hour","day"], help="Welche Aggregationen schreiben")
    args = ap.parse_args()

    here = Path(__file__).resolve()
    repo = find_repo_root(here.parent)
    last_base = (repo / args.last_base).resolve()
    mfrr_base = (repo / args.mfrr_base).resolve()
    out_base = (repo / args.out_base).resolve()

    print(f"[INFO] Repo        : {repo}")
    print(f"[INFO] Last base  : {last_base}")
    print(f"[INFO] mFRR base  : {mfrr_base}")
    print(f"[INFO] Out base   : {out_base}")
    print(f"[INFO] Aggs       : {args.aggs}")

    written = 0
    missing = 0

    for m in range(1, 13):
        last_df = read_month_parquet(last_base, args.year, m)
        mfrr_df = read_month_parquet(mfrr_base, args.year, m)

        if last_df is None and mfrr_df is None:
            print(f"[WARN] Monat {m:02d}: Weder Lastprofil noch mFRR vorhanden – übersprungen.")
            missing += 1
            continue

        # Basis für den Join (immer timestamps vorhanden)
        if last_df is not None:
            base_df = last_df
        elif mfrr_df is not None:
            # hier weiß Pylance nun sicher: mfrr_df ist ein DataFrame
            base_df = mfrr_df[["timestamp"]].copy()
        else:
            # sollte durch das continue oben nie passieren; hilft dem Type Checker
            raise RuntimeError(f"Unexpected None for month {m:02d}")

        # mFRR-Spalten (können leer sein)
        if mfrr_df is not None:
            mfrr_keep = mfrr_df[["timestamp", "total_called_mw", "avg_price_eur_mwh"]].copy()
        else:
            mfrr_keep = pd.DataFrame(columns=["timestamp", "total_called_mw", "avg_price_eur_mwh"])

        # Join (left) auf timestamp
        joined_raw = base_df.merge(mfrr_keep, on="timestamp", how="left")
        joined_raw["year"] = joined_raw["timestamp"].dt.year.astype("int16")
        joined_raw["month"] = joined_raw["timestamp"].dt.month.astype("int8")

        # Schreiben je nach agg
        if "raw" in args.aggs:
            out = write_partition(joined_raw, out_base, "raw", args.year, m)
            print(f"[INFO] Wrote (raw)  : {out} (rows={len(joined_raw)})")
            written += 1

        if "hour" in args.aggs:
            joined_hour = aggregate_weighted(joined_raw, "h")
            out = write_partition(joined_hour, out_base, "hour", args.year, m)
            print(f"[INFO] Wrote (hour) : {out} (rows={len(joined_hour)})")
            written += 1

        if "day" in args.aggs:
            joined_day = aggregate_weighted(joined_raw, "D")
            out = write_partition(joined_day, out_base, "day", args.year, m)
            print(f"[INFO] Wrote (day)  : {out} (rows={len(joined_day)})")
            written += 1

    if written == 0:
        print("[ERROR] Keine Partition geschrieben. Prüfe Inputs.")
        return 2

    print(f"[INFO] Fertig. Geschriebene Partitionen: {written}. Fehlende Monate: {missing}.")
    print(f"[HINT] Lesen in DuckDB: SELECT * FROM parquet_scan('{out_base}/agg=raw/year=*/month=*/data.parquet');")
    return 0


if __name__ == "__main__":
    sys.exit(main())