# python -m steps.step06_sozio_technisches_simulationsmodell.flexibility_potential.d_surface_batch
# steps/step06_sozio_technisches_simulationsmodell/flexibility_potential/d_surface_batch.py
from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd

from .a_survey_data_preparer import (
    prepare_survey_flexibility_data,
    APPLIANCES as KNOWN_APPLIANCES,
)
from .b_participation_calculator import calculate_participation_metrics
from .c_flexibility_visualizer import SurfaceParams, generate_3d_flexibility_surface_plot

# Fallback, falls aus den Daten keine Geräte abgeleitet werden können
APPLIANCES_FALLBACK: list[str] = list(KNOWN_APPLIANCES)

def _durations_for_device(df: pd.DataFrame, device: str, max_h: float) -> np.ndarray:
    s = df.loc[df["device"] == device, "survey_max_duration_h"].dropna()
    arr = s[(s > 0) & (s <= max_h)].unique()
    if arr.size == 0:
        # konservativer Fallback
        return np.array([0.5, 1.5, 3.0])
    return np.array(sorted(arr))

def _max_rate_for_device(df: pd.DataFrame, device: str,
                         durations: np.ndarray, incentives: np.ndarray) -> float:
    maxr = 0.0
    for d in durations:
        for inc in incentives:
            m = calculate_participation_metrics(df, device, float(d), float(inc))
            maxr = max(maxr, m["raw_participation_rate"] * 100.0)
    return maxr

def batch_generate_surfaces(
    out_dir: str = "steps/step06_sozio_technisches_simulationsmodell/flexibility_potential/figures",
    max_incentive_pct: float = 50.0,
    incentive_steps: int = 11,
    max_event_duration_h: float = 30.0,
    appliances: list[str] | None = None,
) -> None:
    # Daten aufbereiten (nutzt die robuste ID-/Alias-Logik aus a_survey_data_preparer)
    df = prepare_survey_flexibility_data()
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    # finale Geräteliste bestimmen (nie None)
    if appliances is None:
        devices = df["device"].dropna().unique().tolist()
        appliances_final: list[str] = devices if devices else APPLIANCES_FALLBACK
    else:
        appliances_final = list(appliances)

    incentives = np.linspace(0, max_incentive_pct, incentive_steps)

    # 1) globale Farbskalen-Obergrenze bestimmen
    maxima: list[float] = []
    for a in appliances_final:
        durs = _durations_for_device(df, a, max_event_duration_h)
        maxima.append(_max_rate_for_device(df, a, durs, incentives))
    global_cmax = float(np.ceil(max(maxima or [10.0]) / 5.0) * 5.0)
    global_cmax = max(global_cmax, 10.0)
    print(f"[INFO] Globale Farbskala: 0–{global_cmax:.0f}%")

    # 2) Plots erzeugen (HTML-Dateien)
    for a in appliances_final:
        p = SurfaceParams(
            target_appliance=a,
            incentive_steps=incentive_steps,
            max_incentive_pct_on_plot=max_incentive_pct,
            max_event_duration_h_on_plot=max_event_duration_h,
            color_cmin=0.0,
            color_cmax=global_cmax,
            show=False,
            save_html_path=str(Path(out_dir) / f"flex_surface_{a.replace(' ', '_')}.html"),
        )
        generate_3d_flexibility_surface_plot(df, p)
        print(f"[OK] {a}: {p.save_html_path}")

if __name__ == "__main__":
    batch_generate_surfaces()
