#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Preprocess Survey Q4 (Accommodation type):
- liest das Survey-CSV,
- findet 'respondent_id' und die Spalten-Gruppe zu
  "In welcher Art von Unterkunft wohnen Sie?" (Frage + folgende Options-Spalten),
- extrahiert die erste gültige Auswahl als eine von vier Kanon-Kategorien,
- schreibt data/survey/processed/question_4_accommodation.csv.

Aufruf (Repo-Root):
  python3 processing/survey/jobs/preprocess_q4_accommodation.py
Optional:
  python3 processing/survey/jobs/preprocess_q4_accommodation.py \
    --infile "data/survey/raw/Energieverbrauch und Teilnahmebereitschaft an Demand-Response-Programmen in Haushalten.csv" \
    --outfile "data/survey/processed/question_4_accommodation.csv"
"""

from __future__ import annotations
import argparse
from pathlib import Path
from typing import Optional, List
import sys
import pandas as pd

FOUR_CANON: List[str] = [
    "Wohnung (Eigentum)",
    "Wohnung (Miete)",
    "Haus (Miete)",
    "Haus (Eigentum)",
]

def project_root() -> Path:
    try:
        return Path(__file__).resolve().parents[3]
    except NameError:
        return Path.cwd()

def read_raw_csv(path: Path) -> pd.DataFrame:
    # SurveyMonkey: zweite Kopfzeile (Options-/Response-Zeile) überspringen
    # Strings beibehalten (dtype=str), damit wir frei normalisieren können.
    try:
        return pd.read_csv(path, encoding="utf-8", sep=",", header=0, skiprows=[1], dtype=str)
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="latin-1", sep=",", header=0, skiprows=[1], dtype=str)

def find_col_by_names(columns, candidates) -> Optional[str]:
    # 1) exakte Treffer
    for c in candidates:
        if c in columns:
            return c
    # 2) tolerante Normalisierung
    norm = {str(col).lower().replace(" ", "").replace("?", "").replace("*", ""): col for col in columns}
    for c in candidates:
        key = c.lower().replace(" ", "").replace("?", "").replace("*", "")
        if key in norm:
            return norm[key]
    return None

def normalize_accommodation(val: Optional[str]) -> Optional[str]:
    if val is None or pd.isna(val):
        return None
    s = str(val).strip()
    if not s:
        return None
    if s in FOUR_CANON:
        return s

    sl = s.lower()
    has_whg = "wohnung" in sl
    has_haus = "haus" in sl
    has_miete = "miete" in sl
    has_eigentum = ("eigentum" in sl) or ("eigentümer" in sl) or ("eigentuem" in sl)

    if has_whg and has_eigentum:
        return "Wohnung (Eigentum)"
    if has_whg and has_miete:
        return "Wohnung (Miete)"
    if has_haus and has_miete:
        return "Haus (Miete)"
    if has_haus and has_eigentum:
        return "Haus (Eigentum)"

    # fallback: nichts Passendes
    return None

def collect_q4_block(df: pd.DataFrame, q_col_name: str, extra_cols_after: int = 6) -> list[str]:
    """
    Liefert eine Liste von Spaltennamen, beginnend bei der Frage-Spalte und
    zusätzlich die nachfolgenden 'extra_cols_after' Spalten. Das deckt die
    typischen Options-Spalten (häufig 'Unnamed: ...') ab.
    """
    cols = list(df.columns)
    if q_col_name not in cols:
        return []
    i = cols.index(q_col_name)
    block = [q_col_name]
    for off in range(1, extra_cols_after + 1):
        if i + off < len(cols):
            block.append(cols[i + off])
    return block

def choose_from_block(row: pd.Series, cols: list[str]) -> Optional[str]:
    """
    Durchsucht die Spalten im Block in Reihenfolge und liefert die erste
    gültige Kanon-Kategorie.
    """
    for c in cols:
        if c not in row:
            continue
        norm = normalize_accommodation(row[c])
        if norm is not None:
            return norm
    return None

def preprocess(infile: Path, outfile: Path) -> None:
    print(f"[INFO] Repo-Root: {project_root()}")
    print(f"[INFO] Input CSV: {infile}")
    print(f"[INFO] Output:    {outfile}")

    df = read_raw_csv(infile)

    # Spalten ermitteln
    resp_col = find_col_by_names(
        df.columns,
        ["respondent_id", "Respondent ID", "respondent id"]
    )
    if not resp_col:
        raise KeyError("respondent_id-Spalte nicht gefunden.")

    q4_col = find_col_by_names(
        df.columns,
        ["In welcher Art von Unterkunft wohnen Sie?", "Unterkunft", "Accommodation", "Art von Unterkunft"]
    )
    if not q4_col:
        raise KeyError("Spalte 'In welcher Art von Unterkunft wohnen Sie?' nicht gefunden.")

    # Block der Q4-Spalten (Frage + folgende Options-Spalten) sammeln
    q4_block = collect_q4_block(df, q4_col, extra_cols_after=6)

    # Ergebnis-DataFrame aufbauen
    df_out = df[[resp_col]].copy()
    df_out.rename(columns={resp_col: "respondent_id"}, inplace=True)

    # Block normalisieren und erste nicht-NA je Zeile holen
    norm_block = df[q4_block].apply(lambda s: s.map(normalize_accommodation))
    first_non_na = norm_block.stack(dropna=True).groupby(level=0).first()
    df_out["accommodation_type"] = first_non_na.reindex(df.index)

    # Ausgabe (nullable string, damit fehlende Werte als <NA> erscheinen)
    outfile.parent.mkdir(parents=True, exist_ok=True)
    df_out["respondent_id"] = df_out["respondent_id"].astype("string")
    df_out["accommodation_type"] = df_out["accommodation_type"].astype("string")
    df_out.to_csv(outfile, index=False, encoding="utf-8")

    total = len(df_out)
    na_count = df_out["accommodation_type"].isna().sum()
    print(f"[OK] Geschrieben: {outfile}  (rows={total}, ohne Zuordnung={na_count})")

def main():
    root = project_root()
    default_in = root / "data/survey/raw/Energieverbrauch und Teilnahmebereitschaft an Demand-Response-Programmen in Haushalten.csv"
    default_out = root / "data/survey/processed/question_4_accommodation.csv"

    ap = argparse.ArgumentParser(description="Preprocess Survey Q4 (Accommodation)")
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
