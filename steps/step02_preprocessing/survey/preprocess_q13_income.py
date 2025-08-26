#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
preprocess_q13_income.py

Extrahiert Q13 ("Wie hoch ist Ihr monatliches Haushaltsnettoeinkommen?")
und leitet numerische Grenzen ab:

- Unter 3.000 CHF      -> min=0,     max=3000,  mid=NA
- 3.000 - 5.000 CHF    -> min=3000,  max=5000,  mid=(min+max)/2
- 5.001 - 7.000 CHF    -> min=5001,  max=7000,  mid=(min+max)/2
- 7.001 - 10.000 CHF   -> min=7001,  max=10000, mid=(min+max)/2
- Über 10.000 CHF      -> min=10000, max=NA,    mid=NA
- Keine Angabe / leer  -> alle NA

Aufruf (Repo-Root):
  python3 processing/survey/jobs/preprocess_q13_income.py
"""

from __future__ import annotations
from pathlib import Path
import sys
import re
import argparse
import pandas as pd
import numpy as np


def project_root() -> Path:
    try:
        return Path(__file__).resolve().parents[3]
    except NameError:
        return Path.cwd()


def _read_csv_any_encoding(path: str | Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path, header=0, skiprows=[1], dtype=str)
    except UnicodeDecodeError:
        return pd.read_csv(path, header=0, skiprows=[1], dtype=str, encoding="latin-1")


def _find_q13_col(columns) -> str:
    """Spalte mit 'Haushaltsnettoeinkommen' (case-insensitive) finden."""
    for c in columns:
        if isinstance(c, str) and "haushaltsnettoeinkommen" in c.lower():
            return c
    raise KeyError("Q13-Spalte (Haushaltsnettoeinkommen) nicht gefunden.")


def _clean_income_label(x: object) -> str:
    """Leere/NA/Strings wie 'nan' -> 'Keine Angabe' sonst getrimmter Originalwert."""
    if x is None:
        return "Keine Angabe"
    s = str(x).strip()
    if s == "":
        return "Keine Angabe"
    if s.lower() in {"nan", "na", "n/a", "keine angabe"}:
        return "Keine Angabe"
    return s


def _to_int(num_str: str | None) -> int | None:
    if not num_str:
        return None
    digits = re.sub(r"[^\d]", "", num_str)
    return int(digits) if digits else None


def _bounds_for(label: str) -> tuple[int | None, int | None, int | None]:
    """
    Liefert (min, max, mid) in CHF für einen Label-String.
    Offene Ränder bleiben None; 'Unter' -> min=0, 'Über' -> max=None.
    """
    low = high = mid = None
    lab_low = label.lower()

    if label == "Keine Angabe":
        return (None, None, None)

    # Unter X CHF
    m = re.search(r"unter\s*([\d\.\s']+)\s*chf", lab_low)
    if m:
        high = _to_int(m.group(1))
        low = 0 if high is not None else None
        return (low, high, None)

    # Über X CHF
    m = re.search(r"über\s*([\d\.\s']+)\s*chf", lab_low)
    if m:
        low = _to_int(m.group(1))
        return (low, None, None)

    # A - B CHF (inkl. Varianten mit Punkten/Apostrophen)
    m = re.search(r"([\d\.'\s]+)\s*-\s*([\d\.'\s]+)\s*chf", lab_low)
    if m:
        low = _to_int(m.group(1))
        high = _to_int(m.group(2))
        if low is not None and high is not None:
            mid = int((low + high) / 2)
        return (low, high, mid)

    # Falls ein anderes Format auftaucht -> keine Zahlen
    return (None, None, None)


def preprocess_q13_income(infile: Path, outfile: Path) -> None:
    df = _read_csv_any_encoding(infile)

    if "respondent_id" not in df.columns:
        print("[ERROR] Spalte 'respondent_id' nicht gefunden.", file=sys.stderr)
        sys.exit(1)

    q13_col = _find_q13_col(df.columns)
    print(f"[INFO] Repo-Root: {project_root()}")
    print(f"[INFO] Input CSV: {infile}")
    print(f"[INFO] Output:    {outfile}")
    print(f"[INFO] Q13-Spalte: {q13_col!r}")

    # Label bereinigen
    out = pd.DataFrame({"respondent_id": df["respondent_id"]})
    out["q13_income"] = df[q13_col].map(_clean_income_label)

    # Numerische Grenzen ableiten
    mins, maxs, mids = [], [], []
    for lab in out["q13_income"]:
        lo, hi, md = _bounds_for(lab)
        mins.append(lo)
        maxs.append(hi)
        mids.append(md)

    out["income_min_chf"] = pd.Series(mins, dtype="Int64")
    out["income_max_chf"] = pd.Series(maxs, dtype="Int64")
    out["income_mid_chf"] = pd.Series(mids, dtype="Int64")

    # Speichern
    outfile.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(outfile, index=False, encoding="utf-8")
    print(f"[OK] Q13 gespeichert: {outfile} (rows={len(out)})")

    # kurze Kontrolle
    print("[INFO] Verteilung q13_income:")
    print(out["q13_income"].value_counts(dropna=False))


def main():
    root = project_root()
    default_in = root / "data/survey/raw/Energieverbrauch und Teilnahmebereitschaft an Demand-Response-Programmen in Haushalten.csv"
    default_out = root / "data/survey/processed/question_13_income.csv"

    ap = argparse.ArgumentParser(description="Preprocess Survey Q13 (Income)")
    ap.add_argument("--infile", type=str, default=str(default_in))
    ap.add_argument("--outfile", type=str, default=str(default_out))
    args = ap.parse_args()

    infile = Path(args.infile).resolve()
    outfile = Path(args.outfile).resolve()
    if not infile.exists():
        print(f"[ERROR] Input nicht gefunden: {infile}", file=sys.stderr)
        sys.exit(1)

    preprocess_q13_income(infile, outfile)


if __name__ == "__main__":
    main()
