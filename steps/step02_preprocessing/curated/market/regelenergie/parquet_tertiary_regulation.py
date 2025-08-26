# steps/step02_preprocessing/curated/market/regelenergie/parquet_tertiary_regulation.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kuratiert mFRR/Tertiärregelenergie für Analytics:
Liests die von preprocess_tertiary_regulation.py erzeugten Monats-CSV
(data/market/processed/regelenergie/YYYY-MM.csv)
und schreibt Parquet-partitioniert nach:
data/curated/market/regelenergie/year=YYYY/month=MM/data.parquet

Schema (beibehalten):
  timestamp (ns), total_called_mw (float64), avg_price_eur_mwh (float64)

Aufruf:
  python -m steps.step02_preprocessing.curated.market.regelenergie.parquet_tertiary_regulation --year 2024
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path
import pandas as pd

# ------------------------- Pfad-Utilities -------------------------

def find_repo_root(start: Path) -> Path:
    """Suche Repo-Root ('.git' oder typische Ordner)."""
    for p in [start, *start.parents]:
        if (p / ".git").exists() or ((p / "apps").is_dir() and (p / "data").is_dir()):
            return p
    return start.parents[3]  # Fallback

def write_parquet_partition(df: pd.DataFrame, base: Path, year: int, month: int) -> Path:
    """Schreibt df nach base/year=YYYY/month=MM/data.parquet (Snappy, PyArrow)."""
    out_dir = base / f"year={year}" / f"month={month:02d}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "data.parquet"
    # Typen normalisieren
    if "timestamp" in df.columns:
        df = df.copy()
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df[["timestamp", "total_called_mw", "avg_price_eur_mwh"]].copy()
    df.to_parquet(out_file, index=False, engine="pyarrow", compression="snappy")
    return out_file

# ----------------------------- CLI/Runner -----------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="Kuratiert mFRR (tertiary regulation) Monats-CSV → Parquet (partitioniert).")
    ap.add_argument("--year", type=int, default=2024, help="Jahr der processed-Dateien (Default: 2024)")
    ap.add_argument("--in_dir", type=str, default="data/market/processed/regelenergie",
                    help="Input-Basisordner mit YYYY-MM.csv")
    ap.add_argument("--out_dir", type=str, default="data/curated/market/regelenergie",
                    help="Output-Basisordner (Hive-Partitionen year=/month=)")
    args = ap.parse_args()

    here = Path(__file__).resolve()
    repo = find_repo_root(here.parent)
    in_base = (repo / args.in_dir).resolve()
    out_base = (repo / args.out_dir).resolve()

    print(f"[INFO] Repo root     : {repo}")
    print(f"[INFO] Input (base)  : {in_base}")
    print(f"[INFO] Output (base) : {out_base}")

    if not in_base.exists():
        print(f"[ERROR] Input-Verzeichnis nicht gefunden: {in_base}")
        return 1

    # Alle Monatsdateien des Jahres
    files = sorted(in_base.glob(f"{args.year}-[0-1][0-9].csv"))
    if not files:
        print(f"[WARN] Keine Monats-CSV unter {in_base} gefunden (Jahr {args.year}).")
        return 0

    import_errors = 0
    written = 0

    for p in files:
        try:
            # Robust einlesen (Kommas als Dezimaltrenner wären hier unüblich, aber wir tolerieren)
            df = pd.read_csv(p)
            # Minimal-Checks
            need = {"timestamp", "total_called_mw", "avg_price_eur_mwh"}
            miss = need - set(df.columns)
            if miss:
                print(f"[WARN] {p.name}: fehlende Spalten {miss} – übersprungen.")
                continue

            # Monat aus Dateinamen oder aus Timestamps ableiten
            try:
                month = int(p.stem.split("-")[1])
            except Exception:
                # Fallback: aus timestamp
                ts = pd.to_datetime(df["timestamp"], errors="coerce")
                month = int(ts.dt.month.mode().iat[0])

            out_file = write_parquet_partition(df, out_base, args.year, month)
            print(f"[INFO] Wrote {out_file} (rows={len(df)})")
            written += 1

        except Exception as e:
            print(f"[ERROR] Konnte {p.name} nicht verarbeiten: {e}")
            import_errors += 1

    print(f"[INFO] Done. Parquet-Partitionen geschrieben: {written}  Fehler: {import_errors}")
    print(f"[HINT] Mit DuckDB/Arrow lesbar (Hive-Partitionen year=/month=).")
    return 0

if __name__ == "__main__":
    sys.exit(main())
