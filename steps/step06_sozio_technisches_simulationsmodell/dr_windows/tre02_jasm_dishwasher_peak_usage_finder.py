# steps/step06_sozio_technisches_simulationsmodell/dr_windows/tre02_jasm_dishwasher_peak_usage_finder.py
"""
Lädt JASM-Lastprofile für die Tage der teuersten TRE-Perioden (mFRR-Arbeitspreis).

- Holt die Top-N-Perioden aus data/market/processed/dr_windows/tre_top_periods_YYYY[_fxXX].csv
  (erzeugt von tre01_peak_price_finder). Falls nicht vorhanden, werden sie on-the-fly
  aus den mFRR-Processed-Daten berechnet.
- Lädt für ein gewähltes Gerät (Default: 'Geschirrspüler') die aggregierten JASM-Lasten
  exakt an diesen Tagen.

CLI:
  python -m steps.step06_sozio_technisches_simulationsmodell.dr_windows.tre02_jasm_dishwasher_peak_usage_finder \
    --year 2024 --appliance "Geschirrspüler" --top 24 [--fx 0.97] [--save]

Speicherziel (bei --save):
  data/market/processed/dr_windows/tre_jasm_{appliance_slug}_{year}_top{N}[ _fx{FX} ].csv
"""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd


# ----------------------- Pfade und Helpers -----------------------

def _project_root_from_file() -> Path:
    here = Path(__file__).resolve()
    for p in here.parents:
        if p.name == "steps":
            return p.parent
    return here.parents[4] if len(here.parents) >= 5 else Path.cwd()

PROJECT_ROOT = _project_root_from_file()

OUT_DIR = PROJECT_ROOT / "data" / "market" / "processed" / "dr_windows"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def _slug(s: str) -> str:
    repl = (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss"))
    s2 = s.lower()
    for a, b in repl:
        s2 = s2.replace(a, b)
    return "".join(ch if ch.isalnum() else "_" for ch in s2).strip("_")


def _fname_out(year: int, appliance: str, top: int, fx: Optional[float]) -> Path:
    slug = _slug(appliance)
    if fx is not None and abs(fx - 1.0) > 1e-9:
        return OUT_DIR / f"tre_jasm_{slug}_{year}_top{top}_fx{fx:.2f}.csv"
    return OUT_DIR / f"tre_jasm_{slug}_{year}_top{top}.csv"


# ----------------------- Loader-Imports (robust) -----------------------

# Top-Fenster (aus tre01) laden
from steps.step04_dataloaders.dataloaders.market.dr_windows_loader import (
    load_tre_top_periods,
    list_tre_windows_files,
)

# mFRR-Jahresbereich (Fallback, falls tre01-CSV fehlt)
from steps.step04_dataloaders.dataloaders.market.tertiary_regulation_loader import (
    load_regulation_range,
)

# JASM-Lastprofile (Aggregationen)
try:
    from steps.step04_dataloaders.dataloaders.lastprofile import load_appliances as load_jasm_profiles
except Exception:
    # alternativer Modulname (falls im Projekt anders benannt)
    from steps.step04_dataloaders.dataloaders.jasm import load_appliances as load_jasm_profiles  # type: ignore


# ----------------------- Kernlogik -----------------------

def _compute_top_periods_fallback(year: int, n_top: int, fx: Optional[float]) -> pd.DataFrame:
    """
    Falls keine tre01-CSV vorhanden ist: berechne Top-N Perioden aus mFRR processed.
    """
    print("[INFO] Fallback: berechne Top-Perioden direkt aus mFRR-Daten …")
    start = dt.datetime(year, 1, 1, 0, 0, 0)
    end   = dt.datetime(year, 12, 31, 23, 45, 0)  # letzter 15-min Slot
    df = load_regulation_range(start=start, end=end)  # Index=timestamp
    if df.empty or "avg_price_eur_mwh" not in df.columns:
        raise RuntimeError("mFRR-Daten leer oder Spalte 'avg_price_eur_mwh' fehlt.")

    fx_rate = 1.0 if fx is None else float(fx)
    df = df.copy()
    df["price_eur_mwh_original"] = df["avg_price_eur_mwh"]
    df["price_chf_kwh"] = df["price_eur_mwh_original"].astype(float) * fx_rate / 1000.0

    top = df.nlargest(n_top, "price_chf_kwh")
    # Zusatzspalten
    top["weekday"] = top.index.day_name()
    top["hour"] = top.index.hour
    return top[["total_called_mw", "avg_price_eur_mwh", "price_eur_mwh_original", "price_chf_kwh", "weekday", "hour"]]


def _load_top_periods(year: int, n_top: int, fx: Optional[float]) -> pd.DataFrame:
    """
    Versuche CSV (tre01) zu laden, sonst Fallback-Berechnung.
    """
    try:
        df = load_tre_top_periods(year, fx=fx)
        if len(df) > n_top:
            df = df.nlargest(n_top, "price_chf_kwh")
        return df
    except FileNotFoundError:
        files = [p.name for p in list_tre_windows_files(year)]
        print(f"[WARN] Keine tre01-CSV gefunden. Verfügbare Dateien: {files}")
        return _compute_top_periods_fallback(year, n_top, fx)


def _extract_unique_dates(index: pd.DatetimeIndex) -> List[dt.date]:
    return sorted({ts.date() for ts in index})


def get_jasm_load_for_specific_dates(
    year: int,
    appliance: str,
    dates: List[dt.date],
) -> pd.DataFrame:
    """
    Lädt aggregierte JASM-Lasten für 'appliance' exakt an den übergebenen 'dates'.
    """
    if not dates:
        return pd.DataFrame(columns=[appliance])

    start_dt = dt.datetime.combine(min(dates), dt.time.min)
    end_dt   = dt.datetime.combine(max(dates), dt.time.max)

    df = load_jasm_profiles(
        appliances=[appliance],
        start=start_dt,
        end=end_dt,
        year=year,
        group=True,
    )
    if df is None or df.empty or appliance not in df.columns:
        raise RuntimeError(f"Keine JASM-Daten für '{appliance}' im Bereich {start_dt}–{end_dt}.")

    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)

    mask = df.index.normalize().isin({pd.Timestamp(d) for d in dates})
    out = df.loc[mask, [appliance]].copy()
    return out


def run(year: int, appliance: str, n_top: int, fx: Optional[float], save: bool) -> pd.DataFrame:
    print(f"[INFO] Lade Top-{n_top} TRE-Perioden {year} …")
    top = _load_top_periods(year, n_top, fx)
    if top.empty:
        raise RuntimeError("Top-Perioden leer.")

    dates = _extract_unique_dates(top.index)
    print(f"[INFO] Relevante Tage: {len(dates)} → {dates[:5]}{' …' if len(dates) > 5 else ''}")

    print(f"[INFO] Lade JASM-Last für '{appliance}' an diesen Tagen …")
    jasm = get_jasm_load_for_specific_dates(year, appliance, dates)
    print(f"[INFO] JASM-Teilmatrix: {jasm.shape[0]} Zeilen, Zeitraum {jasm.index.min()} → {jasm.index.max()}")

    if save:
        out_path = _fname_out(year, appliance, n_top, fx)
        jasm.reset_index().to_csv(out_path, index=False)
        print(f"[INFO] CSV gespeichert: {out_path}")

    return jasm


# ----------------------- CLI -----------------------

def main():
    ap = argparse.ArgumentParser(description="JASM-Last für Top-TRE-Tage laden.")
    ap.add_argument("--year", type=int, default=dt.datetime.today().year)
    ap.add_argument("--appliance", type=str, default="Geschirrspüler")
    ap.add_argument("--top", type=int, default=24, help="Anzahl Top-Perioden (entspricht i.d.R. Top-Tagen)")
    ap.add_argument("--fx", type=float, default=None, help="EUR→CHF Multiplikator (z.B. 0.97). Standard: 1.0")
    ap.add_argument("--save", action="store_true", help="Ergebnis als CSV in data/market/processed/dr_windows speichern")
    args = ap.parse_args()

    try:
        run(args.year, args.appliance, args.top, args.fx, args.save)
    except Exception as e:
        print(f"[FEHLER] {e}")


if __name__ == "__main__":
    main()