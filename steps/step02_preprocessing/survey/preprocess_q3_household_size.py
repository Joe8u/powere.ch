#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Preprocess Survey Q3 (Household Size):
- liest das SurveyMonkey-CSV,
- extrahiert respondent_id und Haushaltsgröße,
- normalisiert Sonderfälle (z. B. "über 6" -> 7, "6+" -> 7, ">6" -> 7),
- konvertiert zu numerisch,
- schreibt data/survey/processed/question_3_household_size.csv.

Aufruf (Repo-Root):
  python3 processing/survey/jobs/preprocess_q3_household_size.py
Optional mit Pfaden:
  python3 processing/survey/jobs/preprocess_q3_household_size.py \
    --infile "data/survey/raw/Energieverbrauch und Teilnahmebereitschaft an Demand-Response-Programmen in Haushalten.csv" \
    --outfile "data/survey/processed/question_3_household_size.csv"
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

    size_col = find_col_by_names(
        df_raw.columns,
        ["Wie viele Personen leben in Ihrem Haushalt?", "Haushaltsgröße", "Haushaltsgroesse", "Household size"]
    )
    if not size_col:
        raise KeyError("Spalte für Haushaltsgröße nicht gefunden.")

    df = df_raw[[resp_col, size_col]].copy()
    df.rename(columns={resp_col: "respondent_id", size_col: "household_size"}, inplace=True)

    # Normalisieren als String
    s = df["household_size"].astype(str).str.strip().str.lower()

    # Häufige Textvarianten auf "7" mappen (Interpretation: >6 Personen -> 7)
    replacements = {
        "über 6": "7",
        "ueber 6": "7",
        ">6": "7",
        "> 6": "7",
        "6+": "7",
        "mehr als 6": "7",
        "mehrals6": "7",
        "größer als 6": "7",
        "groesser als 6": "7",
    }
    for k, v in replacements.items():
        s = s.str.replace(k, v, regex=False)

    # Erste 1–2-stellige Zahl extrahieren (z. B. "3 Personen" -> 3)
    s = s.str.extract(r"(\d{1,2})", expand=False)

    # Zu numerisch
    df["household_size"] = pd.to_numeric(s, errors="coerce")

    # Ausgabeordner sicherstellen und schreiben
    outfile.parent.mkdir(parents=True, exist_ok=True)
    df[["respondent_id", "household_size"]].to_csv(outfile, index=False, encoding="utf-8")
    print(f"[OK] Geschrieben: {outfile}  (rows={len(df)})")


def main():
    root = project_root()
    default_in = root / "data/survey/raw/Energieverbrauch und Teilnahmebereitschaft an Demand-Response-Programmen in Haushalten.csv"
    default_out = root / "data/survey/processed/question_3_household_size.csv"

    ap = argparse.ArgumentParser(description="Preprocess Survey Q3 (Household Size)")
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
