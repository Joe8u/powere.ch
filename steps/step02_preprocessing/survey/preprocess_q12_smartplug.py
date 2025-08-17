#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
preprocess_q12_smartplug.py

Extrahiert Frage 12:
"Könnten Sie sich vorstellen, einen intelligenten Zwischenstecker (Smart Plug) an Ihren Geräten
zu installieren, damit Ihr Elektrizitätswerk Ihren Beitrag messen und Sie entsprechend vergüten kann?"

Schreibt: data/survey/processed/question_12_smartplug.csv
Schema: respondent_id, q12_smartplug

Aufruf (Repo-Root):
  python3 processing/survey/jobs/preprocess_q12_smartplug.py
Optional:
  python3 processing/survey/jobs/preprocess_q12_smartplug.py \
    --infile "data/survey/raw/Energieverbrauch und Teilnahmebereitschaft an Demand-Response-Programmen in Haushalten.csv" \
    --outfile "data/survey/processed/question_12_smartplug.csv" \
    --debug
"""

from __future__ import annotations
from pathlib import Path
import argparse
import re
import sys
import pandas as pd
from typing import Optional

# -------- Pfad-Helfer --------
def project_root() -> Path:
    try:
        return Path(__file__).resolve().parents[3]
    except NameError:
        return Path.cwd()


# -------- I/O --------
def read_raw_flat(path: Path) -> pd.DataFrame:
    """Liest den SurveyMonkey-Export so, dass die ERSTE Headerzeile (Fragen) als Spaltennamen bleibt.
    Die zweite Zeile („Response“, Gerätespalten etc.) wird übersprungen."""
    try:
        return pd.read_csv(path, header=0, skiprows=[1], dtype=str)
    except UnicodeDecodeError:
        return pd.read_csv(path, header=0, skiprows=[1], dtype=str, encoding="latin-1")


# -------- Erkennung & Normalisierung --------
Q12_PATTERN = re.compile(r"(smart\s*plug|zwischenstecker)", re.IGNORECASE)

def find_q12_column(columns: list[str], debug: bool = False) -> str | None:
    """Sucht die Q12-Frage-Spalte über einen toleranten Regex."""
    candidates = []
    for c in columns:
        if not isinstance(c, str):
            continue
        name = c.strip()
        if not name:
            continue
        if Q12_PATTERN.search(name):
            candidates.append(name)

    if debug:
        print(f"[DEBUG] Q12-Kandidaten: {candidates}")

    if not candidates:
        return None
    # Falls mehrere Treffer: nimm den längsten (meist der volle Fragetext)
    candidates.sort(key=len, reverse=True)
    return candidates[0]


def normalize_choice(val: Optional[str]) -> Optional[str]:
    if val is None or pd.isna(val):
        return None
    s = str(val).strip()
    if not s or s.lower() == "nan":
        return None

    low = s.lower()
    if low.startswith("ja") or low in {"y", "yes"}:
        return "Ja"
    if low.startswith("nein") or low in {"n", "no"}:
        return "Nein"
    return s[:1].upper() + s[1:]

    low = s.lower()
    # Ja-Varianten
    if low.startswith("ja") or low in {"y", "yes"}:
        return "Ja"
    # Nein-Varianten
    if low.startswith("nein") or low in {"n", "no"}:
        return "Nein"
    # 'weiss nicht' o.ä. so lassen, aber mit großem Anfangsbuchstaben
    return s[:1].upper() + s[1:]


# -------- Hauptlogik --------
def preprocess(infile: Path, outfile: Path, debug: bool = False) -> None:
    root = project_root()
    print(f"[INFO] Repo-Root: {root}")
    print(f"[INFO] Input CSV: {infile}")
    print(f"[INFO] Output:    {outfile}")

    df = read_raw_flat(infile)

    if "respondent_id" not in df.columns:
        print("[ERROR] 'respondent_id' nicht gefunden.", file=sys.stderr)
        sys.exit(1)

    q12_col = find_q12_column(df.columns.tolist(), debug=debug)
    if not q12_col:
        print("[ERROR] Konnte die Q12-Spalte (Smart Plug / Zwischenstecker) nicht finden.", file=sys.stderr)
        if debug:
            print("[DEBUG] Verfügbare Spalten:")
            for c in df.columns:
                print("  -", c)
        sys.exit(1)

    if debug:
        print(f"[DEBUG] Verwende Q12-Spalte: {q12_col!r}")

    out = df[["respondent_id", q12_col]].copy()
    out.rename(columns={q12_col: "q12_smartplug"}, inplace=True)
    out["q12_smartplug"] = (
    out["q12_smartplug"]
      .map(normalize_choice)
      .astype("string")   # None -> <NA>
)

    outfile.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(outfile, index=False, encoding="utf-8")
    print(f"[OK] Q12 (Smart Plug) gespeichert: {outfile} (rows={len(out)})")


def main():
    root = project_root()
    default_in = root / "data/survey/raw/Energieverbrauch und Teilnahmebereitschaft an Demand-Response-Programmen in Haushalten.csv"
    default_out = root / "data/survey/processed/question_12_smartplug.csv"

    ap = argparse.ArgumentParser(description="Preprocess Survey Q12 (Smart Plug)")
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