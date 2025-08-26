# steps/step02_preprocessing/market/regelenergie/preprocess_tertiary_regulation.py
"""
Aggregiert mFRR-Aktivierungen aus monatlichen Dateien (z. B.:
data/market/raw/regelenergie/mfrR/2024/2024-01-TRE-Ergebnis.csv)

- Filtert nur tatsächlich abgerufene Mengen (called_mw > 0).
- Berechnet je 15-Minuten-Intervall die Gesamtmenge und den
  mengen-gewichteten Durchschnittspreis.

Schreibt je Monat:
  data/market/processed/regelenergie/YYYY-MM.csv
und spiegelt nach:
  steps/step03_processed_data/market/regelenergie/YYYY-MM.csv

Spalten:
  timestamp, total_called_mw, avg_price_eur_mwh

Aufruf:
  python -m steps.step02_preprocessing.market.regelenergie.preprocess_tertiary_regulation --year 2024
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Optional

import pandas as pd
from shutil import copy2


# ----------------------------- Pfade -----------------------------

def _project_root_from_file() -> Path:
    """Finde das Repo-Root relativ zu dieser Datei (…/steps/...)."""
    here = Path(__file__).resolve()
    for p in here.parents:
        if p.name == "steps":
            return p.parent
    return here.parents[4] if len(here.parents) >= 5 else Path.cwd()


PROJECT_ROOT = _project_root_from_file()

# raw/… und processed/… unter data/market/
RAW_BASE    = PROJECT_ROOT / "data" / "market" / "raw" / "regelenergie" / "mfrR"
PROC_BASE   = PROJECT_ROOT / "data" / "market" / "processed" / "regelenergie"
MIRROR_BASE = PROJECT_ROOT / "steps" / "step03_processed_data" / "market" / "regelenergie"
PROC_BASE.mkdir(parents=True, exist_ok=True)
MIRROR_BASE.mkdir(parents=True, exist_ok=True)


# ----------------------- Einlesen & Normalisieren -----------------------

_AUSSCHREIBUNG_RE = re.compile(r"TRE[_-](\d{2})[_-](\d{2})[_-](\d{2})")  # TRE_24_01_05 → 2024-01-05


def _read_month(path: Path) -> pd.DataFrame:
    """Liest eine Monats-CSV robust ein und gibt ein normalisiertes DataFrame zurück."""
    if not path.exists():
        raise FileNotFoundError(path)

    # Encoding-Probleme (Umlaute): cp1252/latin-1 versuchen, dann utf-8, dann Default
    df_opt: Optional[pd.DataFrame] = None
    for enc in ("cp1252", "latin-1", "utf-8"):
        try:
            df_opt = pd.read_csv(path, sep=";", dtype=str, encoding=enc)
            break
        except Exception:
            continue
    if df_opt is None:
        df_opt = pd.read_csv(path, sep=";", dtype=str)

    # Ab hier sicher DataFrame
    df = df_opt.copy()
    df.columns = [str(c).strip() for c in df.columns]

    # Erwartete Kernspalten prüfen (die "Einheit"-Spalten können doppelt vorkommen)
    needed = ["Ausschreibung", "Von", "Bis", "Produkt",
              "Angebotene Menge", "Abgerufene Menge", "Preis", "Status"]
    missing = [c for c in needed if c not in df.columns]
    if missing:
        # Tolerante Suche, falls Exporte leicht andere Spaltenbezeichner haben
        def _find_col_like(pat: str) -> Optional[str]:
            for c in df.columns:
                if re.fullmatch(pat, c, flags=re.I):
                    return c
            return None

        alt_map: dict[str, Optional[str]] = {
            "Ausschreibung":      _find_col_like(r"Ausschreibung"),
            "Von":                _find_col_like(r"Von"),
            "Bis":                _find_col_like(r"Bis"),
            "Produkt":            _find_col_like(r"Produkt"),
            "Angebotene Menge":   _find_col_like(r"Angebotene\s+Menge"),
            "Abgerufene Menge":   _find_col_like(r"Abgerufene\s+Menge"),
            "Preis":              _find_col_like(r"Preis"),
            "Status":             _find_col_like(r"Status"),
        }
        rename_map: dict[str, str] = {v: k for k, v in alt_map.items()
                                      if v is not None and v != k}
        if rename_map:
            df = df.rename(columns=rename_map)

    # Einheiten-Spalten neben Menge/Preis ermitteln (stehen direkt rechts daneben)
    cols = list(df.columns)

    def _right_of(colname: str, cols_list: list[str]) -> Optional[str]:
        if colname not in cols_list:
            return None
        i = cols_list.index(colname)
        return cols_list[i + 1] if i + 1 < len(cols_list) else None

    offered_unit_col = _right_of("Angebotene Menge", cols)
    called_unit_col  = _right_of("Abgerufene Menge", cols)
    price_unit_col   = _right_of("Preis", cols)

    rename_cols: dict[str, str] = {
        "Ausschreibung":      "tender_id",
        "Von":                "time_from",
        "Bis":                "time_to",
        "Produkt":            "product",
        "Angebotene Menge":   "offered_qty",
        "Abgerufene Menge":   "called_qty",
        "Preis":              "price_eur_mwh",
        "Status":             "status",
    }
    if offered_unit_col: rename_cols[offered_unit_col] = "offered_unit"
    if called_unit_col:  rename_cols[called_unit_col]  = "called_unit"
    if price_unit_col:   rename_cols[price_unit_col]   = "price_unit"

    df = df.rename(columns=rename_cols)

    # Nur relevante Spalten behalten (falls vorhanden)
    keep: list[str] = [
        "tender_id", "time_from", "time_to", "product",
        "offered_qty", "offered_unit",
        "called_qty", "called_unit",
        "price_eur_mwh", "price_unit", "status",
    ]
    keep = [c for c in keep if c in df.columns]
    df = df[keep].copy()

    # Strings trimmen
    for c in df.columns:
        if pd.api.types.is_string_dtype(df[c]) or df[c].dtype == object:
            df[c] = df[c].astype(str).str.strip()

    # Mengen & Preis numerisch (Kommas tolerieren)
    def _to_float(s: pd.Series) -> pd.Series:
        return pd.to_numeric(
            s.astype(str)
             .str.replace(",", ".", regex=False)
             .str.replace(r"[^\d.\-]", "", regex=True),
            errors="coerce",
        ).astype("Float64")

    df["offered_mw"]    = _to_float(df["offered_qty"])    if "offered_qty"    in df.columns else pd.Series([pd.NA]*len(df), dtype="Float64")
    df["called_mw"]     = _to_float(df["called_qty"])     if "called_qty"     in df.columns else pd.Series([pd.NA]*len(df), dtype="Float64")
    df["price_eur_mwh"] = _to_float(df["price_eur_mwh"])  if "price_eur_mwh"  in df.columns else pd.Series([pd.NA]*len(df), dtype="Float64")

    # Datum aus tender_id ableiten: TRE_YY_MM_DD
    def _date_from_tender(tender: str) -> Optional[pd.Timestamp]:
        if not isinstance(tender, str):
            return None
        m = _AUSSCHREIBUNG_RE.search(tender)
        if not m:
            return None
        yy, mm, dd = m.groups()
        year = 2000 + int(yy)
        return pd.Timestamp(year=year, month=int(mm), day=int(dd))

    df["date"] = df["tender_id"].map(_date_from_tender)

    # Zeit kombinieren → timestamp (Beginn des 15-Min-Intervalls)
    def _combine(dt: Optional[pd.Timestamp], hhmm: Optional[str]) -> Optional[pd.Timestamp]:
        if pd.isna(dt) or not isinstance(hhmm, str) or ":" not in hhmm:
            return None
        h, m = hhmm.split(":", 1)
        try:
            return pd.Timestamp(year=dt.year, month=dt.month, day=dt.day, hour=int(h), minute=int(m))
        except Exception:
            return None

    time_from_series = df["time_from"] if "time_from" in df.columns else pd.Series([None] * len(df))
    df["timestamp"] = [_combine(d, t) for d, t in zip(df["date"], time_from_series)]

    # Nur aktivierte Mengen mit gültigem Preis und Timestamp
    df = df[
        (df["called_mw"].fillna(0) > 0)
        & df["price_eur_mwh"].notna()
        & (df["price_eur_mwh"] >= 0)
        & df["timestamp"].notna()
    ].copy()

    return df


def _aggregate_quarter_hour(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregiert je timestamp total_called_mw und mengen-gewichteten Durchschnittspreis."""
    if df.empty:
        return pd.DataFrame(columns=["timestamp", "total_called_mw", "avg_price_eur_mwh"])

    df = df.copy()
    df["_pxq"] = df["price_eur_mwh"] * df["called_mw"]

    agg_qty = (
        df.groupby("timestamp")["called_mw"]
          .sum()
          .rename("total_called_mw")
          .reset_index()
    )
    pxq = (
        df.groupby("timestamp")["_pxq"]
          .sum()
          .rename("sum_pxq")
          .reset_index()
    )

    merged = agg_qty.merge(pxq, on="timestamp", how="left")
    merged["avg_price_eur_mwh"] = merged["sum_pxq"] / merged["total_called_mw"]
    merged = merged[["timestamp", "total_called_mw", "avg_price_eur_mwh"]].sort_values("timestamp")
    return merged


# ----------------------------- Pipeline -----------------------------

def process_year(year: int) -> None:
    raw_dir = RAW_BASE / str(year)
    if not raw_dir.exists():
        raise FileNotFoundError(f"Rohdaten-Verzeichnis fehlt: {raw_dir}")

    print(f"[INFO] Verarbeite Jahr {year} aus {raw_dir}")
    all_events: list[pd.DataFrame] = []

    # Dateien wie 2024-01-TRE-Ergebnis.csv
    files = sorted(raw_dir.glob(f"{year}-[0-1][0-9]-TRE-Ergebnis.csv"))
    if not files:
        print(f"[WARN] Keine Dateien gefunden unter {raw_dir}")
        return

    for csv_path in files:
        month = csv_path.stem.split("-")[1]
        print(f"  • Lese {csv_path.name} …")
        month_df = _read_month(csv_path)

        if month_df.empty:
            print(f"    └─ keine aktivierten Events in {csv_path.name}")
            continue

        # Aggregation pro 15 Min
        qh = _aggregate_quarter_hour(month_df)
        out_path = PROC_BASE / f"{year}-{month}.csv"
        qh.to_csv(out_path, index=False)
        print(f"    └─ gespeichert: {out_path} (rows={len(qh)})")

        # Spiegeln nach steps/step03_processed_data
        mirror_path = MIRROR_BASE / f"{year}-{month}.csv"
        copy2(out_path, mirror_path)
        print(f"    └─ gespiegelt:  {mirror_path}")

        all_events.append(month_df[["timestamp", "called_mw", "price_eur_mwh"]])

    # Optional: Überblick für das Jahr
    if all_events:
        yr = pd.concat(all_events, ignore_index=True)
        print("\n[INFO] Jahresüberblick (nur aktivierte):")
        print("  Zeilen:", len(yr))
        print("  Zeitraum:", yr["timestamp"].min(), "→", yr["timestamp"].max())
        print("  Max. Preis (EUR/MWh):", float(yr["price_eur_mwh"].max()))
    else:
        print("[INFO] Keine aktivierten Events im Jahr gefunden.")


# ----------------------------- CLI -----------------------------

def main():
    ap = argparse.ArgumentParser(description="Preprocess mFRR (tertiary regulation) monthly CSVs.")
    ap.add_argument(
        "--year",
        type=int,
        default=pd.Timestamp.today().year,
        help="Jahr der Rohdaten (Ordnername unter data/market/raw/regelenergie/mfrR/)",
    )
    args = ap.parse_args()
    process_year(args.year)


if __name__ == "__main__":
    main()
