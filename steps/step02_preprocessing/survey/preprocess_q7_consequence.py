#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Preprocess Survey Q7 (problematische Konsequenzen):
- liest das Survey-CSV (SurveyMonkey: 2. Kopfzeile wird übersprungen),
- findet 'respondent_id' und die Q7-Spalte robust (exakte Kandidaten + fuzzy),
- trimmt Werte, wandelt leere Platzhalter in NA,
- schreibt data/survey/processed/question_7_consequence.csv.

Aufruf (Repo-Root):
  python3 processing/survey/jobs/preprocess_q7_consequence.py
  # oder mit Argumenten:
  python3 processing/survey/jobs/preprocess_q7_consequence.py --infile ... --outfile ...
"""

from __future__ import annotations
import argparse
from pathlib import Path
import sys
import re
import pandas as pd


# ---------- Pfad-/IO-Helfer ----------
def project_root() -> Path:
    try:
        return Path(__file__).resolve().parents[3]
    except NameError:
        return Path.cwd()


def read_raw_csv(path: Path) -> pd.DataFrame:
    # SurveyMonkey-Export: zweite Kopfzeile (Options-/Response-Zeile) überspringen
    try:
        return pd.read_csv(path, encoding="utf-8", sep=",", header=0, skiprows=[1], dtype=str)
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="latin-1", sep=",", header=0, skiprows=[1], dtype=str)


def _norm_key(s: str) -> str:
    return (
        str(s).lower()
        .replace(" ", "")
        .replace("?", "")
        .replace("*", "")
        .replace("(", "")
        .replace(")", "")
        .replace(",", "")
        .replace("„", "")
        .replace("“", "")
        .replace("’", "")
        .replace("'", "")
        .replace("-", "-")
        .replace("–", "-")
        .replace("—", "-")
        .strip()
    )


def find_col_by_names(columns, candidates):
    # erst exakte, dann normalisierte Treffer
    for c in candidates:
        if c in columns:
            return c
    norm_map = {_norm_key(col): col for col in columns}
    for c in candidates:
        k = _norm_key(c)
        if k in norm_map:
            return norm_map[k]
    return None


def find_col_contains(columns, *tokens):
    toks = [_norm_key(t) for t in tokens]
    for col in columns:
        key = _norm_key(col)
        if all(t in key for t in toks):
            return col
    return None


# ---------- Werte-Bereinigung ----------
EMPTY_PAT = re.compile(r"^\s*(nan|null|none|na|n/a|-+)?\s*$", re.IGNORECASE)


def clean_choice(val):
    """Trim, leere/NA-ähnliche Platzhalter -> None"""
    if val is None or pd.isna(val):
        return None
    s = str(val).strip()
    if not s or EMPTY_PAT.match(s):
        return None
    return s


# ---------- Hauptlogik ----------
def preprocess(infile: Path, outfile: Path) -> None:
    print(f"[INFO] Repo-Root: {project_root()}")
    print(f"[INFO] Input CSV: {infile}")
    print(f"[INFO] Output:    {outfile}")

    df = read_raw_csv(infile)

    # respondent_id robust finden
    resp_col = find_col_by_names(df.columns, ["respondent_id", "Respondent ID", "respondent id"])
    if not resp_col:
        raise KeyError("respondent_id-Spalte nicht gefunden.")

    # Q7-Spalte finden: exakte Kandidaten, dann fuzzy auf 'Konsequenzen' + 'problematisch'
    q7_candidates = [
        "Welche der folgenden Konsequenzen der zunehmenden Einspeisung von erneuerbaren Energien ist aus Ihrer Sicht problematisch? (Nur eine Antwort möglich)?",
        "Welche der folgenden Konsequenzen der zunehmenden Einspeisung von erneuerbaren Energien ist aus Ihrer Sicht problematisch? (Nur eine Antwort möglich)",
        "Welche der folgenden Konsequenzen ist problematisch?",
    ]
    q7_col = find_col_by_names(df.columns, q7_candidates)
    if not q7_col:
        q7_col = find_col_contains(df.columns, "konsequenzen", "problematisch")
    if not q7_col:
        # letzte Chance: nur "konsequenzen"
        q7_col = find_col_contains(df.columns, "konsequenzen")
    if not q7_col:
        raise KeyError("Q7-Spalte (Konsequenzen) nicht gefunden.")

    # Ausgabe-DataFrame
    df_out = df[[resp_col]].copy()
    df_out.rename(columns={resp_col: "respondent_id"}, inplace=True)
    df_out["consequence"] = df[q7_col].map(clean_choice).astype("string")

    # schreiben
    outfile.parent.mkdir(parents=True, exist_ok=True)
    df_out["respondent_id"] = df_out["respondent_id"].astype("string")
    df_out.to_csv(outfile, index=False, encoding="utf-8")

    total = len(df_out)
    na_count = df_out["consequence"].isna().sum()
    print(f"[OK] Geschrieben: {outfile}  (rows={total}, ohne Auswahl={na_count})")


def main():
    root = project_root()
    default_in = root / "data/survey/raw/Energieverbrauch und Teilnahmebereitschaft an Demand-Response-Programmen in Haushalten.csv"
    default_out = root / "data/survey/processed/question_7_consequence.csv"

    ap = argparse.ArgumentParser(description="Preprocess Survey Q7 (Konsequenzen)")
    ap.add_argument("--infile", type=str, default=str(default_in), help="Pfad zur Roh-CSV")
    ap.add_argument("--outfile", type=str, default=str(default_out), help="Pfad zur Ausgabe-CSV")
    args = ap.parse_args()

    infile = Path(args.infile).resolve()
    outfile = Path(args.outfile).resolve()
    if not infile.exists():
        print(f"[ERROR] Input nicht gefunden: {infile}", file=sys.stderr)
        sys.exit(1)

    preprocess(infile, outfile)


if __name__ == "__main__":
    main()
