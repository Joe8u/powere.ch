#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# python steps/step02_preprocessing/curated/lastprofile/build_lastprofile_parquet.py --year 2024
"""
Build curated Parquet dataset from processed monthly load-profile CSVs.

Input (processed CSVs):  data/lastprofile/processed/<year>/<year>-01.csv ... -12.csv
Output (curated Parquet): data/curated/lastprofile/year=<year>/month=<MM>/data.parquet

- Hive-style partitioning: year=YYYY/month=MM
- Compression: Snappy
- Validates expected row counts (96*days per month)
- Keeps column names (German categories) as produced by step02_preprocessing/lastprofile

Run:
  python steps/step02_preprocessing/curated/lastprofile/build_lastprofile_parquet.py --year 2024
"""
from __future__ import annotations
import argparse
import calendar
import sys
from pathlib import Path
from typing import List, Tuple

import pandas as pd

# ---------- helpers ----------

def find_repo_root(start: Path) -> Path:
    """Walk upwards until '.git' or ('apps' and 'data') exist. Fallback: topmost parent."""
    for p in [start, *start.parents]:
        if (p / ".git").exists() or ((p / "apps").is_dir() and (p / "data").is_dir()):
            return p
    return start.parents[-1]

def month_expected_rows(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1] * 96  # 96 x 15-min slots per day

def read_month_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "timestamp" not in df.columns:
        raise ValueError(f"'timestamp' column missing in {path}")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=False, errors="coerce")
    if df["timestamp"].isna().any():
        raise ValueError(f"Invalid timestamps in {path}")
    # enforce numeric dtype for all non-timestamp columns
    for c in df.columns:
        if c != "timestamp":
            df[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")
    # add year/month partition cols
    df["year"] = df["timestamp"].dt.year.astype("int16")
    df["month"] = df["timestamp"].dt.month.astype("int8")
    # optional convenience column
    df["total_mw"] = df.drop(columns=["timestamp", "year", "month"]).sum(axis=1)
    # sort
    return df.sort_values("timestamp").reset_index(drop=True)

def write_parquet_partition(df: pd.DataFrame, out_base: Path, year: int, month: int) -> Path:
    part_dir = out_base / f"year={year}" / f"month={month:02d}"
    part_dir.mkdir(parents=True, exist_ok=True)
    out_file = part_dir / "data.parquet"
    # Write a single file per month partition (deterministic name)
    df.to_parquet(out_file, index=False, engine="pyarrow", compression="snappy")
    return out_file

# ---------- main ----------

def main() -> int:
    ap = argparse.ArgumentParser(description="Write curated Parquet dataset (Hive partitions) from processed CSVs.")
    ap.add_argument("--year", type=int, default=2024, help="Target year (default: 2024)")
    ap.add_argument("--in-dir", type=str, default=None,
                    help="Input dir with processed monthly CSVs (default: data/lastprofile/processed/<year>/)")
    ap.add_argument("--out-dir", type=str, default="data/curated/lastprofile",
                    help="Output base dir for curated Parquet dataset")
    ap.add_argument("--strict", action="store_true", help="Fail if a month is missing or row count mismatches")
    args = ap.parse_args()

    script_path = Path(__file__).resolve()
    repo_root = find_repo_root(script_path.parent)
    year = args.year
    in_dir = Path(args.in_dir) if args.in_dir else Path("data/lastprofile/processed") / str(year)
    out_dir = Path(args.out_dir)

    in_dir = (repo_root / in_dir).resolve()
    out_dir = (repo_root / out_dir).resolve()

    print(f"[INFO] Repo root     : {repo_root}")
    print(f"[INFO] Input dir     : {in_dir}")
    print(f"[INFO] Output (base) : {out_dir}")

    if not in_dir.exists():
        print(f"[ERROR] Input dir not found: {in_dir}")
        return 1

    written: List[Tuple[int, Path]] = []
    for m in range(1, 13):
        in_file = in_dir / f"{year}-{m:02d}.csv"
        if not in_file.exists():
            msg = f"[WARN] Missing {in_file} — skipping."
            if args.strict:
                print(msg.replace("[WARN]", "[ERROR]"))
                return 2
            print(msg)
            continue

        df = read_month_csv(in_file)
        exp = month_expected_rows(year, m)
        if len(df) != exp:
            msg = f"[WARN] Row count {len(df)} != expected {exp} for {in_file}"
            if args.strict:
                print(msg.replace("[WARN]", "[ERROR]"))
                return 3
            print(msg)

        out_file = write_parquet_partition(df, out_dir, year, m)
        print(f"[INFO] Wrote {out_file} (rows={len(df)})")
        written.append((m, out_file))

    if not written:
        print("[ERROR] Nothing written. Check input directory and filenames.")
        return 4

    print(f"[INFO] Done. Partitions written: {len(written)} (year={year})")
    print(f"[INFO] Dataset root: {out_dir}")
    print(f"[HINT] You can read this with DuckDB/Arrow using hive partitioning (year/month).")
    return 0

if __name__ == "__main__":
    sys.exit(main())
