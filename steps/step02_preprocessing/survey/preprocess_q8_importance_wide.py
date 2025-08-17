#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Preprocess Survey Q8 (Importance ratings, wide):
- liest das Survey-CSV (SurveyMonkey: 2. Kopfzeile wird übersprungen),
- findet 'respondent_id' und die Q8-Fragespalte robust,
- liest die Geräte-Namen aus der zweiten Header-Zeile,
- pars’t die 6 Ratings (1–5) zu ganzzahligen Werten (nullable Int64),
- schreibt wide: respondent_id + 6 Gerätespalten.

Aufruf (Repo-Root):
  python3 processing/survey/jobs/preprocess_q8_importance_wide.py
  # oder:
  python3 processing/survey/jobs/preprocess_q8_importance_wide.py --infile ... --outfile ...
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


def read_second_header_row(path: Path) -> list[str]:
    # Liest exakt die zweite Datei-Zeile (erste Datenzeile), die Options-/Labels enthält
    try:
        row = pd.read_csv(path, header=None, skiprows=1, nrows=1, dtype=str)
    except UnicodeDecodeError:
        row = pd.read_csv(path, header=None, skiprows=1, nrows=1, dtype=str, encoding="latin-1")
    return row.iloc[0].tolist()


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


# ---------- Parsing ----------
RATING_RE = re.compile(r"^\s*([1-5])")


def parse_rating(x):
    """String wie '5 = sehr wichtig' oder '5' -> int; sonst <NA>."""
    if x is None or pd.isna(x):
        return pd.NA
    s = str(x).strip()
    m = RATING_RE.match(s)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return pd.NA
    return pd.NA


CANON_DEVICE_NAMES = {
    "geschirrspüler": "Geschirrspüler",
    "backofenundherd": "Backofen und Herd",
    "fernseherundentertainment-systeme": "Fernseher und Entertainment-Systeme",
    "fernseherundentertainmentsysteme": "Fernseher und Entertainment-Systeme",
    "bürogerate": "Bürogeräte",
    "burogerate": "Bürogeräte",
    "waschmaschine": "Waschmaschine",
    "staubsauger": "Staubsauger",
}


def canonicalize_device_label(label: str) -> str:
    key = _norm_key(label)
    return CANON_DEVICE_NAMES.get(key, label.strip() if isinstance(label, str) else label)


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

    # Q8-Frage finden (exakte Kandidaten, sonst fuzzy)
    q8_candidates = [
        "Bitte bewerten Sie, wie wichtig es für Sie ist, die folgenden Haushaltsgeräte jederzeit nutzen zu können (1 = sehr unwichtig, 5 = sehr wichtig)",
        "Bitte bewerten Sie, wie wichtig es für Sie ist, die folgenden Haushaltsgeräte jederzeit nutzen zu können (1=sehr unwichtig, 5=sehr wichtig)",
    ]
    q8_col = find_col_by_names(df.columns, q8_candidates)
    if not q8_col:
        q8_col = find_col_contains(df.columns, "bewertensie", "wichtig", "haushaltsgerate")
    if not q8_col:
        raise KeyError("Q8-Fragespalte nicht gefunden.")

    # Position der Q8-Frage und zweite Header-Zeile
    q_idx: int = list(df.columns).index(q8_col)
    second = read_second_header_row(infile)

    # Zwei mögliche Slices testen: ohne +1 (Standard) und mit +1 (Fallback)
    slice0 = second[q_idx : q_idx + 6]
    slice1 = second[q_idx + 1 : q_idx + 7] if q_idx + 7 <= len(second) else []

    def score_slice(vals: list[str]) -> int:
        vals_str = [str(v) if v is not None else "" for v in vals]
        nonempty = sum(1 for v in vals_str if v and v.lower() != "response")
        bonus = sum(1 for v in vals_str if _norm_key(v) in CANON_DEVICE_NAMES)
        return nonempty + bonus

    chosen_offset = 0
    if score_slice(slice1) > score_slice(slice0):
        chosen_offset = 1

    # Start/Ende einmal ausrechnen (klar typisiert)
    start = q_idx + chosen_offset
    end = start + 6

    appliances_raw = second[start:end]
    if len(appliances_raw) != 6:
        print(f"[ERROR] Erwartet 6 Gerätebezeichner, gefunden {len(appliances_raw)}: {appliances_raw}", file=sys.stderr)
        sys.exit(1)

    appliances = [canonicalize_device_label(a) for a in appliances_raw]

    # Spalten per **Namen** auswählen statt per Integer-Index
    start: int = int(start)
    end: int = int(end)
    rating_col_names = list(df.columns[start:end])
    cols_names = [resp_col] + rating_col_names
    data = df.loc[:, cols_names].copy()
    data.columns = ["respondent_id"] + appliances

    # Ratings parsen -> nullable Int64
    for col in appliances:
        data[col] = data[col].map(parse_rating).astype("Int64")

    # Schreiben
    outfile.parent.mkdir(parents=True, exist_ok=True)
    data["respondent_id"] = data["respondent_id"].astype("string")
    data.to_csv(outfile, index=False, encoding="utf-8")

    # kurze Statistik
    filled = {col: int(data[col].notna().sum()) for col in appliances}
    print(f"[OK] Geschrieben: {outfile}")
    print("[INFO] Nicht-NA pro Spalte:", filled)


def main():
    root = project_root()
    default_in = root / "data/survey/raw/Energieverbrauch und Teilnahmebereitschaft an Demand-Response-Programmen in Haushalten.csv"
    default_out = root / "data/survey/processed/question_8_importance_wide.csv"

    ap = argparse.ArgumentParser(description="Preprocess Survey Q8 (Importance, wide)")
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