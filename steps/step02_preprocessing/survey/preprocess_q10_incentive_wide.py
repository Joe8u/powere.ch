#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
preprocess_q10_incentive_wide.py

Erkennt im Survey-Export (CSV) die Q10-Spalten:
- <Gerät> - Ja/Nein/… (Choice)
- <Gerät> - Falls Ja, Stromkosten-Rabatt in Prozent (Pct)

und schreibt ein Wide-CSV:
  respondent_id, <Gerät>_choice, <Gerät>_pct, …

Bereinigung:
- Wenn Choice "Nein" ODER "Ja (freiwillig)" -> _pct = NA
- Wenn Choice fehlt, aber _pct vorhanden -> _pct = NA

Aufruf (Repo-Root):
  python3 processing/survey/jobs/preprocess_q10_incentive_wide.py
Optional:
  python3 processing/survey/jobs/preprocess_q10_incentive_wide.py \
    --infile "data/survey/raw/Energieverbrauch und Teilnahmebereitschaft an Demand-Response-Programmen in Haushalten.csv" \
    --outfile "data/survey/processed/question_10_incentive_wide.csv" \
    --debug
"""

from __future__ import annotations
from pathlib import Path
import argparse
import re
import sys
import pandas as pd
import numpy as np


def project_root() -> Path:
    try:
        return Path(__file__).resolve().parents[3]
    except NameError:
        return Path.cwd()


# ---- Heuristiken / Parser ----
def parse_pct(x):
    """Extrahiert erste Ganzzahl aus z.B. '5%' -> 5, sonst pd.NA."""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return pd.NA
    s = str(x).strip()
    if not s or s.lower() == "nan":
        return pd.NA
    m = re.search(r"(\d+)", s)
    return int(m.group(1)) if m else pd.NA


def is_voluntary(choice_val: str) -> bool:
    """Erkennt 'Ja (freiwillig)' in diversen Schreibweisen."""
    if choice_val is None or (isinstance(choice_val, float) and np.isnan(choice_val)):
        return False
    s = str(choice_val).strip().lower()
    # Beispiele in deinen Daten: 'Ja, f' / 'Ja f' / 'Ja freiwillig' / zusammengezogene Varianten
    return ("ja" in s) and (("freiw" in s) or (" f" in s) or (", f" in s)) and ("+" not in s) and ("kompens" not in s)


def is_no(choice_val: str) -> bool:
    if choice_val is None or (isinstance(choice_val, float) and np.isnan(choice_val)):
        return False
    return "nein" in str(choice_val).strip().lower()


def find_q10_columns(header_cols: list[str], debug: bool = False):
    """
    Scannt die 2. Kopfzeile (header=1) und findet Q10-Choice/Pct-Spalten.
    Wir erkennen Q10 an Mustern in der Spaltenbezeichnung, NICHT über Level-0.
    """
    # Muster: "<Gerät> - Falls Ja ... Prozent"
    pct_re = re.compile(r"^\s*(?P<dev>[^-]+?)\s*-\s*.*falls\s*ja.*prozent.*$", re.IGNORECASE)
    # Muster: "<Gerät> - Ja ... / Nein ... / (freiwillig|Kompensation) ..."
    choice_re = re.compile(r"^\s*(?P<dev>[^-]+?)\s*-\s*.*(ja|nein|freiw|kompens).*$", re.IGNORECASE)

    choice_map: dict[str, str] = {}  # dev -> column name
    pct_map: dict[str, str] = {}     # dev -> column name

    for col in header_cols:
        if not isinstance(col, str):
            continue
        name = col.strip()
        if not name:
            continue

        m_pct = pct_re.match(name)
        if m_pct:
            dev = m_pct.group("dev").strip()
            pct_map[dev] = col
            continue

        m_choice = choice_re.match(name)
        if m_choice:
            dev = m_choice.group("dev").strip()
            choice_map[dev] = col
            continue

    kept = [d for d in choice_map.keys() if d in pct_map]

    if debug:
        print("[DEBUG] Q10-Choice-Kandidaten:", choice_map)
        print("[DEBUG] Q10-Pct-Kandidaten:   ", pct_map)
        print("[DEBUG] Q10-Geräte (both):    ", kept)

    return kept, choice_map, pct_map


def preprocess(infile: Path, outfile: Path, debug: bool = False) -> None:
    root = project_root()
    print(f"[INFO] Repo-Root: {root}")
    print(f"[INFO] Input CSV: {infile}")
    print(f"[INFO] Output:    {outfile}")

    # A) respondent_id sicher aus "flacher" Sicht holen
    try:
        df_flat = pd.read_csv(infile, header=0, skiprows=[1], dtype=str)
    except UnicodeDecodeError:
        df_flat = pd.read_csv(infile, header=0, skiprows=[1], dtype=str, encoding="latin-1")
    if "respondent_id" not in df_flat.columns:
        print("[ERROR] 'respondent_id' nicht gefunden.", file=sys.stderr)
        sys.exit(1)

    # B) 2. Kopfzeile als Header verwenden, um Q10-Spalten robust zu finden
    try:
        df_h1 = pd.read_csv(infile, header=1, dtype=str)
    except UnicodeDecodeError:
        df_h1 = pd.read_csv(infile, header=1, dtype=str, encoding="latin-1")

    devices, choice_map, pct_map = find_q10_columns(df_h1.columns.tolist(), debug=debug)
    if not devices:
        print("[ERROR] Keine vollständigen (choice+pct) Gerätepärchen in Q10 gefunden.", file=sys.stderr)
        if debug:
            print("[DEBUG] Header (header=1):")
            for c in df_h1.columns.tolist():
                print("   -", c)
        sys.exit(1)

    # C) Output-Frame aufbauen
    out = pd.DataFrame({"respondent_id": df_flat["respondent_id"]})

    for dev in devices:
        c_col = choice_map[dev]
        p_col = pct_map[dev]

        choice_series = df_h1[c_col].astype("string")
        pct_series = df_h1[p_col].map(parse_pct)

        # Bereinigung
        mask_no = choice_series.map(is_no)
        mask_vol = choice_series.map(is_voluntary)
        pct_series = pct_series.mask(mask_no | mask_vol, pd.NA)
        pct_series = pct_series.mask(choice_series.isna() & pct_series.notna(), pd.NA)

        out[f"{dev}_choice"] = choice_series
        out[f"{dev}_pct"] = pd.to_numeric(pct_series, errors="coerce").astype("Int64")

    outfile.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(outfile, index=False, encoding="utf-8")
    print(f"[OK] Wide-Format Q10 gespeichert: {outfile} (rows={len(out)}, cols={len(out.columns)})")


def main():
    root = project_root()
    default_in = root / "data/survey/raw/Energieverbrauch und Teilnahmebereitschaft an Demand-Response-Programmen in Haushalten.csv"
    default_out = root / "data/survey/processed/question_10_incentive_wide.csv"

    ap = argparse.ArgumentParser(description="Preprocess Survey Q10 (Incentive wide)")
    ap.add_argument("--infile", type=str, default=str(default_in), help="Pfad zur Roh-CSV")
    ap.add_argument("--outfile", type=str, default=str(default_out), help="Pfad zur Ausgabe-CSV")
    ap.add_argument("--debug", action="store_true", help="Mehr Diagnoseausgaben")
    args = ap.parse_args()

    infile = Path(args.infile).resolve()
    outfile = Path(args.outfile).resolve()
    if not infile.exists():
        print(f"[ERROR] Input nicht gefunden: {infile}", file=sys.stderr)
        sys.exit(1)

    preprocess(infile, outfile, debug=args.debug)


if __name__ == "__main__":
    main()
