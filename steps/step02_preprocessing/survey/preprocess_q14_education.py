#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
preprocess_q14_education.py

Extrahiert Frage 14:
"Was ist Ihr höchster Bildungsabschluss?"
und schreibt: data/survey/processed/question_14_education.csv

Aufruf (Repo-Root):
  python3 processing/survey/jobs/preprocess_q14_education.py
Optional:
  python3 processing/survey/jobs/preprocess_q14_education.py <input.csv> <output.csv>
"""

from __future__ import annotations
import os
import sys
import re
import pandas as pd


# ---------- Pfade ----------
BASE_DIR = os.path.abspath(os.path.join(__file__, os.pardir, os.pardir, os.pardir, os.pardir))

# vorher: 'data', 'raw', 'survey'
RAW_DIR = os.path.join(BASE_DIR, 'data', 'survey', 'raw')
# vorher: 'data', 'processed', 'survey' ist ok – aber zur Einheitlichkeit:
OUT_DIR = os.path.join(BASE_DIR, 'data', 'survey', 'processed')

RAW_FILENAME = 'Energieverbrauch und Teilnahmebereitschaft an Demand-Response-Programmen in Haushalten.csv'
OUT_FILENAME = 'question_14_education.csv'

RAW_PATH = os.path.join(RAW_DIR, RAW_FILENAME)
OUT_PATH = os.path.join(OUT_DIR, OUT_FILENAME)


# ---------- Helpers ----------
def _read_csv_any_encoding(path: str) -> pd.DataFrame:
    try:
        return pd.read_csv(path, header=0, skiprows=[1], dtype=str)
    except UnicodeDecodeError:
        return pd.read_csv(path, header=0, skiprows=[1], dtype=str, encoding="latin-1")


def _find_col_contains(df: pd.DataFrame, needle: str) -> str | None:
    """Finde erste Spalte, deren Name 'needle' (case-insensitive) enthält."""
    low = needle.lower()
    for c in df.columns:
        if isinstance(c, str) and low in c.lower():
            return c
    return None


def _normalize_education(x: str) -> str:
    """
    Normalisiert verschiedene Schreibweisen auf eine kleine Menge kanonischer Kategorien.
    Leere/fehlende Eingaben -> 'Keine Angabe'.
    """
    if x is None:
        return "Keine Angabe"
    s = str(x).strip()
    if s == "" or s.lower() in {"nan", "na", "n/a"}:
        return "Keine Angabe"

    s_low = s.lower()

    # Reihenfolge wichtig: spezifisch -> allgemein
    patterns = [
        (r"(doktor|ph\.?d|dr\.)",                 "Doktorat/PhD"),
        (r"\bmaster\b|msc|m\.a\.",                "Master"),
        (r"\bbachelor\b|bsc|b\.a\.",              "Bachelor"),
        (r"fachhochschule|\bfh\b",                 "Fachhochschule"),
        (r"universit|eth",                         "Universität/ETH"),
        (r"berufsausbildung|lehre|matur",         "Berufsausbildung/Lehre/Maturität"),
        (r"\bander",                               "Andere"),
        (r"keine angabe|keine antwort|weiss nicht|weiß nicht|unbekannt|prefer not", "Keine Angabe"),
    ]
    for pat, label in patterns:
        if re.search(pat, s_low):
            return label

    # Falls die Originaloption bereits eine klare Kategorie ist, so belassen:
    return s


# ---------- Hauptfunktion ----------
def preprocess_q14_education(raw_csv: str, out_csv: str) -> None:
    # 1) Einlesen
    df = _read_csv_any_encoding(raw_csv)

    # 2) respondent_id prüfen
    if "respondent_id" not in df.columns:
        print("Spalte 'respondent_id' nicht gefunden.", file=sys.stderr)
        sys.exit(1)

    # 3) Q14-Spalte finden
    q14_col = _find_col_contains(df, "Bildungsabschluss")
    if not q14_col:
        print("Konnte Q14 nicht finden (Spalte mit 'Bildungsabschluss').", file=sys.stderr)
        print("Verfügbare Spalten-Beispiele:", list(df.columns)[:10], file=sys.stderr)
        sys.exit(1)
    print(f"[INFO] Q14-Spalte: {q14_col!r}")

    # 4) respondent_id + Roh-Antwort extrahieren
    out = df[["respondent_id", q14_col]].copy()
    out.rename(columns={q14_col: "q14_education_raw"}, inplace=True)

    # 5) Normalisieren
    out["q14_education"] = out["q14_education_raw"].apply(_normalize_education)
    out.drop(columns=["q14_education_raw"], inplace=True)

    # 6) Speichern
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    out.to_csv(out_csv, index=False, encoding="utf-8")
    print(f"[OK] Q14 gespeichert: {out_csv} (rows={len(out)})")

    # Optional: kleine Verteilungsausgabe
    vc = out["q14_education"].value_counts(dropna=False).sort_index()
    print("[INFO] Verteilung q14_education:")
    print(vc)


# ---------- CLI ----------
if __name__ == "__main__":
    if len(sys.argv) == 1:
        preprocess_q14_education(RAW_PATH, OUT_PATH)
    elif len(sys.argv) == 3:
        _, raw, out = sys.argv
        preprocess_q14_education(raw, out)
    else:
        print(
            "Usage:\n"
            "  python preprocess_q14_education.py\n"
            "  python preprocess_q14_education.py <input.csv> <output.csv>",
            file=sys.stderr
        )
        sys.exit(1)
