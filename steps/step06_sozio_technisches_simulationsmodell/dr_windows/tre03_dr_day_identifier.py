# steps/step06_sozio_technisches_simulationsmodell/dr_windows/tre03_dr_day_identifier.py
"""
Identifiziere DR-Kandidatentage: Mindestens eine TRE-Preisspitze liegt innerhalb
des kürzesten JASM-Zeitfensters, das >= <threshold>% der Tagesenergie abdeckt.

CLI-Beispiele:
  # Standard: 2024, Geschirrspüler, Top 150 Perioden, 70% Fenster
  python -m steps.step06_sozio_technisches_simulationsmodell.dr_windows.tre03_dr_day_identifier --year 2024

  # Mit FX 0.97, anderes Gerät, speichern
  python -m steps.step06_sozio_technisches_simulationsmodell.dr_windows.tre03_dr_day_identifier \
    --year 2024 --appliance "Geschirrspüler" --top 200 --threshold 70 --fx 0.97 --save

Ausgabe (bei --save):
  data/market/processed/dr_windows/tre_windows_<slug>_<year>_top<T>_thr<THR>[ _fx<FX> ].csv
  data/market/processed/dr_windows/tre_dr_days_<slug>_<year>_top<T>_thr<THR>[ _fx<FX> ].csv
"""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# ----------------------- Pfade -----------------------

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
    s2 = s.lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        s2 = s2.replace(a, b)
    return "".join(ch if ch.isalnum() else "_" for ch in s2).strip("_")

def _fname_windows(year: int, appliance: str, top: int, thr: float, fx: Optional[float]) -> Path:
    slug = _slug(appliance)
    base = f"tre_windows_{slug}_{year}_top{top}_thr{int(round(thr))}"
    if fx is not None and abs(fx - 1.0) > 1e-9:
        base += f"_fx{fx:.2f}"
    return OUT_DIR / f"{base}.csv"

def _fname_days(year: int, appliance: str, top: int, thr: float, fx: Optional[float]) -> Path:
    slug = _slug(appliance)
    base = f"tre_dr_days_{slug}_{year}_top{top}_thr{int(round(thr))}"
    if fx is not None and abs(fx - 1.0) > 1e-9:
        base += f"_fx{fx:.2f}"
    return OUT_DIR / f"{base}.csv"


# ----------------------- Loader -----------------------

from steps.step04_dataloaders.dataloaders.market.dr_windows_loader import (
    load_tre_top_periods,
)
try:
    from steps.step04_dataloaders.dataloaders.lastprofile import load_appliances as load_jasm_profiles
except Exception:
    # optionaler Fallback-Name, falls dein Projekt den Loader anders nennt
    from steps.step04_dataloaders.dataloaders.jasm import load_appliances as load_jasm_profiles  # type: ignore


# ----------------------- Kernfunktionen -----------------------

def compute_shortest_energy_windows(
    df: pd.DataFrame,
    col: str,
    threshold_pct: float,
) -> Dict[dt.date, Optional[Tuple[dt.time, dt.time, float, float]]]:
    """
    Für jeden Tag im DataFrame (Index=DatetimeIndex) berechne das kürzeste zusammenhängende
    Zeitfenster, dessen Summenanteil >= threshold_pct % des Tagesgesamtverbrauchs ist.
    Rückgabe:
      { date -> (start_time, end_time, window_sum, window_pct) } oder None, wenn nicht berechenbar.
    """
    out: Dict[dt.date, Optional[Tuple[dt.time, dt.time, float, float]]] = {}

    if df is None or df.empty or col not in df.columns:
        return out

    # Stelle sicher, dass wir mit einem DatetimeIndex arbeiten
    if not isinstance(df.index, pd.DatetimeIndex):
        df = df.copy()
        df.index = pd.to_datetime(df.index)

    # Gruppiere exakt nach Tagesbeginn-Timestamps und wandle Schlüssel explizit in date um
    for key, ddf in df.groupby(df.index.normalize()):
        day_ts: pd.Timestamp = pd.Timestamp(key)
        day: dt.date = day_ts.date()

        # Werte als float-Serie mit DatetimeIndex
        idx: pd.DatetimeIndex = pd.DatetimeIndex(ddf.index)
        s = pd.Series(ddf[col].astype(float).values, index=idx)

        if s.empty or float(s.sum()) <= 0.0:
            out[day] = None
            continue

        target = float(s.sum()) * (threshold_pct / 100.0)
        vals = s.values.astype(float, copy=False)
        n = len(vals)

        left = 0
        cur = 0.0
        best_len = np.inf
        best_pair: Optional[Tuple[int, int]] = None

        for right in range(n):
            cur += vals[right]
            while left <= right and (cur - vals[left]) >= target:
                cur -= vals[left]
                left += 1
            if cur >= target:
                win_len = right - left + 1
                if win_len < best_len:
                    best_len = win_len
                    best_pair = (left, right)

        if best_pair is None:
            out[day] = None
            continue

        l, r = best_pair

        # Schrittweite klar als Timedelta (zur Not 15 min fallback)
        if len(idx) >= 2:
            step: pd.Timedelta = pd.Timedelta(idx[1] - idx[0])
        else:
            step = pd.Timedelta(minutes=15)

        start_ts: pd.Timestamp = pd.Timestamp(idx[l])
        end_ts: pd.Timestamp = pd.Timestamp(idx[r]) + step

        # 00:00 anzeigen, wenn formales Ende am Folgetag (über Mitternacht)
        end_time: dt.time = end_ts.time() if end_ts.date() == start_ts.date() else dt.time(0, 0)

        win_sum = float(s.iloc[l : r + 1].sum())
        pct = float(100.0 * win_sum / float(s.sum()))

        out[day] = (start_ts.time(), end_time, win_sum, pct)

    return out


def identify_dr_candidate_days(
    tre_peaks: pd.DataFrame,
    windows: Dict[dt.date, Optional[Tuple[dt.time, dt.time, float, float]]],
) -> List[dt.date]:
    """
    Ein Tag ist DR-Kandidat, wenn mindestens eine TRE-Preisspitze des Tages innerhalb
    des Geräte-Fensters liegt.
    Fenster-Regeln:
      - start < end: klassisches Tagesfenster
      - start != 00:00 und end == 00:00: bis Tagesende
      - start == end == 00:00: 24h-Fenster
    """
    days: List[dt.date] = []
    if tre_peaks is None or tre_peaks.empty or not windows:
        return days
    if not isinstance(tre_peaks.index, pd.DatetimeIndex):
        tre_peaks = tre_peaks.copy()
        tre_peaks.index = pd.to_datetime(tre_peaks.index)

    for day, win in windows.items():
        if win is None:
            continue
        start_t, end_t, _, _ = win
        mask = tre_peaks.index.date == day
        peaks = tre_peaks.loc[mask]
        if peaks.empty:
            continue
        for ts in peaks.index:
            t = ts.time()
            overlap = False
            if start_t < end_t:
                overlap = (start_t <= t < end_t)
            elif end_t == dt.time(0, 0) and start_t != dt.time(0, 0):
                overlap = (t >= start_t)  # bis Tagesende
            elif start_t == dt.time(0, 0) and end_t == dt.time(0, 0):
                overlap = True  # 24h
            if overlap:
                days.append(day)
                break
    return sorted(set(days))


# ----------------------- High-Level Run -----------------------

def run(
    year: int,
    appliance: str,
    top: int,
    threshold_pct: float,
    fx: Optional[float],
    save: bool,
) -> Tuple[pd.DataFrame, List[dt.date]]:
    print(f"[INFO] Lade Top-{top} TRE-Perioden {year} …")
    tre = load_tre_top_periods(year, fx=fx)
    if tre.empty:
        raise RuntimeError("Keine TRE-Preisfenster gefunden.")
    if len(tre) > top:
        tre = tre.nlargest(top, "price_chf_kwh")

    # relevante Tage
    days = sorted(set(tre.index.normalize().date))
    print(f"[INFO] Relevante Tage: {len(days)} → {days[:5]}{' …' if len(days) > 5 else ''}")

    # JASM-Daten für diese Tage laden
    start_dt = dt.datetime.combine(min(days), dt.time.min)
    end_dt   = dt.datetime.combine(max(days), dt.time.max)
    df_jasm = load_jasm_profiles(
        appliances=[appliance],
        start=start_dt,
        end=end_dt,
        year=year,
        group=True,
    )
    if df_jasm is None or df_jasm.empty or appliance not in df_jasm.columns:
        raise RuntimeError(f"Keine JASM-Daten für '{appliance}' im Bereich {start_dt}–{end_dt}.")

    if not isinstance(df_jasm.index, pd.DatetimeIndex):
        df_jasm.index = pd.to_datetime(df_jasm.index)

    # nur die relevanten Tage
    mask = df_jasm.index.normalize().isin({pd.Timestamp(d) for d in days})
    df_jasm = df_jasm.loc[mask, [appliance]].copy()

    # Kürzeste Fenster pro Tag
    windows = compute_shortest_energy_windows(df_jasm, appliance, threshold_pct)

    # DR-Kandidaten bestimmen
    dr_days = identify_dr_candidate_days(tre, windows)

    print("\n--- ERGEBNIS ---")
    if dr_days:
        print(f"{len(dr_days)} Tag(e) erfüllen die DR-Bedingungen für '{appliance}' "
              f"(Top {top} TRE-Spitzen, {threshold_pct:.0f}%-Fenster):")
        for d in dr_days:
            print(d.strftime("%Y-%m-%d"))
    else:
        print(f"Keine passenden Tage gefunden (Top {top}, {threshold_pct:.0f}%).")

    # optional speichern
    if save:
        # Fenster-Tabelle
        rows = []
        for d, win in windows.items():
            if win is None:
                rows.append({"date": d, "start": None, "end": None, "window_pct": None, "window_sum": None})
            else:
                st, en, ssum, pct = win
                rows.append({
                    "date": d,
                    "start": st.strftime("%H:%M"),
                    "end":   en.strftime("%H:%M"),
                    "window_pct": round(pct, 3),
                    "window_sum": ssum,
                })
        df_windows = pd.DataFrame(rows).sort_values("date")
        p_win = _fname_windows(year, appliance, top, threshold_pct, fx)
        df_windows.to_csv(p_win, index=False)
        print(f"[INFO] Fenster gespeichert: {p_win}")

        # Kandidatentage
        df_days = pd.DataFrame({"date": [d.strftime("%Y-%m-%d") for d in dr_days]})
        p_days = _fname_days(year, appliance, top, threshold_pct, fx)
        df_days.to_csv(p_days, index=False)
        print(f"[INFO] DR-Tage gespeichert: {p_days}")

    return df_jasm, dr_days


# ----------------------- CLI -----------------------

def main():
    ap = argparse.ArgumentParser(description="DR-Kandidatentage anhand TRE-Peaks & JASM-Fenstern ermitteln.")
    ap.add_argument("--year", type=int, default=dt.datetime.today().year)
    ap.add_argument("--appliance", type=str, default="Geschirrspüler")
    ap.add_argument("--top", type=int, default=150, help="Anzahl Top-TRE-Perioden")
    ap.add_argument("--threshold", type=float, default=70.0, help="Energie-Schwelle in % (pro Tag)")
    ap.add_argument("--fx", type=float, default=None, help="EUR→CHF Multiplikator (z. B. 0.97)")
    ap.add_argument("--save", action="store_true", help="Ergebnisse als CSV in data/market/processed/dr_windows speichern")
    args = ap.parse_args()

    try:
        run(args.year, args.appliance, args.top, args.threshold, args.fx, args.save)
    except Exception as e:
        print(f"[FEHLER] {e}")

if __name__ == "__main__":
    main()
