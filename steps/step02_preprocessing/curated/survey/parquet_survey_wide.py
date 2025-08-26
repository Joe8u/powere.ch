#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Baut ein "wide" Survey-Parquet aus allen CSVs in data/survey/processed
und schreibt nach:
  data/curated/survey/wide/data.parquet

- Robuste ID-Spaltenerkennung (respondent_id, response_id, id, …)
- Toleranter CSV-Import (utf-8, cp1252, latin-1)
- Typstabile Konvertierungen (pandas.to_numeric(errors='coerce'))

Aufruf:
  python steps/step02_preprocessing/curated/survey/parquet_survey_wide.py
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional, List, Tuple

import pandas as pd


# ----------------------------- Pfade & Utils -----------------------------

def find_repo_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / ".git").exists() or ((p / "apps").is_dir() and (p / "data").is_dir()):
            return p
    return start.parents[3] if len(start.parents) >= 3 else start


def sanitize_col(name: str) -> str:
    s = str(name).strip()
    s = s.replace("\u00a0", " ")  # non-breaking space
    s = s.replace("ß", "ss")
    s = s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
    s = s.replace("Ä", "Ae").replace("Ö", "Oe").replace("Ü", "Ue")
    s = s.lower()
    s = s.replace(" ", "_").replace("-", "_").replace("/", "_").replace("__", "_")
    return s


ID_CANDIDATES = {
    "respondent_id", "respondentid", "respondent",
    "response_id", "responseid",
    "id",
    "collector_id", "collectorid",
    "email", "email_address",
}


def detect_id_column(df: pd.DataFrame) -> Optional[str]:
    cols: List[str] = [sanitize_col(c) for c in list(df.columns)]
    orig = dict(zip(cols, list(df.columns)))

    # harte Kandidaten zuerst
    for c in cols:
        if c in ID_CANDIDATES:
            return orig[c]

    # heuristik: *_id oder enthält "respondent" + "id"
    for c in cols:
        if c.endswith("_id"):
            return orig[c]
    for c in cols:
        if ("respondent" in c and "id" in c) or c == "id":
            return orig[c]
    return None


def read_processed_csv(path: Path) -> pd.DataFrame:
    """CSV robust lesen, Spalten normalisieren; garantiert ein DataFrame zurück."""
    if not path.exists():
        raise FileNotFoundError(path)

    df_opt: Optional[pd.DataFrame] = None
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            df_opt = pd.read_csv(path, dtype=str, encoding=enc)
            break
        except Exception:
            continue

    if df_opt is None:
        # letzter Versuch ohne Encoding-Angabe
        df_opt = pd.read_csv(path, dtype=str)

    # ab hier garantiert vorhanden
    df: pd.DataFrame = df_opt
    # Spalten-Namen normalisieren (kopie)
    new_cols = [sanitize_col(c) for c in list(df.columns)]
    df.columns = new_cols
    return df


def add_file_prefix(df: pd.DataFrame, prefix: str, id_col: str) -> pd.DataFrame:
    """Alle Nicht-ID-Spalten mit prefix__ versehen, um Kollisionen zu vermeiden."""
    out = df.copy()
    renamed = {}
    for c in list(out.columns):
        if c == id_col:
            continue
        renamed[c] = f"{prefix}__{c}"
    if renamed:
        out = out.rename(columns=renamed)
    return out


def parse_numeric_columns(df: pd.DataFrame, col_substrings: Tuple[str, ...] = ("percent", "pct", "preis", "rabatt")) -> pd.DataFrame:
    """Konvertiert ausgewählte Spalten numerisch (coerce), toleriert Kommas, % etc."""
    out = df.copy()

    # Kandidaten heuristisch auswählen:
    cand_cols: List[str] = []
    for c in list(out.columns):
        cs = c.lower()
        if any(sub in cs for sub in col_substrings):
            cand_cols.append(c)

    if cand_cols:
        for c in cand_cols:
            s = (
                out[c]
                .astype(str)
                .str.replace(",", ".", regex=False)
                .str.replace(r"[^\d.\-]", "", regex=True)
            )
            out[c] = pd.to_numeric(s, errors="coerce")  # <- typstabil
    return out


# ----------------------------- Zusammenbauen -----------------------------

def build_wide(in_dir: Path) -> pd.DataFrame:
    if not in_dir.exists():
        raise FileNotFoundError(f"Eingabeverzeichnis fehlt: {in_dir}")

    parts: List[pd.DataFrame] = []

    # Alle CSVs (eine Ebene) – bei dir liegen die Files als question_*.csv
    for csv_path in sorted(in_dir.glob("*.csv")):
        print(f"  • Lese {csv_path.name}")
        try:
            df = read_processed_csv(csv_path)
        except Exception as e:
            print(f"    └─ [WARN] Konnte nicht lesen: {e}")
            continue

        id_col = detect_id_column(df)
        if id_col is None:
            print("    └─ [WARN] Keine ID-Spalte erkannt -> überspringe Datei")
            continue

        prefix = sanitize_col(csv_path.stem)  # z.B. question_10_incentive_wide
        df = add_file_prefix(df, prefix, id_col=id_col)

        # auf Duplikate prüfen & ggf. deduplizieren
        if df.duplicated(subset=[id_col]).any():
            df = df.drop_duplicates(subset=[id_col], keep="first")

        parts.append(df[[id_col] + [c for c in list(df.columns) if c != id_col]])

    if not parts:
        raise RuntimeError("Kein DataFrame erstellt (alle Dateien übersprungen?)")

    # progressives Outer-Join auf ID
    wide = parts[0]
    id_col = detect_id_column(wide)
    if id_col is None:
        raise RuntimeError("Unerwartet: ID-Spalte im ersten Teil nicht gefunden.")

    for i in range(1, len(parts)):
        right = parts[i]
        right_id = detect_id_column(right)
        if right_id is None:
            print("    └─ [WARN] Teil ohne ID beim Join – übersprungen.")
            continue
        wide = wide.merge(right, left_on=id_col, right_on=right_id, how="outer")
        if right_id != id_col:
            wide = wide.drop(columns=[right_id])

    # Optionale numerische Normalisierung
    wide = parse_numeric_columns(wide)

    # sortierte Spalten: ID zuerst
    cols = list(wide.columns)
    cols = [c for c in cols if c != id_col]
    cols_sorted = [id_col] + sorted(cols)
    wide = wide[cols_sorted]

    return wide


def write_parquet(df: pd.DataFrame, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Arrow/Parquet (Snappy)
    df.to_parquet(out_path, index=False, engine="pyarrow", compression="snappy")
    return out_path


# ----------------------------- CLI -----------------------------

def main() -> int:
    here = Path(__file__).resolve()
    repo = find_repo_root(here.parent)
    in_dir = repo / "data" / "survey" / "processed"
    out_path = repo / "data" / "curated" / "survey" / "wide" / "data.parquet"

    print(f"[INFO] Repo root : {repo}")
    print(f"[INFO] Input dir : {in_dir}")
    print(f"[INFO] Output    : {out_path}")

    wide = build_wide(in_dir)
    outp = write_parquet(wide, out_path)
    print(f"[INFO] Wrote {outp} (rows={len(wide)}, cols={len(wide.columns)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
