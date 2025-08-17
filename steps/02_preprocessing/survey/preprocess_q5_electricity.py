#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Preprocess Survey Q5 (Electricity type):
- liest das Survey-CSV,
- findet 'respondent_id' und die Spalte
  "Welche Art von Strom beziehen Sie hauptsächlich?",
- mappt Antworten robust auf vier Kanon-Kategorien,
- schreibt data/survey/processed/question_5_electricity.csv.

Aufruf (Repo-Root):
  python3 processing/survey/jobs/preprocess_q5_electricity.py
Optional:
  python3 processing/survey/jobs/preprocess_q5_electricity.py \
    --infile "data/survey/raw/Energieverbrauch und Teilnahmebereitschaft an Demand-Response-Programmen in Haushalten.csv" \
    --outfile "data/survey/processed/question_5_electricity.csv"
"""

from __future__ import annotations
import argparse
from pathlib import Path
from typing import Optional
import sys
import re
import unicodedata
import pandas as pd


CANON_OEKOSTROM = "Ökostrom (aus erneuerbaren Energien wie Wasser, Sonne, Wind)"
CANON_KONV     = "Konventionellen Strom (Kernenergie und fossilen Brennstoffen)"
CANON_MIX      = "Eine Mischung aus konventionellem Strom und Ökostrom"
CANON_UNKNOWN  = "Weiss nicht"

CANON_SET = {CANON_OEKOSTROM, CANON_KONV, CANON_MIX, CANON_UNKNOWN}


def project_root() -> Path:
    try:
        return Path(__file__).resolve().parents[3]
    except NameError:
        return Path.cwd()


def read_raw_csv(path: Path) -> pd.DataFrame:
    # SurveyMonkey: zweite Kopfzeile (Options-/Response-Zeile) überspringen
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


def _normalize_text(s: str) -> str:
    # Akzente entfernen, ß->ss, whitespace normalisieren, lower
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.replace("ß", "ss")
    s = s.lower()
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_electricity(val: Optional[str]) -> Optional[str]:
    """Mappt freie/abweichende Antworten auf die vier Kanon-Kategorien."""
    if val is None or pd.isna(val):
        return None
    s = str(val).strip()
    if not s:
        return None
    if s in CANON_SET:
        return s

    n = _normalize_text(s)

    # Unknown / don't know
    if n in {"weiss nicht", "weis nicht", "weiß nicht", "weissnich", "weißnicht", "wn", "ka", "k. a.", "k.a.", "dont know", "don't know"}:
        return CANON_UNKNOWN

    # Ökostrom
    if ("oekostrom" in n) or ("ökostrom" in n) or ("erneuerbar" in n) or ("wasser" in n) or ("sonne" in n) or ("wind" in n):
        # Achtung: "Mischung" weiter unten prüfen – falls "mix" vorkommt, überschreibt MIX.
        eco_hit = True
    else:
        eco_hit = False

    # Konventionell
    konv_hit = ("konventionell" in n) or ("kernenergie" in n) or ("fossil" in n) or ("atom" in n)

    # Mischung
    mix_hit = ("misch" in n) or ("mix" in n)

    if mix_hit:
        return CANON_MIX
    if eco_hit and not konv_hit:
        return CANON_OEKOSTROM
    if konv_hit and not eco_hit:
        return CANON_KONV

    # Wenn sowohl eco_hit als auch konv_hit vorkommen, als Mix werten.
    if eco_hit and konv_hit:
        return CANON_MIX

    # keine sichere Zuordnung
    return None


def preprocess(infile: Path, outfile: Path) -> None:
    print(f"[INFO] Repo-Root: {project_root()}")
    print(f"[INFO] Input CSV: {infile}")
    print(f"[INFO] Output:    {outfile}")

    df = read_raw_csv(infile)

    # Spalten ermitteln
    resp_col = find_col_by_names(df.columns, ["respondent_id", "Respondent ID", "respondent id"])
    if not resp_col:
        raise KeyError("respondent_id-Spalte nicht gefunden.")

    q_col = find_col_by_names(
        df.columns,
        ["Welche Art von Strom beziehen Sie hauptsächlich?", "Strom beziehen", "Electricity type"]
    )
    if not q_col:
        raise KeyError("Spalte 'Welche Art von Strom beziehen Sie hauptsächlich?' nicht gefunden.")

    # Mapping anwenden
    df_out = df[[resp_col]].copy()
    df_out.rename(columns={resp_col: "respondent_id"}, inplace=True)
    df_out["electricity_type"] = df[q_col].map(normalize_electricity)

    # Ausgabe (nullable string, damit None als <NA> erscheint)
    outfile.parent.mkdir(parents=True, exist_ok=True)
    df_out["respondent_id"] = df_out["respondent_id"].astype("string")
    df_out["electricity_type"] = df_out["electricity_type"].astype("string")
    df_out.to_csv(outfile, index=False, encoding="utf-8")

    total = len(df_out)
    na_count = df_out["electricity_type"].isna().sum()
    print(f"[OK] Geschrieben: {outfile}  (rows={total}, ohne Zuordnung={na_count})")


def main():
    root = project_root()
    default_in = root / "data/survey/raw/Energieverbrauch und Teilnahmebereitschaft an Demand-Response-Programmen in Haushalten.csv"
    default_out = root / "data/survey/processed/question_5_electricity.csv"

    ap = argparse.ArgumentParser(description="Preprocess Survey Q5 (Electricity type)")
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