#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Preprocess Survey Q1 (Age):
- liest das SurveyMonkey-CSV,
- extrahiert respondent_id und Alter,
- normalisiert Sonderfälle ("unter 18" -> 17, "über 95" -> 96),
- konvertiert Alter zu numerisch,
- schreibt data/survey/processed/question_1_age.csv.

Aufruf (Repo-Root):
  python3 processing/survey/jobs/preprocess_q1_age.py
Optional mit Pfaden:
  python3 processing/survey/jobs/preprocess_q1_age.py \
    --infile "data/survey/raw/Energieverbrauch und Teilnahmebereitschaft an Demand-Response-Programmen in Haushalten.csv" \
    --outfile "data/survey/processed/question_1_age.csv"
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

    # Spalten ermitteln
    resp_col = find_col_by_names(
        df_raw.columns,
        ["respondent_id", "Respondent ID", "respondent id"]
    )
    if not resp_col:
        raise KeyError("respondent_id-Spalte nicht gefunden.")

    age_col = find_col_by_names(
        df_raw.columns,
        ["Wie alt sind Sie?", "Wie alt sind Sie?*", "Age", "Alter"]
    )
    if not age_col:
        raise KeyError("Alters-Spalte (z. B. 'Wie alt sind Sie?') nicht gefunden.")

    df = df_raw[[resp_col, age_col]].copy()
    df.rename(columns={resp_col: "respondent_id", age_col: "age"}, inplace=True)

    # Normalisieren -> string
    s = df["age"].astype(str).str.strip().str.lower()

    # Häufige Varianten ersetzen
    replacements = {
        "unter 18": "17",
        "über 95": "96",
        "ueber 95": "96",
        "über95": "96",
        "<18": "17",
        ">95": "96",
    }
    s = s.replace(replacements, regex=False)

    # Erste 1–3-stellige Zahl aus dem String extrahieren, Rest verwerfen
    s = s.str.extract(r"(\d{1,3})", expand=False)

    # Zu numerisch
    df["age"] = pd.to_numeric(s, errors="coerce")

    # Ausgabeordner sicherstellen
    outfile.parent.mkdir(parents=True, exist_ok=True)
    df[["respondent_id", "age"]].to_csv(outfile, index=False, encoding="utf-8")
    print(f"[OK] Geschrieben: {outfile}  (rows={len(df)})")


def main():
    root = project_root()
    default_in = root / "data/survey/raw/Energieverbrauch und Teilnahmebereitschaft an Demand-Response-Programmen in Haushalten.csv"
    default_out = root / "data/survey/processed/question_1_age.csv"

    ap = argparse.ArgumentParser(description="Preprocess Survey Q1 (Age)")
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