# steps/step06_sozio_technisches_simulationsmodell/dr_windows/tre04_dr_day_ranker.py
from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

# --- Projektpfade & Utilities -------------------------------------------------
def _project_root_from_file() -> Path:
    here = Path(__file__).resolve()
    for p in here.parents:
        if p.name == "steps":
            return p.parent
    return here.parents[4] if len(here.parents) >= 5 else Path.cwd()

PROJECT_ROOT = _project_root_from_file()
OUT_DIR = PROJECT_ROOT / "data" / "market" / "processed" / "dr_windows"
OUT_DIR.mkdir(parents=True, exist_ok=True)

def _slugify(name: str) -> str:
    s = name.lower()
    repl = {
        "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
        "é": "e", "è": "e", "ê": "e", "à": "a", "á": "a", "ô": "o", "î": "i",
    }
    for k, v in repl.items():
        s = s.replace(k, v)
    return "".join(ch if ch.isalnum() else "_" for ch in s).strip("_")

# --- Imports aus vorigen Steps ------------------------------------------------
# Step 1: Top-TRE-Preise
from .tre01_peak_price_finder import find_top_tre_price_periods
# Step 3: Fenster und Kandidatentage
from .tre03_dr_day_identifier import (
    compute_shortest_energy_windows,
    identify_dr_candidate_days,
)
# JASM Loader
from ...step04_dataloaders.dataloaders.lastprofile import load_appliances as load_jasm

# --- Kernlogik ----------------------------------------------------------------
def _time_diff_hours(start: dt.time, end: dt.time) -> float:
    """Dauer (h) zwischen start und end am selben Kalendertag.
    Sonderfall: end == 00:00 => interpretiere als bis Mitternacht (24:00)."""
    if start == end == dt.time(0, 0):
        return 24.0
    s = dt.datetime.combine(dt.date(2000, 1, 1), start)
    e = dt.datetime.combine(dt.date(2000, 1, 1), end)
    if e > s:
        return (e - s).total_seconds() / 3600.0
    # end == 00:00 (Mitternacht) → bis Tagesende
    if end == dt.time(0, 0) and start != dt.time(0, 0):
        last = dt.datetime.combine(dt.date(2000, 1, 1), dt.time(23, 59))
        return ((last - s).total_seconds() + 60.0) / 3600.0  # ~ bis 24:00
    return 0.0

def calculate_ranking_metrics_for_days(
    candidate_days: List[dt.date],
    srl_peak_data: pd.DataFrame,
    appliance_windows: Dict[dt.date, Optional[Tuple[dt.time, dt.time, float, float]]],
) -> List[Dict[str, Any]]:
    """
    Berechnet Metriken pro Tag:
      - max_srl_price_in_window
      - avg_srl_price_in_window
      - count_srl_peaks_in_window
      - sum_srl_prices_in_window
      - appliance_window_duration_h
      - appliance_window_energy_sum
      - appliance_window_energy_pct
    Erwartet in srl_peak_data eine Spalte 'price_chf_kwh'.
    """
    out: List[Dict[str, Any]] = []
    if not candidate_days or srl_peak_data is None or srl_peak_data.empty or not appliance_windows:
        return out

    df = srl_peak_data.copy()
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)

    for day in candidate_days:
        win = appliance_windows.get(day)
        if win is None:
            continue
        start_t, end_t, win_sum, win_pct = win

        peaks_day = df[df.index.normalize().date == day]
        if peaks_day.empty:
            continue

        max_price = 0.0
        prices_in = []
        count_in = 0
        sum_in = 0.0

        for ts, row in peaks_day.iterrows():
            t = ts.time()
            price = float(row.get("price_chf_kwh", float("nan")))
            if pd.isna(price):
                continue

            overlap = False
            if start_t < end_t:  # normaler Tagesbereich
                overlap = (start_t <= t < end_t)
            elif end_t == dt.time(0, 0) and start_t != dt.time(0, 0):  # bis Mitternacht
                overlap = (t >= start_t)
            elif start_t == dt.time(0, 0) and end_t == dt.time(0, 0):  # 24h
                overlap = True

            if overlap:
                count_in += 1
                sum_in += price
                prices_in.append(price)
                if price > max_price:
                    max_price = price

        if count_in > 0:
            avg_price = sum(prices_in) / len(prices_in) if prices_in else 0.0
            out.append({
                "date": day,
                "max_srl_price_in_window": max_price,
                "avg_srl_price_in_window": avg_price,
                "count_srl_peaks_in_window": count_in,
                "sum_srl_prices_in_window": sum_in,
                "appliance_window_duration_h": _time_diff_hours(start_t, end_t),
                "appliance_window_energy_sum": float(win_sum),
                "appliance_window_energy_pct": float(win_pct),
                "appliance_window_start": start_t.strftime("%H:%M"),
                "appliance_window_end": end_t.strftime("%H:%M"),
            })

    # Ranking: 1) max Preis, 2) Anzahl Overlaps
    out.sort(
        key=lambda x: (x["max_srl_price_in_window"], x["count_srl_peaks_in_window"]),
        reverse=True,
    )
    return out

# --- CLI ----------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Rankt DR-Kandidatentage basierend auf TRE-Preisspitzen & JASM-Fenstern.")
    ap.add_argument("--year", type=int, default=2024, help="Analysejahr")
    ap.add_argument("--top", type=int, default=150, help="Anzahl Top-TRE-Perioden")
    ap.add_argument("--appliance", type=str, default="Geschirrspüler", help="Gerätename aus JASM")
    ap.add_argument("--threshold", type=float, default=70.0, help="Energie-Schwelle in % (für Fenster)")
    ap.add_argument("--fx", type=float, default=None, help="EUR→CHF Kurs (optional, z.B. 0.97)")
    ap.add_argument("--save", action="store_true", help="Ranking als CSV speichern")
    ap.add_argument("--tz", type=str, default="Europe/Zurich", help="Zeitzone für JASM (nur fürs Laden)")
    args = ap.parse_args()

    year = args.year
    n_top = args.top
    appliance = args.appliance
    thr = args.threshold
    fx = args.fx

    print(f"[INFO] Lade Top-{n_top} TRE-Perioden {year} …")
    df_peaks = find_top_tre_price_periods(year, n_top=n_top, fx=fx)
    if df_peaks is None or df_peaks.empty:
        print("[FEHLER] Keine TRE-Topperioden geladen.")
        return
    if not isinstance(df_peaks.index, pd.DatetimeIndex):
        df_peaks.index = pd.to_datetime(df_peaks.index)

    # Relevante Tage
    days = sorted(set(df_peaks.index.normalize().date))
    print(f"[INFO] Relevante Tage: {len(days)}")

    # JASM für diese Tage laden
    if days:
        start = dt.datetime.combine(min(days), dt.time.min)
        end   = dt.datetime.combine(max(days), dt.time.max)
        df_jasm = load_jasm(appliances=[appliance], start=start, end=end, year=year, group=True)
        if df_jasm is None or df_jasm.empty or appliance not in df_jasm.columns:
            print(f"[FEHLER] Keine JASM-Daten für '{appliance}' im Zeitraum {start.date()}–{end.date()}.")
            return
        if not isinstance(df_jasm.index, pd.DatetimeIndex):
            df_jasm.index = pd.to_datetime(df_jasm.index)
        # Nur die gewünschten Tage filtern
        mask = df_jasm.index.normalize().isin([pd.Timestamp(d) for d in days])
        df_jasm = df_jasm.loc[mask, [appliance]]
    else:
        print("[FEHLER] Keine Tage aus Topperioden ermittelt.")
        return

    # Fenster je Tag berechnen
    windows = compute_shortest_energy_windows(df_jasm, col=appliance, threshold_pct=thr)

    # Kandidatentage bestimmen (Überlapp mit Top-TRE)
    cand = identify_dr_candidate_days(df_peaks, windows)

    # Ranking berechnen
    ranked = calculate_ranking_metrics_for_days(cand, df_peaks, windows)

    # Ausgabe
    if ranked:
        print("\n--- ERGEBNIS (GERANKT) ---")
        print(f"{len(ranked)} Tag(e) bewertet für '{appliance}'.")
        header = (
            f"{'Rank':<5} | {'Datum':<10} | {'max CHF/kWh':<12} | "
            f"{'#Overlaps':<9} | {'Ø CHF/kWh':<10} | {'Σ CHF/kWh':<10} | "
            f"{'Win(h)':<6} | {'Win%':<6} | {'Start':<5} | {'Ende':<5}"
        )
        print(header)
        print("-" * len(header))
        for i, row in enumerate(ranked, start=1):
            print(
                f"{i:<5} | {row['date']:%Y-%m-%d} | "
                f"{row['max_srl_price_in_window']:<12.4f} | "
                f"{row['count_srl_peaks_in_window']:<9d} | "
                f"{row['avg_srl_price_in_window']:<10.4f} | "
                f"{row['sum_srl_prices_in_window']:<10.4f} | "
                f"{row['appliance_window_duration_h']:<6.2f} | "
                f"{row['appliance_window_energy_pct']:<6.1f} | "
                f"{row['appliance_window_start']:<5} | {row['appliance_window_end']:<5}"
            )
    else:
        print("\n--- ERGEBNIS ---\nKeine Tage gefunden, die gerankt werden konnten.")

    # Optional speichern
    if args.save and ranked:
        slug = _slugify(appliance)
        if fx is not None:
            fname = f"tre_ranked_days_{slug}_{year}_top{n_top}_thr{int(thr)}_fx{fx:.2f}.csv"
        else:
            fname = f"tre_ranked_days_{slug}_{year}_top{n_top}_thr{int(thr)}_.csv"
        out = OUT_DIR / fname
        pd.DataFrame(ranked).to_csv(out, index=False)
        print(f"[INFO] Ranking gespeichert: {out}")

if __name__ == "__main__":
    main()