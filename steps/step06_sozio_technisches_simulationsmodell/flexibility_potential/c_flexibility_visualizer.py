#python -m steps.step06_sozio_technisches_simulationsmodell.flexibility_potential.d_surface_batch
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Tuple
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from steps.step06_sozio_technisches_simulationsmodell.flexibility_potential.a_survey_data_preparer import (
    prepare_survey_flexibility_data,
)
from steps.step06_sozio_technisches_simulationsmodell.flexibility_potential.b_participation_calculator import (
    calculate_participation_metrics,
)

@dataclass(frozen=True)
class SurfaceParams:
    target_appliance: str
    max_event_duration_h_on_plot: float = 30.0
    incentive_steps: int = 11          # z.B. 0..100 in 11 Schritten = 0,10,...,100
    max_incentive_pct_on_plot: float = 100.0
    color_cmin: float = 0.0            # % Teilnahme
    color_cmax: float = 100.0          # % Teilnahme
    show: bool = True                  # fig.show()
    save_html_path: str | None = None  # z.B. "figures/surface_<geraet>.html"

def _durations_for_device(df: pd.DataFrame, device: str, max_h: float) -> np.ndarray:
    """
    Ermittelt sinnvolle Dauerstufen aus Q9 für ein bestimmtes Gerät ( >0 und <= max_h ).
    Fallback: feste Stufen aus dem Mapping {1.5, 4.5, 9, 24, 30}.
    """
    if "survey_max_duration_h" not in df.columns:
        return np.array([1.5, 4.5, 9.0, 24.0, 30.0])

    vals = (
        df.loc[df["device"] == device, "survey_max_duration_h"]
        .dropna()
        .astype(float)
        .tolist()
    )
    uniq = sorted({d for d in vals if 0 < d <= max_h})
    if uniq:
        return np.array(uniq, dtype=float)

    # Fallbacks
    fallback = np.array([1.5, 4.5, 9.0, 24.0, 30.0], dtype=float)
    return fallback[fallback <= max_h] if (fallback <= max_h).any() else np.array([1.5])

def compute_surface(
    df_survey_flex: pd.DataFrame,
    params: SurfaceParams,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Berechnet X (Anreiz %), Y (Dauer h), Z (Teilnahme %).
    """
    # X – Anreize in %
    x_incentives = np.linspace(0.0, float(params.max_incentive_pct_on_plot), int(params.incentive_steps))
    # Y – Dauern in h
    y_durations = _durations_for_device(df_survey_flex, params.target_appliance, float(params.max_event_duration_h_on_plot))
    if y_durations.size == 0:
        raise ValueError("Keine Dauerstufen verfügbar.")

    X, Y = np.meshgrid(x_incentives, y_durations)
    Z = np.zeros_like(X, dtype=float)

    # Teilnahmequote für jedes (duration, incentive)-Paar
    for i, d in enumerate(y_durations):
        for j, p in enumerate(x_incentives):
            m = calculate_participation_metrics(
                df_survey_flex_input=df_survey_flex,
                target_appliance=params.target_appliance,
                event_duration_h=float(d),
                offered_incentive_pct=float(p),
            )
            Z[i, j] = float(m["raw_participation_rate"]) * 100.0  # in %

    return X, Y, Z

def generate_3d_flexibility_surface_plot(
    df_survey_flex: pd.DataFrame,
    params: SurfaceParams,
) -> go.Figure:
    """
    Baut den 3D-Surface-Plot für ein Gerät anhand der Umfragedaten.
    """
    X, Y, Z = compute_surface(df_survey_flex, params)

    fig = go.Figure(
        data=[
            go.Surface(
                z=Z,
                x=X,
                y=Y,
                colorscale="Viridis",
                colorbar_title="Teilnahme (%)",
                name=params.target_appliance,
                contours={"z": {"show": True, "highlightcolor": "limegreen", "project": {"z": True}}},
                cmin=float(params.color_cmin),
                cmax=float(params.color_cmax),
            )
        ]
    )
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

if __name__ == "__main__":
    # Minimaler Quicktest
    df = prepare_survey_flexibility_data()
    if df.empty:
        print("[WARN] Keine Survey-Flexibilitätsdaten gefunden.")
    else:
        p = SurfaceParams(
            target_appliance="Geschirrspüler",
            incentive_steps=11,
            max_incentive_pct_on_plot=50.0,
            max_event_duration_h_on_plot=30.0,
            color_cmax=100.0,
            show=False,
            save_html_path="flex_surface_Geschirrspueler.html",
        )
        generate_3d_flexibility_surface_plot(df, p)
        print("[OK] Plot geschrieben: flex_surface_Geschirrspueler.html")
