#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Preprocess Survey Q2 (Gender):
- liest das SurveyMonkey-CSV,
- extrahiert respondent_id und Geschlecht,
- schreibt data/survey/processed/question_2_gender.csv.

Aufruf (Repo-Root):
  python3 processing/survey/jobs/preprocess_q2_gender.py
Optional mit Pfaden:
  python3 processing/survey/jobs/preprocess_q2_gender.py \
    --infile "data/survey/raw/Energieverbrauch und Teilnahmebereitschaft an Demand-Response-Programmen in Haushalten.csv" \
    --outfile "data/survey/processed/question_2_gender.csv"
"""

from __future__ import annotations
import argparse
from pathlib import Path
import sys
import pandas as pd


def project_root() -> Path:
    # Datei liegt unter: processing/survey/jobs/... -> drei Ebenen hoch = Repo-Root
    try:
        return Path(__file__).resolve().parents[3]
    except NameError:
        return Path.cwd()


def read_raw_csv(path: Path) -> pd.DataFrame:
    # SurveyMonkey-Exporte haben oft eine zweite „Header“-Zeile -> skiprows=[1]
    try:
        return pd.read_csv(path, encoding="utf-8", sep=",", header=0, skiprows=[1])
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="latin-1", sep=",", header=0, skiprows=[1])


def find_col_by_names(columns, candidates):
    # exakte Kandidaten zuerst
    for c in candidates:
        if c in columns:
            return c
    # toleranter: normalisieren (lower, ohne Leerzeichen/?,*)
    norm = {str(col).lower().replace(" ", "").replace("?", "").replace("*", ""): col for col in columns}
    for c in candidates:
        key = c.lower().replace(" ", "").replace("?", "").replace("*", "")
        if key in norm:
            return norm[key]
    return None


def preprocess(infile: Path, outfile: Path) -> None:
    print(f"[INFO] Repo-Root: {project_root()}")
    print(f"[INFO] Input CSV: {infile}")
    print(f"[INFO] Output:    {outfile}")

    df_raw = read_raw_csv(infile)

    # Spalten finden
    resp_col = find_col_by_names(
        df_raw.columns,
        ["respondent_id", "Respondent ID", "respondent id"]
    )
    if not resp_col:
        raise KeyError("respondent_id-Spalte nicht gefunden.")

    gender_col = find_col_by_names(
        df_raw.columns,
        ["Was ist Ihr Geschlecht?", "Was ist Ihr Geschlecht?*", "Gender", "Geschlecht"]
    )
    if not gender_col:
        raise KeyError("Geschlechts-Spalte (z. B. 'Was ist Ihr Geschlecht?') nicht gefunden.")

    df = df_raw[[resp_col, gender_col]].copy()
    df.rename(columns={resp_col: "respondent_id", gender_col: "gender"}, inplace=True)

    # (Optional) Trim/Normalisierung – wir lassen Originalwerte bestehen
    df["gender"] = df["gender"].astype(str).str.strip()

    # Ausgabeordner sicherstellen
    outfile.parent.mkdir(parents=True, exist_ok=True)
    df[["respondent_id", "gender"]].to_csv(outfile, index=False, encoding="utf-8")
    print(f"[OK] Geschrieben: {outfile}  (rows={len(df)})")


def main():
    root = project_root()
    default_in = root / "data/survey/raw/Energieverbrauch und Teilnahmebereitschaft an Demand-Response-Programmen in Haushalten.csv"
    default_out = root / "data/survey/processed/question_2_gender.csv"

    ap = argparse.ArgumentParser(description="Preprocess Survey Q2 (Gender)")
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
