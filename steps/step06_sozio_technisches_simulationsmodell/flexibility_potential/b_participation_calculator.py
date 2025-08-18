from __future__ import annotations

from typing import Dict, Any, Iterable
from dataclasses import dataclass
import pandas as pd
import numpy as np

# interner Import: nutzt den bereits migrierten Preparer
from steps.step06_sozio_technisches_simulationsmodell.flexibility_potential.a_survey_data_preparer import (
    prepare_survey_flexibility_data,
)



@dataclass(frozen=True)
class ParticipationInput:
    target_appliance: str
    event_duration_h: float
    offered_incentive_pct: float

def calculate_participation_metrics(
    df_survey_flex_input: pd.DataFrame,
    target_appliance: str,
    event_duration_h: float,
    offered_incentive_pct: float,
) -> Dict[str, Any]:
    """
    Berechnet die rohe Teilnahmequote für ein Gerät / eine Eventdauer / einen Anreiz.

    Erwartete df-Spalten (von prepare_survey_flexibility_data):
      - respondent_id (str)
      - device (str)
      - survey_max_duration_h (float | NaN)
      - survey_incentive_choice ('yes_fixed' | 'yes_conditional' | 'no' | 'unknown_*')
      - survey_incentive_pct_required (float | NaN) — bei yes_fixed = 0.0
    """
    if df_survey_flex_input is None or df_survey_flex_input.empty:
        return {
            "target_appliance": target_appliance,
            "event_duration_h": event_duration_h,
            "offered_incentive_pct": offered_incentive_pct,
            "base_population": 0,
            "num_participants": 0,
            "raw_participation_rate": 0.0,
        }

    # nur das Zielgerät
    df_dev = df_survey_flex_input[df_survey_flex_input["device"] == target_appliance].copy()
    base_population = int(df_dev["respondent_id"].nunique()) if not df_dev.empty else 0
    if base_population == 0:
        return {
            "target_appliance": target_appliance,
            "event_duration_h": event_duration_h,
            "offered_incentive_pct": offered_incentive_pct,
            "base_population": 0,
            "num_participants": 0,
            "raw_participation_rate": 0.0,
        }

    participants: set[str] = set()

    for _, row in df_dev.iterrows():
        survey_max_duration = row.get("survey_max_duration_h", np.nan)
        incentive_choice = row.get("survey_incentive_choice", "unknown_choice")
        pct_required = row.get("survey_incentive_pct_required", np.nan)

        # Dauer-Bedingung (Q9)
        duration_met = False
        if not pd.isna(survey_max_duration):
            # "Nein, auf keinen Fall" ist 0.0 -> nie ausreichend für Events > 0
            if survey_max_duration == 0.0 and event_duration_h > 0:
                duration_met = False
            else:
                duration_met = (survey_max_duration >= event_duration_h)

        # Anreiz-Bedingung (Q10)
        incentive_met = False
        if incentive_choice == "yes_fixed":
            incentive_met = True
        elif incentive_choice == "yes_conditional":
            if not pd.isna(pct_required) and float(pct_required) <= float(offered_incentive_pct):
                incentive_met = True
        # 'no' oder 'unknown_*' -> bleibt False

        if duration_met and incentive_met:
            rid = str(row.get("respondent_id", ""))
            if rid:
                participants.add(rid)

    num_participants = len(participants)
    raw_rate = (num_participants / base_population) if base_population > 0 else 0.0

    return {
        "target_appliance": target_appliance,
        "event_duration_h": float(event_duration_h),
        "offered_incentive_pct": float(offered_incentive_pct),
        "base_population": int(base_population),
        "num_participants": int(num_participants),
        "raw_participation_rate": float(raw_rate),
    }

def participation_grid(
    df_survey_flex_input: pd.DataFrame,
    target_appliance: str,
    durations_h: Iterable[float],
    incentives_pct: Iterable[float],
) -> pd.DataFrame:
    """Bequeme Rasterauswertung über mehrere Dauern/Anreize."""
    rows: list[Dict[str, Any]] = []
    for d in durations_h:
        for p in incentives_pct:
            rows.append(
                calculate_participation_metrics(
                    df_survey_flex_input=df_survey_flex_input,
                    target_appliance=target_appliance,
                    event_duration_h=float(d),
                    offered_incentive_pct=float(p),
                )
            )
    return pd.DataFrame(rows)

if __name__ == "__main__":
    # Mini-Quicktest
    df = prepare_survey_flexibility_data()
    if df.empty:
        print("[WARN] Keine Survey-Flexibilitätsdaten.")
    else:
        demo = calculate_participation_metrics(
            df, "Geschirrspüler", event_duration_h=1.5, offered_incentive_pct=10.0
        )
        print("Demo:", demo)
        grid = participation_grid(df, "Geschirrspüler", durations_h=[1.5,4.5,9.0], incentives_pct=[0,10,20,30])
        print(grid.head())
