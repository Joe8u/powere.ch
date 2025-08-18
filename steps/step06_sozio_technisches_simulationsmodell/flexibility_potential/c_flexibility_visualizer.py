# steps/step06_sozio_technisches_simulationsmodell/flexibility_potential/c_flexibility_visualizer.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from .b_participation_calculator import calculate_participation_metrics

@dataclass
class SurfaceParams:
    target_appliance: str
    incentive_steps: int = 11
    max_incentive_pct_on_plot: float = 50.0
    max_event_duration_h_on_plot: float = 30.0
    color_cmin: float = 0.0
    color_cmax: float = 100.0
    show: bool = False
    save_html_path: Optional[str] = None
    debug: bool = False  # print Z stats

def _device_durations(df: pd.DataFrame, device: str, max_h: float) -> np.ndarray:
    s = df.loc[df["device"] == device, "survey_max_duration_h"].dropna()
    arr = s[(s > 0) & (s <= max_h)].unique()
    if arr.size == 0:
        return np.array([0.5, 1.5, 3.0])
    return np.array(sorted(arr))

def generate_3d_flexibility_surface_plot(df_survey_flex: pd.DataFrame, params: SurfaceParams):
    incentives = np.linspace(0.0, float(params.max_incentive_pct_on_plot), int(params.incentive_steps))
    durations = _device_durations(df_survey_flex, params.target_appliance, float(params.max_event_duration_h_on_plot))
    if durations.size == 0:
        print(f"[WARN] Keine Dauern für {params.target_appliance} gefunden — skip.")
        return None

    Z = np.zeros((len(durations), len(incentives)), dtype=float)
    for i, d in enumerate(durations):
        for j, inc in enumerate(incentives):
            m = calculate_participation_metrics(
                df_survey_flex_input=df_survey_flex,
                target_appliance=params.target_appliance,
                event_duration_h=float(d),
                offered_incentive_pct=float(inc),
            )
            Z[i, j] = m["raw_participation_rate"] * 100.0

    zmin = float(np.nanmin(Z)) if Z.size else 0.0
    zmax = float(np.nanmax(Z)) if Z.size else 0.0
    if params.debug:
        print(f"[DEBUG] {params.target_appliance}: durations={durations.tolist()} incentives={incentives.tolist()} Zmin/Zmax={zmin:.2f}/{zmax:.2f}")

    fig = go.Figure(data=[
        go.Surface(
            z=Z,
            x=incentives,
            y=durations,
            colorscale="Viridis",
            colorbar_title="Teilnahme (%)",
            contours={"z": {"show": True, "project": {"z": True}}},
            cmin=float(params.color_cmin),
            cmax=float(params.color_cmax),
        )
    ])
    fig.update_layout(
        title=f"Flexibilitätspotenzial: {params.target_appliance}<br>Modellierte Teilnahmequote (Umfrage-basiert, %)",
        scene=dict(
            xaxis_title="Anreiz (Kompensation in %)",
            yaxis_title="Event-Dauer (Stunden, aus Q9)",
            zaxis_title="Teilnahmequote (%)",
            zaxis=dict(range=[float(params.color_cmin), float(params.color_cmax)]),
            camera=dict(eye=dict(x=-1.8, y=1.8, z=1.5)),
            aspectmode="cube",
        ),
        margin=dict(l=10, r=10, b=10, t=80),
    )

    if params.save_html_path:
        fig.write_html(params.save_html_path, include_plotlyjs="cdn")
    if params.show:
        fig.show()
    return fig