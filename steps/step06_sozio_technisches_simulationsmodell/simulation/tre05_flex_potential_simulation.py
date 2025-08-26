# steps/step06_sozio_technisches_simulationsmodell/simulation/tre05_flex_potential_simulation.py
from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import calendar
import sys

# ------------------------------------------------------------
# Projektpfade
# ------------------------------------------------------------
def _project_root_from_file() -> Path:
    here = Path(__file__).resolve()
    for p in here.parents:
        if p.name == "steps":
            return p.parent
    return here.parents[4] if len(here.parents) >= 5 else Path.cwd()

PROJECT_ROOT = _project_root_from_file()
RESULTS_DIR = PROJECT_ROOT / "data" / "market" / "processed" / "simulation"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

def _slugify(name: str) -> str:
    s = name.lower()
    repl = {"ä":"ae","ö":"oe","ü":"ue","ß":"ss","é":"e","è":"e","ê":"e","à":"a","á":"a","ô":"o","î":"i"}
    for k,v in repl.items(): s = s.replace(k,v)
    return "".join(ch if ch.isalnum() else "_" for ch in s).strip("_")

# ------------------------------------------------------------
# Imports aus vorhandenen Steps & Dataloaders
# ------------------------------------------------------------
from steps.step06_sozio_technisches_simulationsmodell.dr_windows.tre01_peak_price_finder import (
    find_top_tre_price_periods
)
from steps.step06_sozio_technisches_simulationsmodell.dr_windows.tre03_dr_day_identifier import (
    compute_shortest_energy_windows,
    identify_dr_candidate_days,
)
from steps.step06_sozio_technisches_simulationsmodell.dr_windows.tre04_dr_day_ranker import (
    calculate_ranking_metrics_for_days
)
from steps.step04_dataloaders.dataloaders.market.tertiary_regulation_loader import (
    load_regulation_range
)
from steps.step04_dataloaders.dataloaders.lastprofile import (
    load_appliances as load_jasm_year_profile
)

# Survey-Module (lokal in steps/*)
SRC_DIR = PROJECT_ROOT / "src"
if SRC_DIR.exists():
    sys.path.insert(0, str(SRC_DIR))

from steps.step06_sozio_technisches_simulationsmodell.flexibility_potential.a_survey_data_preparer import (
    prepare_survey_flexibility_data
)
from steps.step06_sozio_technisches_simulationsmodell.flexibility_potential.b_participation_calculator import (
    calculate_participation_metrics
)

# ------------------------------------------------------------
# Helfer
# ------------------------------------------------------------
def _to_utc_index(idx: pd.DatetimeIndex, local_tz: str = "Europe/Zurich") -> pd.DatetimeIndex:
    if idx.tz is None:
        try:
            return idx.tz_localize(local_tz, ambiguous="infer", nonexistent="shift_forward").tz_convert("UTC")
        except Exception:
            return idx.tz_localize("UTC", ambiguous="infer", nonexistent="shift_forward")
    return idx.tz_convert("UTC")

def get_data_for_specific_window(
    df_timeseries: pd.DataFrame,
    start_utc: pd.Timestamp,
    end_utc: pd.Timestamp,
    value_column: str
) -> pd.Series:
    """Gibt IMMER eine Series zurück (für Pylance & Robustheit)."""
    if df_timeseries is None or df_timeseries.empty or value_column not in df_timeseries.columns:
        return pd.Series(dtype=float)
    ser = df_timeseries[value_column]
    mask = (ser.index >= start_utc) & (ser.index < end_utc)
    return ser.loc[mask]

# ------------------------------------------------------------
# Main
# ------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(
        description="Step 5 – Simulation des umfragebasierten Flexibilitätspotenzials (Geschirrspüler, TRE)."
    )
    ap.add_argument("--year", type=int, default=2024)
    ap.add_argument("--top", type=int, default=150)
    ap.add_argument("--appliance", type=str, default="Geschirrspüler")
    ap.add_argument("--threshold", type=float, default=70.0)
    ap.add_argument("--tz", type=str, default="Europe/Zurich")
    ap.add_argument("--fx", type=float, default=None)
    ap.add_argument("--simulate_days", type=int, default=3)
    ap.add_argument("--offsets", type=float, nargs="*", default=[2.0, 1.0, 0.0])
    ap.add_argument("--durations", type=float, nargs="*", default=[1.5, 3.0, 4.5])

    # Geräteeigenschaften (Standard: 1 Zyklus ~ 1.44 kWh in 1.5 h)
    ap.add_argument("--cycle_kwh", type=float, default=1.44,
                    help="Energie eines vollständigen Geschirrspüler-Zyklus [kWh].")
    ap.add_argument("--cycle_hours", type=float, default=1.5,
                    help="Dauer eines vollständigen Zyklus [h].")
    ap.add_argument("--max_event_hours_paid", type=float, default=3.0,
                    help="Max. vergütete Eventdauer (Zeit-Cap) [h].")

    # Monatsbasis (entweder fix oder dynamisch via daily_kwh * Tage_im_Monat)
    ap.add_argument("--monthly_kwh", type=float, default=43.2,
                    help="Monatlicher Energieverbrauch des Geräts [kWh]. Standard 30*1.44.")
    ap.add_argument("--daily_kwh", type=float, default=None,
                    help="Durchschnittlicher Tagesverbrauch [kWh]. Überschreibt monthly_kwh pro Eventmonat.")

    # Vergütungslogik
    ap.add_argument("--base_comp_chf_kwh", type=float, default=0.29,
                    help="Basis-Kompensation (Preismaßstab) in CHF/kWh.")
    ap.add_argument("--cap", type=float, default=0.629,
                    help="Maximale Teilnahmequote (z. B. 0.629 = 62.9%).")
    ap.add_argument("--max_comp_pct", type=float, default=62.9,
                    help="Maximales Angebots-% der monatlichen Gerätekosten (z. B. 62.9).")

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

    CYCLE_KWH      = float(args.cycle_kwh)
    CYCLE_H        = float(args.cycle_hours)
    MAX_EVENT_H    = float(args.max_event_hours_paid)

    MONTHLY_KWH_DEFAULT = float(args.monthly_kwh)
    DAILY_KWH_OPT       = None if args.daily_kwh is None else float(args.daily_kwh)

    BASE_PRICE_CHF_KWH_COMPENSATION = float(args.base_comp_chf_kwh)
    MAX_PARTICIPATION_CAP           = float(args.cap)
    MAX_COMP_PCT                    = float(args.max_comp_pct)  # %-Punkte, nicht Anteil

    INTERVAL_MIN = 15
    INTERVAL_H   = INTERVAL_MIN / 60.0

    print("\n[Phase 0/5] Lade Jahres-Zeitreihen …")

    # TRE (Jahr)
    print("  • Lade komplette TRE-Preisdaten (Jahr) …")
    s0 = dt.datetime(YEAR, 1, 1, 0, 0, 0)
    e0 = dt.datetime(YEAR, 12, 31, 23, 59, 59)
    df_tre_all = load_regulation_range(start=s0, end=e0)
    if df_tre_all.empty or "avg_price_eur_mwh" not in df_tre_all.columns:
        raise SystemExit("FEHLER: TRE-Daten leer oder 'avg_price_eur_mwh' fehlt.")
    df_tre_all = df_tre_all[["avg_price_eur_mwh"]].copy()
    # Annahme: avg_price_eur_mwh ≈ CHF/MWh (Deine Loader rechnen die FX bereits ein, falls FX gesetzt wurde)
    df_tre_all["tre_price_chf_kwh"] = df_tre_all["avg_price_eur_mwh"] / 1000.0
    df_tre_all.index = _to_utc_index(pd.to_datetime(df_tre_all.index), LOCAL_TZ)
    print("    → TRE Jahr zu UTC konvertiert.")

    # JASM (Jahr) → 15min → MWh/Intervall
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

    print("\n[Phase 2/5] Steps 1–4 (Peaks → Fenster → Kandidaten → Ranking) …")
    # Step 1
    df_peaks = find_top_tre_price_periods(YEAR, n_top=N_TOP, fx=(FX if FX is not None else 1.0))
    if df_peaks is None or df_peaks.empty:
        raise SystemExit("FEHLER: Step1 – Topperioden leer.")
    df_peaks.index = _to_utc_index(pd.to_datetime(df_peaks.index), LOCAL_TZ)

    # Peak-Tage bestimmen
    peak_days = sorted(set(df_peaks.index.date))
    if not peak_days:
        raise SystemExit("FEHLER: Keine Peak-Tage ermittelt.")

    # Step 3a: Fenster je Peak-Tag aus JASM (UTC-Index, day match über .date)
    mask_days = pd.Index(df_jasm_15m_mwh.index.date).isin(peak_days)
    df_jasm_days = df_jasm_15m_mwh.loc[mask_days, [APPLIANCE_NAME]].copy()
    windows = compute_shortest_energy_windows(df_jasm_days, col=APPLIANCE_NAME, threshold_pct=THRESHOLD_PCT)

    # Step 3b: Kandidaten
    cand_days = identify_dr_candidate_days(df_peaks, windows)

    # Step 4: Ranking
    ranked = calculate_ranking_metrics_for_days(cand_days, df_peaks, windows)
    if not ranked:
        print("\n[INFO] Keine gerankten Tage gefunden — keine Simulation möglich.")
        return

    print(f"[INFO] {len(ranked)} gerankte Tage → simuliere Top {min(N_DAYS_SIM, len(ranked))} …")
    days_to_sim: List[Dict[str, Any]] = []
    for i, r in enumerate(ranked[:N_DAYS_SIM], start=1):
        d: dt.date = r["date"]
        peaks_day = df_peaks[df_peaks.index.date == d]
        match = peaks_day[np.isclose(peaks_day["price_chf_kwh"], r["max_srl_price_in_window"])]
        if not match.empty:
            ref_ts = pd.to_datetime(match.index[0]).tz_convert("UTC")
            days_to_sim.append({
                "date": d, "rank_step4": i,
                "ref_peak_ts_utc": ref_ts,
                "max_price": r["max_srl_price_in_window"]  # bleibt gleich: Preis_spitze_im_Fenster
            })

    if not days_to_sim:
        print("[INFO] Keine geeigneten Referenz-Peaks gefunden.")
        return

    # ------------------------------------------------------------
    # Phase 3/5: Simulation
    # ------------------------------------------------------------
    print(f"\n[Phase 3/5] Starte Simulation für {len(days_to_sim)} Tag(e), "
          f"{len(PRE_OFFSETS_H)} Offset(s), {len(DURATIONS_H)} Dauer(en) …")

    avg_cycle_power_kw = CYCLE_KWH / CYCLE_H if CYCLE_H > 0 else 0.0

    results: List[Dict[str, Any]] = []

    for day in days_to_sim:
        d = day["date"]
        ref = day["ref_peak_ts_utc"]
        print(f"\n— Tag {d:%Y-%m-%d} (Rank {day['rank_step4']}), Referenz-Peak {ref:%Y-%m-%d %H:%M} @ {day['max_price']:.4f} CHF/kWh —")

        for pre_off in PRE_OFFSETS_H:
            for dur_h in DURATIONS_H:
                start = ref - pd.Timedelta(hours=float(pre_off))
                end   = start + pd.Timedelta(hours=float(dur_h))

                # 1) Roh-Fenster schneiden
                jasm_raw = get_data_for_specific_window(
                    df_jasm_15m_mwh, start, end, f"{APPLIANCE_NAME}_mwh_interval"
                ).rename("jasm_mwh")

                tre_raw = get_data_for_specific_window(
                    df_tre_all, start, end, "tre_price_chf_kwh"
                ).rename("tre_chf_kwh")

                # 2) Align 15-min Slots
                aligned = pd.concat([jasm_raw, tre_raw], axis=1).dropna()

                if aligned.empty:
                    results.append({
                        "event_date": f"{d:%Y-%m-%d}", "rank_step4": day["rank_step4"],
                        "reference_peak_utc": f"{ref:%Y-%m-%d %H:%M}",
                        "event_start_utc": f"{start:%Y-%m-%d %H:%M}",
                        "event_duration_h": float(dur_h), "pre_peak_offset_h": float(pre_off),
                        "avg_tre_price_in_window_chf_kwh": float("nan"),
                        "event_hours_paid_cap": 0.0,
                        "event_kwh_cap": 0.0,
                        "event_max_comp_chf_per_hh": 0.0,
                        "event_max_comp_pct_of_month": 0.0,
                        "error_message": "No common 15-min slots in window",
                    })
                    continue

                # 3) Ab hier nur die ausgerichteten Reihen
                jasm_mwh = aligned["jasm_mwh"]
                tre_prices = aligned["tre_chf_kwh"]

                avg_tre_price = float(tre_prices.mean())

                # Zeit-Cap: min(Eventdauer, 3h, Zyklusdauer)
                event_hours_paid_cap = float(min(float(dur_h), MAX_EVENT_H, CYCLE_H))
                # Energie-Cap für einen Zyklus innerhalb der gezahlten Zeit:
                # max. CYCLE_KWH, aber falls paid_hours < cycle_hours: nur anteilig
                event_kwh_cap = float(min(CYCLE_KWH, avg_cycle_power_kw * event_hours_paid_cap))

                # Monatsbasis ggf. dynamisch über daily_kwh
                if DAILY_KWH_OPT is not None:
                    days_in_month = calendar.monthrange(start.year, start.month)[1]
                    monthly_kwh_basis = DAILY_KWH_OPT * days_in_month
                else:
                    monthly_kwh_basis = MONTHLY_KWH_DEFAULT

                monthly_cost_basis_chf = monthly_kwh_basis * BASE_PRICE_CHF_KWH_COMPENSATION

                # Obergrenze je Haushalt pro Event (in CHF / in % der Monatsbasis)
                event_max_comp_chf_per_hh = float(avg_tre_price * event_kwh_cap)
                event_max_comp_pct_of_month = (event_max_comp_chf_per_hh / monthly_cost_basis_chf * 100.0) \
                                               if monthly_cost_basis_chf > 0 else 0.0

                # Guardrails
                if not np.isfinite(avg_tre_price) or avg_tre_price < 0 or event_kwh_cap <= 1e-12:
                    results.append({
                        "event_date": f"{d:%Y-%m-%d}", "rank_step4": day["rank_step4"],
                        "reference_peak_utc": f"{ref:%Y-%m-%d %H:%M}",
                        "event_start_utc": f"{start:%Y-%m-%d %H:%M}",
                        "event_duration_h": float(dur_h), "pre_peak_offset_h": float(pre_off),
                        "avg_tre_price_in_window_chf_kwh": avg_tre_price,
                        "event_hours_paid_cap": event_hours_paid_cap,
                        "event_kwh_cap": event_kwh_cap,
                        "event_max_comp_chf_per_hh": event_max_comp_chf_per_hh,
                        "event_max_comp_pct_of_month": event_max_comp_pct_of_month,
                        "error_message": "No energy payable (cap) or invalid TRE price",
                    })
                    continue

                # 4) Teilnahme-Iteration (Angebot in % der Monatskosten)
                MAX_ITERS = 50
                DAMP      = 0.5
                EPS_PCT   = 0.01  # %-Punkte

                offer_pct = 0.0          # aktuelles Angebots-% der Monatskosten
                prev_pct  = -1.0
                iters     = 0

                last_raw_particip = 0.0
                last_cap_particip = 0.0
                last_shifted_mwh  = 0.0
                last_tre_value    = 0.0
                last_unit_payout  = 0.0

                # Für die netzweite Energierechnung bleibt jasm_mwh maßgeblich (pot. Last im Fenster)
                while abs(offer_pct - prev_pct) > EPS_PCT and iters < MAX_ITERS:
                    prev_pct = offer_pct
                    iters += 1

                    metrics = calculate_participation_metrics(
                        df_survey_flex_input=df_survey,
                        target_appliance=APPLIANCE_NAME,
                        event_duration_h=float(dur_h),
                        offered_incentive_pct=float(offer_pct),
                    )
                    raw_rate = float(min(max(metrics.get("raw_participation_rate", 0.0), 0.0), 1.0))
                    cap_rate = float(min(raw_rate, MAX_PARTICIPATION_CAP))  # <= 62.9 %

                    shifted_series_mwh = jasm_mwh * cap_rate
                    shifted_sum_mwh    = float(shifted_series_mwh.sum())

                    if shifted_sum_mwh <= 1e-12:
                        tre_value  = 0.0
                        unit_payout = 0.0
                        next_offer  = 0.0
                    else:
                        tre_value  = float((shifted_series_mwh * 1000.0 * tre_prices).sum())
                        base_cost  = shifted_sum_mwh * 1000.0 * BASE_PRICE_CHF_KWH_COMPENSATION
                        next_offer = (tre_value / base_cost) * 100.0 if base_cost > 1e-12 else 0.0
                        unit_payout = tre_value / (shifted_sum_mwh * 1000.0)

                    # Angebots-% deckeln:
                    # - globaler Prozent-Cap (z. B. 62.9 %)
                    # - zusätzlich Event-Cap in % der Monatsbasis (aus Preis*Energiecap)
                    next_offer = max(0.0, min(next_offer, MAX_COMP_PCT, event_max_comp_pct_of_month))

                    # Dämpfung
                    offer_pct = DAMP * prev_pct + (1.0 - DAMP) * next_offer

                    last_raw_particip = raw_rate
                    last_cap_particip = cap_rate
                    last_shifted_mwh  = shifted_sum_mwh
                    last_tre_value    = tre_value
                    last_unit_payout  = unit_payout

                converged = (iters < MAX_ITERS) or (abs(offer_pct - prev_pct) <= EPS_PCT)

                # 5) Pro-Haushalt-Auszahlung für das Event: min(Prozent * Monatskosten, Event-Obergrenze)
                comp_per_hh_chf_theoretical = (offer_pct / 100.0) * monthly_cost_basis_chf
                comp_per_hh_chf_event = float(min(comp_per_hh_chf_theoretical, event_max_comp_chf_per_hh))

                # Ergebnis sammeln
                results.append({
                    "event_date": f"{d:%Y-%m-%d}",
                    "rank_step4": day["rank_step4"],
                    "reference_peak_utc": f"{ref:%Y-%m-%d %H:%M}",
                    "event_start_utc": f"{start:%Y-%m-%d %H:%M}",
                    "event_duration_h": float(dur_h),
                    "pre_peak_offset_h": float(pre_off),

                    "avg_tre_price_in_window_chf_kwh": float(avg_tre_price),

                    # Event-Caps & Herleitung
                    "event_hours_paid_cap": float(event_hours_paid_cap),
                    "event_kwh_cap": float(event_kwh_cap),
                    "event_max_comp_chf_per_hh": float(event_max_comp_chf_per_hh),
                    "event_max_comp_pct_of_month": float(event_max_comp_pct_of_month),

                    # Angebot/Teilnahme (gedeckelt)
                    "konvergierter_komp_prozentsatz": float(min(offer_pct, MAX_COMP_PCT, event_max_comp_pct_of_month)),
                    "rohe_teilnahmequote_vor_cap": float(last_raw_particip),
                    "finale_teilnahmequote": float(last_cap_particip),

                    # Monatsbasis (für Prozentlogik)
                    "kompensations_basis_energie_kwh": float(monthly_kwh_basis),
                    "kompensations_basis_kosten_chf": float(monthly_cost_basis_chf),

                    # Netzweite Ergebnisgrößen
                    "total_verschobene_energie_mwh": float(last_shifted_mwh),
                    "total_tre_wert_chf": float(last_tre_value),
                    "auszahlung_pro_kwh_verschoben_chf": float(last_unit_payout),

                    # Pro Haushalt & Event tatsächlich gezahlt (mit Eventcap)
                    "kompensation_pro_haushalt_pro_event_chf": float(comp_per_hh_chf_event),

                    "iterations_to_converge": int(iters),
                    "converged": bool(converged),
                    "error_message": None,
                })

    # ------------------------------------------------------------
    # Phase 4/5: Ausgabe
    # ------------------------------------------------------------
    print("\n[Phase 4/5] Zusammenfassung …")
    if not results:
        print("Keine Simulationsergebnisse.")
        return

    df_res = pd.DataFrame(results)
    show_cols = [
        "event_date","rank_step4","event_duration_h","pre_peak_offset_h",
        "avg_tre_price_in_window_chf_kwh",
        "event_hours_paid_cap","event_kwh_cap",
        "event_max_comp_chf_per_hh","event_max_comp_pct_of_month",
        "konvergierter_komp_prozentsatz","rohe_teilnahmequote_vor_cap","finale_teilnahmequote",
        "kompensation_pro_haushalt_pro_event_chf",
        "kompensations_basis_energie_kwh","kompensations_basis_kosten_chf",
        "total_verschobene_energie_mwh","total_tre_wert_chf",
        "converged","error_message",
    ]
    show_cols = [c for c in show_cols if c in df_res.columns]
    fmt = {
        "avg_tre_price_in_window_chf_kwh": "{:.4f}".format,
        "event_hours_paid_cap": "{:.2f}".format,
        "event_kwh_cap": "{:.2f}".format,
        "event_max_comp_chf_per_hh": "{:.2f}".format,
        "event_max_comp_pct_of_month": "{:.2f}%".format,
        "konvergierter_komp_prozentsatz": "{:.2f}%".format,
        "rohe_teilnahmequote_vor_cap": "{:.2%}".format,
        "finale_teilnahmequote": "{:.2%}".format,
        "kompensation_pro_haushalt_pro_event_chf": "{:.2f}".format,
        "kompensations_basis_energie_kwh": "{:.2f}".format,
        "kompensations_basis_kosten_chf": "{:.2f}".format,
        "total_verschobene_energie_mwh": "{:.3f}".format,
        "total_tre_wert_chf": "{:.2f}".format,
    }
    print(df_res[show_cols].to_string(index=False, formatters={k:v for k,v in fmt.items() if k in df_res.columns}))

    # ------------------------------------------------------------
    # Phase 5/5: Speichern
    # ------------------------------------------------------------
    if args.save:
        slug = _slugify(APPLIANCE_NAME)
        fx_tag = f"_fx{FX:.2f}" if FX is not None and abs(FX - 1.0) > 1e-9 else ""
        out_name = f"tre05_simulation_results_{slug}_{YEAR}_top{N_TOP}_thr{int(THRESHOLD_PCT)}{fx_tag}.csv"
        out_path = RESULTS_DIR / out_name
        df_res.to_csv(out_path, index=False, sep=";", decimal=".")
        print(f"\n[INFO] Ergebnisse gespeichert: {out_path}")

if __name__ == "__main__":
    main()
