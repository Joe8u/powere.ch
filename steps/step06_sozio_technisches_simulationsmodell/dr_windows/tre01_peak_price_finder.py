# steps/step06_sozio_technisches_simulationsmodell/dr_windows/tre01_peak_price_finder.py
"""
Findet die N teuersten Perioden der tertiären Regelenergie (TRE, mFRR-Arbeitspreis)
und (optional) speichert sie unter:
  data/market/processed/dr_windows/tre_top_periods_<YEAR>[ _fx<FX> ].csv
"""

from __future__ import annotations
from pathlib import Path
import argparse
import datetime as dt
import numpy as np
import pandas as pd

# Loader für die vorprozessierten TRE-Daten (mFRR)
from steps.step04_dataloaders.dataloaders.market.tertiary_regulation_loader import (
    list_regulation_months,
    load_regulation_range,
)

# ---------------------------------------------------------------------
# Pfade
# ---------------------------------------------------------------------
def _project_root_from_file() -> Path:
    here = Path(__file__).resolve()
    for p in here.parents:
        if p.name == "steps":
            return p.parent
    return here.parents[4] if len(here.parents) >= 5 else Path.cwd()

PROJECT_ROOT = _project_root_from_file()
OUT_DIR = PROJECT_ROOT / "data" / "market" / "processed" / "dr_windows"
OUT_DIR.mkdir(parents=True, exist_ok=True)

def _fname_top_periods(year: int, fx: float | None) -> str:
    if fx is not None and abs((fx or 1.0) - 1.0) > 1e-9:
        return f"tre_top_periods_{year}_fx{fx:.2f}.csv"
    return f"tre_top_periods_{year}.csv"

def _latest_available_year() -> int | None:
    base = PROJECT_ROOT / "data" / "market" / "processed" / "regelenergie"
    years: list[int] = []
    if base.exists():
        for p in base.glob("[0-9][0-9][0-9][0-9]-[0-1][0-9].csv"):
            try:
                years.append(int(p.stem.split("-")[0]))
            except Exception:
                pass
    return max(years) if years else None

# ---------------------------------------------------------------------
# Kernlogik
# ---------------------------------------------------------------------
def convert_mwh_to_kwh_price_eur(price_eur_mwh: float | int | None) -> float:
    if price_eur_mwh is None or (isinstance(price_eur_mwh, float) and np.isnan(price_eur_mwh)):
        return np.nan
    return float(price_eur_mwh) / 1000.0

def find_top_tre_price_periods(year: int, n_top: int, fx: float | None = 1.0) -> pd.DataFrame | None:
    print(f"[INFO] Lade TRE-Arbeitspreise {year} …")
    start = dt.datetime(year, 1, 1)
    end   = dt.datetime(year, 12, 31, 23, 59, 59)

    df = load_regulation_range(start=start, end=end)  # Index=timestamp, cols: total_called_mw, avg_price_eur_mwh
    if df is None or df.empty:
        print("[FEHLER] Keine Daten geladen.")
        return None
    if "avg_price_eur_mwh" not in df.columns:
        print("[FEHLER] Spalte 'avg_price_eur_mwh' nicht vorhanden.")
        return None

    df = df.copy()
    df["price_eur_mwh_original"] = df["avg_price_eur_mwh"]

    # FX robust behandeln (None => 1.0)
    fx_rate = 1.0 if fx is None else float(fx)

    # EUR/MWh -> CHF/kWh (EUR≈CHF, optional FX)
    df["price_chf_kwh"] = (
        df["price_eur_mwh_original"].apply(convert_mwh_to_kwh_price_eur) * fx_rate
    )

    top = df.nlargest(int(n_top), "price_chf_kwh").copy()
    if top.empty:
        print("[FEHLER] Keine Spitzenperioden gefunden.")
        return None

    # Zusatzspalten
    top["weekday"] = top.index.day_name()
    top["hour"] = top.index.hour

    # Ausgabe (Auszug)
    print(f"\n[INFO] Top {n_top} TRE-Perioden {year} (Auszug):")
    cols_show = ["price_chf_kwh", "price_eur_mwh_original", "weekday", "hour"]
    print(top[cols_show].head(10).to_string())

    avg_chf_kwh = top["price_chf_kwh"].mean()
    avg_eur_mwh = top["price_eur_mwh_original"].mean()
    print(f"\n[INFO] Ø Preis der Top-Perioden: {avg_chf_kwh:.6f} CHF/kWh | {avg_eur_mwh:.2f} EUR/MWh")

    return top

# ---------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Finde die N teuersten TRE-Perioden eines Jahres.")
    parser.add_argument("--year", type=int, default=None,
                        help="Jahr (Default: jüngstes Jahr mit vorprozessierten Regelenergie-Dateien, sonst aktuelles Jahr)")
    parser.add_argument("--top", type=int, default=24, help="Anzahl der Top-Perioden")
    parser.add_argument("--fx", type=float, default=1.0, help="EUR→CHF Umrechnungsfaktor (Standard 1.0)")
    parser.add_argument("--save", action="store_true", help="Ergebnis als CSV in data/market/processed/dr_windows speichern")
    args = parser.parse_args()

    year = args.year
    if year is None:
        latest = _latest_available_year()
        year = latest if latest is not None else pd.Timestamp.today().year

    # kleines Guardrail: wenn es keine Monatsdateien gibt, warnen
    months = list_regulation_months(year)
    if not months:
        print(f"[WARN] Keine Monatsdateien in data/market/processed/regelenergie für {year} gefunden.")
    top = find_top_tre_price_periods(year, n_top=args.top, fx=args.fx)
    if top is None or top.empty:
        print("[INFO] Keine Top-Perioden gefunden oder Verarbeitung fehlgeschlagen.")
        return

    if args.save:
        fname = _fname_top_periods(year, args.fx)
        out_path = OUT_DIR / fname
        top.reset_index().to_csv(out_path, index=False)
        print(f"[INFO] CSV gespeichert: {out_path}")

if __name__ == "__main__":
    main()