# steps/step06_sozio_technisches_simulationsmodell/simulation/tre06_grid_shiftable_energy.py
from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
from typing import Any, Dict, List
import calendar
import sys

import numpy as np
import pandas as pd

# ------------------------------------------------------------
# Projektpfade & Helper
# ------------------------------------------------------------
def _project_root_from_file() -> Path:
    here = Path(__file__).resolve()
    for p in here.parents:
        if p.name == "steps":
            return p.parent
    return here.parents[4] if len(here.parents) >= 5 else Path.cwd()

PROJECT_ROOT = _project_root_from_file()
RESULTS_DIR  = PROJECT_ROOT / "data" / "market" / "processed" / "simulation"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

def _slugify(name: str) -> str:
    s = name.lower()
    repl = {"ä":"ae","ö":"oe","ü":"ue","ß":"ss","é":"e","è":"e","ê":"e","à":"a","á":"a","ô":"o","î":"i"}
    for k, v in repl.items():
        s = s.replace(k, v)
    return "".join(ch if ch.isalnum() else "_" for ch in s).strip("_")

def _to_utc_index(idx: pd.DatetimeIndex, local_tz: str = "Europe/Zurich") -> pd.DatetimeIndex:
    if idx.tz is None:
        try:
            return idx.tz_localize(local_tz, ambiguous="infer", nonexistent="shift_forward").tz_convert("UTC")
        except Exception:
            return idx.tz_localize("UTC", ambiguous="infer", nonexistent="shift_forward")
    return idx.tz_convert("UTC")

def _get_window_series(df: pd.DataFrame, start_utc: pd.Timestamp, end_utc: pd.Timestamp, col: str) -> pd.Series:
    if df is None or df.empty or col not in df.columns:
        return pd.Series(dtype=float)
    ser = df[col]
    mask = (ser.index >= start_utc) & (ser.index < end_utc)
    return ser.loc[mask]

# ------------------------------------------------------------
# Imports aus vorhandenen Steps
# ------------------------------------------------------------
from steps.step06_sozio_technisches_simulationsmodell.dr_windows.tre01_peak_price_finder import (
    find_top_tre_price_periods,
)
from steps.step06_sozio_technisches_simulationsmodell.dr_windows.tre03_dr_day_identifier import (
    compute_shortest_energy_windows,
    identify_dr_candidate_days,
)
from steps.step06_sozio_technisches_simulationsmodell.dr_windows.tre04_dr_day_ranker import (
    calculate_ranking_metrics_for_days,
)
from steps.step04_dataloaders.dataloaders.market.tertiary_regulation_loader import (
    load_regulation_range,
)
from steps.step04_dataloaders.dataloaders.lastprofile import (
    load_appliances as load_jasm_year_profile,
)

# Umfrage-Module (wie in tre05)
SRC_DIR = PROJECT_ROOT / "src"
if SRC_DIR.exists():
    sys.path.insert(0, str(SRC_DIR))

from steps.step06_sozio_technisches_simulationsmodell.flexibility_potential.a_survey_data_preparer import (
    prepare_survey_flexibility_data,
)
from steps.step06_sozio_technisches_simulationsmodell.flexibility_potential.b_participation_calculator import (
    calculate_participation_metrics,
)

# ------------------------------------------------------------
# Main
# ------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(
        description="TRE-06 – Netzsicht: maximal verschiebbare Strommenge je Event (mit tre05-Regeln)."
    )
    # Auswahl/Jahr
    ap.add_argument("--year", type=int, default=2024)
    ap.add_argument("--top", type=int, default=150)
    ap.add_argument("--appliance", type=str, default="Geschirrspüler")
    ap.add_argument("--threshold", type=float, default=70.0)
    ap.add_argument("--tz", type=str, default="Europe/Zurich")
    ap.add_argument("--fx", type=float, default=None)

    # Events (welche Tage/Fenster simulieren)
    ap.add_argument("--simulate_days", type=int, default=3)
    ap.add_argument("--offsets", type=float, nargs="*", default=[2.0, 1.0, 0.0])
    ap.add_argument("--durations", type=float, nargs="*", default=[1.5, 3.0, 4.5])

    # Geräteeigenschaften (Zyklus)
    ap.add_argument("--cycle_kwh", type=float, default=1.44, help="Energie eines Spülgangs [kWh].")
    ap.add_argument("--cycle_hours", type=float, default=1.5, help="Dauer eines Spülgangs [h].")
    ap.add_argument("--max_event_hours_paid", type=float, default=3.0, help="Max. bezahlte Eventdauer [h].")

    # Monatsbasis (für Angebot in % der Monatskosten; gleich wie tre05)
    ap.add_argument("--monthly_kwh", type=float, default=43.2, help="Standard 30*1.44 kWh.")
    ap.add_argument("--daily_kwh", type=float, default=None, help="Überschreibt monthly_kwh via Tage im Eventmonat.")

    # Vergütungs-/Teilnahmelogik (wie tre05)
    ap.add_argument("--base_comp_chf_kwh", type=float, default=0.29, help="Basiskostenmaßstab CHF/kWh.")
    ap.add_argument("--cap", type=float, default=0.629, help="Max. Teilnahmequote (z. B. 0.629).")
    ap.add_argument("--max_comp_pct", type=float, default=62.9, help="Max. Angebots-% der Monatskosten.")

    # Netzsicht: Größe der Zielpopulation
    ap.add_argument("--households", type=int, default=100000,
                    help="Anzahl erreichbarer Haushalte mit Gerät (Netzgebiet / Programmgröße).")

    # Ausgabe
    ap.add_argument("--save", action="store_true")
    args = ap.parse_args()

    YEAR           = args.year
    N_TOP          = args.top
    APPLIANCE_NAME = args.appliance
    THRESHOLD_PCT  = args.threshold
    LOCAL_TZ       = args.tz
    FX             = args.fx
    N_DAYS_SIM     = max(0, int(args.simulate_days))
    PRE_OFFSETS_H  = list(args.offsets)
    DURATIONS_H    = list(args.durations)

    CYCLE_KWH   = float(args.cycle_kwh)
    CYCLE_H     = float(args.cycle_hours)
    MAX_EVENT_H = float(args.max_event_hours_paid)

    MONTHLY_KWH_DEFAULT = float(args.monthly_kwh)
    DAILY_KWH_OPT       = None if args.daily_kwh is None else float(args.daily_kwh)

    BASE_PRICE_CHF_KWH_COMP = float(args.base_comp_chf_kwh)
    MAX_PARTICIPATION_CAP   = float(args.cap)
    MAX_COMP_PCT            = float(args.max_comp_pct)  # %-Punkte

    HH_IN_SCOPE             = max(0, int(args.households))

    INTERVAL_MIN = 15
    INTERVAL_H   = INTERVAL_MIN / 60.0

    # ----------------- Daten laden -----------------
    print("\n[Phase 0/5] Lade Jahres-Zeitreihen …")
    print("  • Lade komplette TRE-Preisdaten (Jahr) …")
    s0 = dt.datetime(YEAR, 1, 1, 0, 0, 0)
    e0 = dt.datetime(YEAR, 12, 31, 23, 59, 59)
    df_tre_all = load_regulation_range(start=s0, end=e0)
    if df_tre_all.empty or "avg_price_eur_mwh" not in df_tre_all.columns:
        raise SystemExit("FEHLER: TRE-Daten leer oder 'avg_price_eur_mwh' fehlt.")
    df_tre_all = df_tre_all[["avg_price_eur_mwh"]].copy()
    df_tre_all["tre_price_chf_kwh"] = df_tre_all["avg_price_eur_mwh"] / 1000.0
    df_tre_all.index = _to_utc_index(pd.to_datetime(df_tre_all.index), LOCAL_TZ)
    print("    → TRE Jahr zu UTC konvertiert.")

    print(f"  • Lade komplette JASM-Daten für '{APPLIANCE_NAME}' …")
    df_jasm_hourly = load_jasm_year_profile(appliances=[APPLIANCE_NAME], start=s0, end=e0, year=YEAR, group=True)
    if df_jasm_hourly is None or df_jasm_hourly.empty or APPLIANCE_NAME not in df_jasm_hourly.columns:
        raise SystemExit(f"FEHLER: JASM-Daten für '{APPLIANCE_NAME}' leer/fehlend.")
    df_jasm_hourly = df_jasm_hourly[[APPLIANCE_NAME]].copy()
    df_jasm_hourly.index = _to_utc_index(pd.to_datetime(df_jasm_hourly.index), LOCAL_TZ)
    df_jasm_15m_mw  = df_jasm_hourly.resample("15min").ffill()
    df_jasm_15m_mwh = df_jasm_15m_mw.copy()
    df_jasm_15m_mwh[f"{APPLIANCE_NAME}_mwh_interval"] = df_jasm_15m_mw[APPLIANCE_NAME] * INTERVAL_H
    print("    → JASM Stunde → 15min (ffill) → MWh/Intervall, alles UTC.")

    print("\n[Phase 1/5] Lade/prepare Umfragedaten …")
    df_survey = prepare_survey_flexibility_data()
    if df_survey.empty:
        raise SystemExit("FEHLER: Keine Umfragedaten geladen.")

    # ----------------- Ranking-Tage finden -----------------
    print("\n[Phase 2/5] Steps 1–4 (Peaks → Fenster → Kandidaten → Ranking) …")
    df_peaks = find_top_tre_price_periods(YEAR, n_top=N_TOP, fx=(FX if FX is not None else 1.0))
    if df_peaks is None or df_peaks.empty:
        raise SystemExit("FEHLER: Step1 – Topperioden leer.")
    df_peaks.index = _to_utc_index(pd.to_datetime(df_peaks.index), LOCAL_TZ)

    peak_days = sorted(set(df_peaks.index.date))
    if not peak_days:
        raise SystemExit("FEHLER: Keine Peak-Tage ermittelt.")

    mask_days   = pd.Index(df_jasm_15m_mwh.index.date).isin(peak_days)
    df_jasm_sel = df_jasm_15m_mwh.loc[mask_days, [APPLIANCE_NAME]].copy()
    windows     = compute_shortest_energy_windows(df_jasm_sel, col=APPLIANCE_NAME, threshold_pct=THRESHOLD_PCT)
    cand_days   = identify_dr_candidate_days(df_peaks, windows)
    ranked      = calculate_ranking_metrics_for_days(cand_days, df_peaks, windows)

    if not ranked:
        print("\n[INFO] Keine gerankten Tage gefunden — keine Simulation möglich.")
        return

    print(f"[INFO] {len(ranked)} gerankte Tage → simuliere Top {min(N_DAYS_SIM, len(ranked))} …")

    # ----------------- Simulation -----------------
    results: List[Dict[str, Any]] = []
    avg_cycle_power_kw = (CYCLE_KWH / CYCLE_H) if CYCLE_H > 0 else 0.0

    for i, r in enumerate(ranked[:N_DAYS_SIM], start=1):
        d: dt.date = r["date"]
        peaks_day  = df_peaks[df_peaks.index.date == d]

        # robust gegenüber alter Key-Benennung aus tre04
        max_price_key = "max_tre_price_in_window" if "max_tre_price_in_window" in r else "max_srl_price_in_window"
        ref_match  = peaks_day[np.isclose(peaks_day["price_chf_kwh"], r[max_price_key])]
        if ref_match.empty:
            print(f"[WARN] Kein Referenz-Peak für {d:%Y-%m-%d}.")
            continue
        ref = pd.to_datetime(ref_match.index[0]).tz_convert("UTC")
        max_price = float(r[max_price_key])

        print(f"\n— Tag {d:%Y-%m-%d} (Rank {i}), Referenz-Peak {ref:%Y-%m-%d %H:%M} @ {max_price:.4f} CHF/kWh —")

        for pre_off in PRE_OFFSETS_H:
            for dur_h in DURATIONS_H:
                start = ref - pd.Timedelta(hours=float(pre_off))
                end   = start + pd.Timedelta(hours=float(dur_h))

                # 1) Fenster schneiden & ausrichten
                jasm_raw = _get_window_series(df_jasm_15m_mwh, start, end, f"{APPLIANCE_NAME}_mwh_interval").rename("jasm_mwh")
                tre_raw  = _get_window_series(df_tre_all,     start, end, "tre_price_chf_kwh").rename("tre_chf_kwh")
                aligned  = pd.concat([jasm_raw, tre_raw], axis=1).dropna()

                if aligned.empty:
                    results.append({
                        "event_date": f"{d:%Y-%m-%d}", "rank_step4": i,
                        "event_start_utc": f"{start:%Y-%m-%d %H:%M}",
                        "event_duration_h": float(dur_h), "pre_peak_offset_h": float(pre_off),
                        "avg_tre_price_in_window_chf_kwh": float("nan"),
                        "shiftable_energy_mwh": 0.0,
                        "binding_constraint": "no_data",
                        "error_message": "No common 15-min slots in window",
                    })
                    continue

                jasm_mwh   = aligned["jasm_mwh"]
                tre_prices = aligned["tre_chf_kwh"]

                # --- Preis über das gesamte Eventfenster (nur Reporting) ---
                avg_tre_price_window = float(tre_prices.mean())

                # --- Cap für bezahlte Stunden & kWh/HH ---
                event_hours_paid_cap = float(min(float(dur_h), MAX_EVENT_H, CYCLE_H))
                event_kwh_cap        = float(min(CYCLE_KWH, avg_cycle_power_kw * event_hours_paid_cap))

                # --- Monatsbasis (für Angebots-%) ---
                if DAILY_KWH_OPT is not None:
                    days_in_month = calendar.monthrange(start.year, start.month)[1]
                    monthly_kwh_basis = DAILY_KWH_OPT * days_in_month
                else:
                    monthly_kwh_basis = MONTHLY_KWH_DEFAULT
                monthly_cost_basis_chf = monthly_kwh_basis * BASE_PRICE_CHF_KWH_COMP

                # --- Durchschnittspreis NUR über die bezahlten Stunden (erste n Slots) ---
                n_slots_paid = int(round(event_hours_paid_cap / INTERVAL_H))
                tre_prices_paid = tre_prices.iloc[:n_slots_paid] if n_slots_paid > 0 else tre_prices.iloc[0:0]
                avg_tre_price_paid = float(tre_prices_paid.mean()) if not tre_prices_paid.empty else float("nan")

                # >>>> FIX: Event-Cap KONSEQUENT vor der Iteration bestimmen
                event_max_comp_chf_per_hh = (avg_tre_price_paid * event_kwh_cap) if np.isfinite(avg_tre_price_paid) else 0.0
                event_max_comp_pct_of_month = (event_max_comp_chf_per_hh / monthly_cost_basis_chf * 100.0) \
                                              if monthly_cost_basis_chf > 1e-12 else 0.0

                # --- Teilnahme-Iteration: Angebots-% (wie tre05) ---
                MAX_ITERS = 50
                DAMP      = 0.5
                EPS_PCT   = 0.01

                offer_pct = 0.0
                prev_pct  = -1.0
                iters     = 0

                last_raw_particip = 0.0
                last_cap_particip = 0.0

                while abs(offer_pct - prev_pct) > EPS_PCT and iters < MAX_ITERS:
                    prev_pct = offer_pct
                    iters += 1

                    metrics = calculate_participation_metrics(
                        df_survey_flex_input= df_survey,
                        target_appliance    = APPLIANCE_NAME,
                        event_duration_h    = float(dur_h),
                        offered_incentive_pct = float(offer_pct),
                    )

                    raw_rate = float(min(max(metrics.get("raw_participation_rate", 0.0), 0.0), 1.0))
                    cap_rate = float(min(raw_rate, MAX_PARTICIPATION_CAP))  # <= 62.9%

                    # ökonomische Zielgröße (für next_offer): Wert im Fenster bei cap_rate
                    shifted_series_mwh_base = jasm_mwh * cap_rate
                    shifted_sum_mwh_base    = float(shifted_series_mwh_base.sum())

                    if shifted_sum_mwh_base <= 1e-12:
                        tre_value  = 0.0
                        next_offer = 0.0
                    else:
                        tre_value  = float((shifted_series_mwh_base * 1000.0 * tre_prices).sum())
                        base_cost  = shifted_sum_mwh_base * 1000.0 * BASE_PRICE_CHF_KWH_COMP
                        ratio      = (tre_value / base_cost) if base_cost > 1e-12 else 0.0
                        next_offer = ratio * 100.0

                    # Angebots-% deckeln: global & Event-% (aus bezahlten Stunden)
                    next_offer = max(0.0, min(next_offer, MAX_COMP_PCT, event_max_comp_pct_of_month))
                    offer_pct  = DAMP * prev_pct + (1.0 - DAMP) * next_offer

                    last_raw_particip = raw_rate
                    last_cap_particip = cap_rate

                converged = (iters < MAX_ITERS) or (abs(offer_pct - prev_pct) <= EPS_PCT)
                part_rate = last_cap_particip  # endgültige Teilnahmequote (<= 0.629)

                # --- Netzsicht: maximal verschiebbare Energie ---
                # (1) Fensterlimit (Angebot im Fenster) bei Teilnahme:
                window_limit_mwh = float((jasm_mwh * part_rate).sum())

                # (2) Haushaltslimit (jeder HH kann höchstens event_kwh_cap verschieben):
                hh_limit_mwh = (HH_IN_SCOPE * part_rate * event_kwh_cap) / 1000.0

                # Tatsächliche Verschiebbarkeit = Min aus beiden
                if window_limit_mwh <= hh_limit_mwh + 1e-12:
                    shiftable_mwh = window_limit_mwh
                    binding = "window_limit"
                else:
                    shiftable_mwh = hh_limit_mwh
                    binding = "per_household_cap"

                # Pro-Haushalt-Auszahlung (für Info, gedeckelt wie tre05)
                comp_theoretical_chf = (offer_pct / 100.0) * monthly_cost_basis_chf
                comp_cap_chf         = event_max_comp_chf_per_hh
                comp_per_hh_event_chf = float(min(comp_theoretical_chf, comp_cap_chf))

                # Reporting
                results.append({
                    "event_date": f"{d:%Y-%m-%d}",
                    "rank_step4": i,
                    "reference_peak_utc": f"{ref:%Y-%m-%d %H:%M}",
                    "event_start_utc": f"{start:%Y-%m-%d %H:%M}",
                    "event_duration_h": float(dur_h),
                    "pre_peak_offset_h": float(pre_off),

                    "avg_tre_price_in_window_chf_kwh": float(avg_tre_price_window),

                    # Caps/Herleitungen (bezahlt)
                    "event_hours_paid_cap": float(event_hours_paid_cap),
                    "event_kwh_cap": float(event_kwh_cap),
                    "avg_tre_price_paid_h_chf_kwh": float(avg_tre_price_paid) if np.isfinite(avg_tre_price_paid) else float("nan"),
                    "event_max_comp_chf_per_hh": float(event_max_comp_chf_per_hh),

                    # Monatsbasis
                    "kompensations_basis_energie_kwh": float(monthly_kwh_basis),
                    "kompensations_basis_kosten_chf": float(monthly_cost_basis_chf),

                    # Angebot/Teilnahme
                    "konvergierter_komp_prozentsatz": float(offer_pct),
                    "finale_teilnahmequote": float(part_rate),

                    # Netzeffekte (Grenzen & Ergebnis)
                    "window_limit_mwh": float(window_limit_mwh),
                    "hh_limit_mwh": float(hh_limit_mwh),
                    "shiftable_energy_mwh": float(shiftable_mwh),
                    "binding_constraint": binding,

                    # Kontext
                    "households_in_scope": int(HH_IN_SCOPE),
                    "kompensation_pro_haushalt_pro_event_chf": float(comp_per_hh_event_chf),

                    "iterations_to_converge": int(iters),
                    "converged": bool(converged),
                    "error_message": None,
                })

    # ----------------- Ausgabe -----------------
    print("\n[Phase 4/5] Zusammenfassung (Top je Tag) …")
    if not results:
        print("Keine Ergebnisse.")
        return

    df = pd.DataFrame(results)

    # Pro Tag die Maximum-Zeile (nach verschiebbarer Energie)
    idx = df.groupby("event_date")["shiftable_energy_mwh"].idxmax()
    best_per_day = df.loc[idx].copy().sort_values(["event_date"])

    cols_show = [
        "event_date","rank_step4","event_duration_h","pre_peak_offset_h",
        "shiftable_energy_mwh","binding_constraint",
        "finale_teilnahmequote","konvergierter_komp_prozentsatz",
        "event_hours_paid_cap","event_kwh_cap",
        "avg_tre_price_in_window_chf_kwh","avg_tre_price_paid_h_chf_kwh",
        "event_max_comp_chf_per_hh",
        "kompensation_pro_haushalt_pro_event_chf",
        "households_in_scope",
    ]
    fmt = {
        "shiftable_energy_mwh": "{:.3f}".format,
        "finale_teilnahmequote": "{:.2%}".format,
        "konvergierter_komp_prozentsatz": "{:.2f}%".format,
        "event_hours_paid_cap": "{:.2f}".format,
        "event_kwh_cap": "{:.2f}".format,
        "avg_tre_price_in_window_chf_kwh": "{:.4f}".format,
        "avg_tre_price_paid_h_chf_kwh": "{:.4f}".format,
        "event_max_comp_chf_per_hh": "{:.2f}".format,
        "kompensation_pro_haushalt_pro_event_chf": "{:.2f}".format,
    }

    print("\n— Maximale verschiebbare Energie pro Tag (Bestes Fenster) —")
    print(best_per_day[cols_show].to_string(index=False, formatters={k:v for k,v in fmt.items() if k in cols_show}))

    # Speichern
    print("\n[Phase 5/5] Speichern …")
    slug = _slugify(APPLIANCE_NAME)
    fx_tag = f"_fx{FX:.2f}" if FX is not None and abs(FX - 1.0) > 1e-9 else ""
    if args.save:
        detailed = RESULTS_DIR / f"tre06_shiftable_energy_detailed_{slug}_{YEAR}_top{N_TOP}_thr{int(THRESHOLD_PCT)}{fx_tag}.csv"
        summary  = RESULTS_DIR / f"tre06_shiftable_energy_summary_{slug}_{YEAR}_top{N_TOP}_thr{int(THRESHOLD_PCT)}{fx_tag}.csv"
        df.to_csv(detailed, index=False, sep=";", decimal=".")
        best_per_day.to_csv(summary, index=False, sep=";", decimal=".")
        print(f"[INFO] Detail gespeichert:  {detailed}")
        print(f"[INFO] Summary gespeichert: {summary}")

if __name__ == "__main__":
    main()