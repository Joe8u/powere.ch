#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Preprocess Survey Q9 (Non-use willingness, wide)
- liest Survey-CSV (SurveyMonkey: 2. Kopfzeile wird übersprungen),
- findet respondent_id und Q9-Fragespalte robust,
- liest 6 Gerätenamen aus der zweiten Header-Zeile,
- schreibt wide: respondent_id + 6 Gerätespalten (bereinigte Strings).
"""

from __future__ import annotations
import argparse
from pathlib import Path
import sys
import pandas as pd

# -------- kleine Utils --------
def project_root() -> Path:
    try:
        return Path(__file__).resolve().parents[3]
    except NameError:
        return Path.cwd()

def read_raw_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path, encoding="utf-8", sep=",", header=0, skiprows=[1], dtype=str)
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="latin-1", sep=",", header=0, skiprows=[1], dtype=str)

def read_second_header_row(path: Path) -> list[str]:
    try:
        row = pd.read_csv(path, header=None, skiprows=1, nrows=1, dtype=str)
    except UnicodeDecodeError:
        row = pd.read_csv(path, header=None, skiprows=1, nrows=1, dtype=str, encoding="latin-1")
    return row.iloc[0].tolist()

def _norm_key(s: str) -> str:
    if s is None:
        return ""
    return (
        str(s).lower()
        .replace("ä","ae").replace("ö","oe").replace("ü","ue").replace("ß","ss")
        .replace(" ", "").replace("?", "").replace("*", "")
        .replace("(", "").replace(")", "").replace(",", "")
        .replace("„","").replace("“","").replace("’","").replace("'","")
        .replace("–","-").replace("—","-")
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

# Kanonische Gerätenamen (wie in Q8)
CANON_DEVICE_NAMES = {
    "geschirrspueler": "Geschirrspüler",
    "geschirrspüler": "Geschirrspüler",
    "backofenundherd": "Backofen und Herd",
    "fernseherundentertainment-systeme": "Fernseher und Entertainment-Systeme",
    "fernseherundentertainmentsysteme": "Fernseher und Entertainment-Systeme",
    "buerogeraete": "Bürogeräte",
    "bürogeräte": "Bürogeräte",
    "burogerate": "Bürogeräte",
    "waschmaschine": "Waschmaschine",
    "staubsauger": "Staubsauger",
}

def canonicalize_device_label(label: str):
    key = _norm_key(label)
    return CANON_DEVICE_NAMES.get(key, (label.strip() if isinstance(label, str) else label))

# -------- Hauptlogik --------
def preprocess(infile: Path, outfile: Path) -> None:
    print(f"[INFO] Repo-Root: {project_root()}")
    print(f"[INFO] Input CSV: {infile}")
    print(f"[INFO] Output:    {outfile}")

    df = read_raw_csv(infile)

    # respondent_id robust finden
    resp_col = find_col_by_names(df.columns, ["respondent_id", "Respondent ID", "respondent id"])
    if not resp_col:
        raise KeyError("respondent_id-Spalte nicht gefunden.")

    # Q9-Frage (exakter Text als Kandidaten + Fallbacks)
    q9_candidates = [
        "Könnten Sie sich vorstellen, eines der folgenden Haushaltsgeräte für einen begrenzten Zeitraum nicht einzuschalten, wenn Sie vom Elektrizitätswerk darum gebeten werden?",
    ]
    q9_col = find_col_by_names(df.columns, q9_candidates)
    if not q9_col:
        # leichter Fallback über Tokens
        for col in df.columns:
            key = _norm_key(col)
            if all(t in key for t in ["vorstell", "geraete", "nicht", "einschalten"]):
                q9_col = col
                break
    if not q9_col:
        raise KeyError("Q9-Fragespalte nicht gefunden.")

    # fester int-Index + zweite Header-Zeile
    q_idx: int = list(df.columns).index(q9_col)
    second = read_second_header_row(infile)

    # Offset bestimmen: direkt ab Frage vs. +1 verschoben
    slice0 = second[q_idx : q_idx + 6]
    slice1 = second[q_idx + 1 : q_idx + 7] if q_idx + 7 <= len(second) else []

    def score(vals: list[str]) -> int:
        vals = [str(v) if v is not None else "" for v in vals]
        nonempty = sum(1 for v in vals if v and v.lower() != "response")
        bonus = sum(1 for v in vals if _norm_key(v) in CANON_DEVICE_NAMES)
        return nonempty + bonus

    chosen_offset: int = 1 if score(slice1) > score(slice0) else 0

    # Start/Ende (klar typisiert) und Gerätenamen
    start: int = q_idx + chosen_offset
    end: int = start + 6
    appliances_raw = second[start:end]
    if len(appliances_raw) != 6:
        print(f"[ERROR] Erwartet 6 Gerätebezeichner, gefunden {len(appliances_raw)}: {appliances_raw}", file=sys.stderr)
        sys.exit(1)

    appliances = [canonicalize_device_label(a) for a in appliances_raw]

    # Spalten per Namen (statt Integer-Mix) auswählen
    rating_col_names = [df.columns[i] for i in range(start, end)]
    cols_names = [resp_col] + rating_col_names
    data = df.loc[:, cols_names].copy()
    data.columns = ["respondent_id"] + appliances

    # Werte säubern: leere/nan -> <NA>, Whitespace kürzen
    for col in appliances:
        s = data[col].astype("string").str.strip()
        s = s.replace({"": pd.NA, "nan": pd.NA, "NaN": pd.NA})
        data[col] = s

    data["respondent_id"] = data["respondent_id"].astype("string")

    # Schreiben
    outfile.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(outfile, index=False, encoding="utf-8")

    # kurze Statistik
    filled = {col: int(data[col].notna().sum()) for col in appliances}
    print(f"[OK] Geschrieben: {outfile}")
    print("[INFO] Nicht-NA pro Spalte:", filled)

def main():
    root = project_root()
    default_in = root / "data/survey/raw/Energieverbrauch und Teilnahmebereitschaft an Demand-Response-Programmen in Haushalten.csv"
    default_out = root / "data/survey/processed/question_9_nonuse_wide.csv"

    ap = argparse.ArgumentParser(description="Preprocess Survey Q9 (Non-use willingness, wide)")
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
