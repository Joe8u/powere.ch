#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
preprocess_q15_party.py

Extrahiert Frage 15:
"Welche der folgenden Parteien entspricht am ehesten Ihrer politischen Präferenz?"
und schreibt: respondent_id, q15_party

Aufruf (Repo-Root):
  python3 processing/survey/jobs/preprocess_q15_party.py
  # oder mit eigenen Pfaden:
  python3 processing/survey/jobs/preprocess_q15_party.py "<raw.csv>" "<out.csv>"
"""

from __future__ import annotations
from pathlib import Path
import sys
import pandas as pd


# ---------------- Pfad-Helper ----------------
def repo_root() -> Path:
    try:
        return Path(__file__).resolve().parents[3]
    except NameError:
        return Path.cwd()


RAW_FILENAME = "Energieverbrauch und Teilnahmebereitschaft an Demand-Response-Programmen in Haushalten.csv"
RAW_PATH = repo_root() / "data/survey/raw" / RAW_FILENAME
OUT_PATH = repo_root() / "data/survey/processed" / "question_15_party.csv"


# --------------- IO-Utilities ---------------
def _read_csv_any_encoding(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path, header=0, skiprows=[1], dtype=str)
    except UnicodeDecodeError:
        return pd.read_csv(path, header=0, skiprows=[1], dtype=str, encoding="latin-1")


def _find_q15_column(columns) -> str | None:
    """
    Suche nach der Q15-Spalte; tolerant auf 'Partei' / 'politisch' im Header.
    """
    for c in columns:
        if isinstance(c, str):
            low = c.lower()
            if "partei" in low or "politisch" in low:
                return c
    return None


# --------------- Hauptlogik -----------------
def preprocess_q15_party(raw_csv: str, out_csv: str) -> None:
    raw_p = Path(raw_csv)
    out_p = Path(out_csv)

    print(f"[INFO] Repo-Root: {repo_root()}")
    print(f"[INFO] Input CSV: {raw_p}")
    print(f"[INFO] Output:    {out_p}")

    df = _read_csv_any_encoding(raw_p)

    # respondent_id prüfen
    if "respondent_id" not in df.columns:
        print("[ERROR] 'respondent_id' nicht gefunden.", file=sys.stderr)
        sys.exit(1)

    # Q15-Spalte identifizieren
    q15_col = _find_q15_column(df.columns)
    if not q15_col:
        print("[ERROR] Q15-Spalte (Parteipräferenz) nicht gefunden.", file=sys.stderr)
        print("        Verfügbare Spalten-Beispiele:", list(df.columns)[:12], file=sys.stderr)
        sys.exit(1)
    print(f"[INFO] Q15-Spalte: {q15_col!r}")

    # respondent_id + Rohantwort holen
    out = df[["respondent_id", q15_col]].copy()
    out.rename(columns={q15_col: "q15_party_raw"}, inplace=True)

    # Bereinigung: leer/NA/„keine …“ -> "Keine Angabe", sonst trimmen
    def clean_party(x: str) -> str:
        if pd.isna(x):
            return "Keine Angabe"
        s = str(x).strip()
        if not s or s.lower().startswith("keine"):
            return "Keine Angabe"
        return s

    out["q15_party"] = out["q15_party_raw"].apply(clean_party)
    out.drop(columns=["q15_party_raw"], inplace=True)

    # Speichern
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_p, index=False, encoding="utf-8")
    print(f"[OK] Q15 (Parteipräferenz) gespeichert: {out_p} (rows={len(out)})")

    # kleine Distribution zur Kontrolle
    vc = out["q15_party"].value_counts(dropna=False)
    print("[INFO] Verteilung q15_party:")
    print(vc)


# --------------- CLI ------------------------
if __name__ == "__main__":
    if len(sys.argv) == 1:
        preprocess_q15_party(str(RAW_PATH), str(OUT_PATH))
    elif len(sys.argv) == 3:
        _, raw, out = sys.argv
        preprocess_q15_party(raw, out)
    else:
        print(
            "Usage:\n"
            "  python3 processing/survey/jobs/preprocess_q15_party.py\n"
            '  python3 processing/survey/jobs/preprocess_q15_party.py "<raw.csv>" "<out.csv>"',
            file=sys.stderr,
        )
        sys.exit(1)
