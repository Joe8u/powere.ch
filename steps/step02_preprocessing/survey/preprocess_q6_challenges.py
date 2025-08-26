#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Preprocess Survey Q6 (Freitext zu Herausforderungen):
- liest das Survey-CSV,
- findet 'respondent_id' und die Spalte mit der Q6-Freitextfrage
  (robust per exaktem Titel oder fuzzy 'Herausforderungen'),
- säubert den Text leicht (Trim, leere Platzhalter -> NA, 'wn' -> 'Weiss nicht'),
- schreibt data/survey/processed/question_6_challenges.csv.
"""

from __future__ import annotations
import argparse
from pathlib import Path
from typing import Optional
import sys
import re
import pandas as pd


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


def find_col_by_names(columns, candidates) -> Optional[str]:
    # 1) exakte Treffer
    for c in candidates:
        if c in columns:
            return c
    # 2) tolerante Normalisierung (Lower, Leerzeichen/„?“/„*“ raus)
    norm = {str(col).lower().replace(" ", "").replace("?", "").replace("*", ""): col for col in columns}
    for c in candidates:
        key = c.lower().replace(" ", "").replace("?", "").replace("*", "")
        if key in norm:
            return norm[key]
    return None


def find_col_contains(columns, token: str) -> Optional[str]:
    """Suche Spalte, deren Name (case-insensitive) das Token enthält."""
    token_l = token.lower()
    for col in columns:
        if token_l in str(col).lower():
            return col
    return None


EMPTY_PAT = re.compile(r"^\s*(nan|null|none|-+|—|–)?\s*$", re.IGNORECASE)


def clean_freetext(val: Optional[str]) -> Optional[str]:
    """Leichte Säuberung: Trim, leere/NA-ähnliche Platzhalter -> None, 'wn' normalisieren."""
    if val is None or pd.isna(val):
        return None
    s = str(val).strip()
    if not s or EMPTY_PAT.match(s):
        return None
    # 'wn' (weiss nicht) und Varianten vereinheitlichen (bewusst minimal-invasiv)
    s_l = s.lower().strip()
    if s_l in {"wn", "weiss nicht", "weiß nicht", "weis nicht", "k.a.", "k. a.", "ka"}:
        return "Weiss nicht"
    return s


def preprocess(infile: Path, outfile: Path) -> None:
    print(f"[INFO] Repo-Root: {project_root()}")
    print(f"[INFO] Input CSV: {infile}")
    print(f"[INFO] Output:    {outfile}")

    df = read_raw_csv(infile)

    # respondent_id ermitteln
    resp_col = find_col_by_names(df.columns, ["respondent_id", "Respondent ID", "respondent id"])
    if not resp_col:
        raise KeyError("respondent_id-Spalte nicht gefunden.")

    # Q6-Spalte ermitteln: erst exakte Kandidaten, danach fuzzy auf 'Herausforderungen'
    q6_candidates = [
        "Denken Sie, dass die zunehmende Erzeugung erneuerbarer Energien Herausforderungen für das Stromsystem mit sich bringt? Wenn ja, welche?Falls Sie es nicht wissen, können Sie gerne ‚wn‘ (weiss nicht) schreiben.",
        "Denken Sie, dass die zunehmende Erzeugung erneuerbarer Energien Herausforderungen für das Stromsystem mit sich bringt? Wenn ja, welche?",
        "Welche Herausforderungen",
    ]
    q6_col = find_col_by_names(df.columns, q6_candidates)
    if not q6_col:
        q6_col = find_col_contains(df.columns, "Herausforderungen")
    if not q6_col:
        raise KeyError("Q6-Spalte (Freitext 'Herausforderungen') nicht gefunden.")

    # Output aufbauen
    df_out = df[[resp_col]].copy()
    df_out.rename(columns={resp_col: "respondent_id"}, inplace=True)
    df_out["challenge_text"] = df[q6_col].map(clean_freetext).astype("string")

    # Datei schreiben
    outfile.parent.mkdir(parents=True, exist_ok=True)
    df_out["respondent_id"] = df_out["respondent_id"].astype("string")
    df_out.to_csv(outfile, index=False, encoding="utf-8")

    total = len(df_out)
    na_count = df_out["challenge_text"].isna().sum()
    print(f"[OK] Geschrieben: {outfile}  (rows={total}, ohne Freitext={na_count})")


def main():
    root = project_root()
    default_in = root / "data/survey/raw/Energieverbrauch und Teilnahmebereitschaft an Demand-Response-Programmen in Haushalten.csv"
    default_out = root / "data/survey/processed/question_6_challenges.csv"

    ap = argparse.ArgumentParser(description="Preprocess Survey Q6 (Freitext-Herausforderungen)")
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
