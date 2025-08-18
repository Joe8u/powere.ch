from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Sequence
import numpy as np
import pandas as pd

from .a_survey_data_preparer import prepare_survey_flexibility_data
from .c_flexibility_visualizer import (
    SurfaceParams,
    compute_surface,
    generate_3d_flexibility_surface_plot,
)

def _slug(name: str) -> str:
    repl = {"ä":"ae","ö":"oe","ü":"ue","Ä":"Ae","Ö":"Oe","Ü":"Ue","ß":"ss","/":"-","\\":"-"}
    s = "".join(repl.get(ch, ch) for ch in str(name))
    s = s.replace(" ", "_")
    return "".join(ch for ch in s if ch.isalnum() or ch in "._-")

def _global_cmax(
    df: pd.DataFrame,
    appliances: Sequence[str],
    incentive_steps: int,
    max_incentive_pct: float,
    max_event_duration_h: float,
) -> float:
    """Maximale Teilnahme (%) über alle Geräte, als Basis für eine einheitliche Farbskala."""
    zmax = 0.0
    for a in appliances:
        X, Y, Z = compute_surface(
            df,
            SurfaceParams(
                target_appliance=a,
                incentive_steps=int(incentive_steps),
                max_incentive_pct_on_plot=float(max_incentive_pct),
                max_event_duration_h_on_plot=float(max_event_duration_h),
                show=False,
            ),
        )
        # Z enthält Teilnahme in %, NaNs ignorieren
        cur = float(np.nanmax(Z)) if Z.size else 0.0
        zmax = max(zmax, cur)
    # Auf 5er-Schritte runden, Mindestwert 10 %
    if zmax <= 0:
        return 10.0
    zmax = float(np.ceil(zmax / 5.0) * 5.0)
    return max(zmax, 10.0)

def generate_all_surfaces(
    out_dir: str | Path = "steps/step06_sozio_technisches_simulationsmodell/flexibility_potential/figures",
    appliances: Sequence[str] | None = None,
    incentive_steps: int = 11,
    max_incentive_pct: float = 50.0,
    max_event_duration_h: float = 30.0,
) -> list[Path]:
    df = prepare_survey_flexibility_data()
    if df.empty:
        raise RuntimeError("Keine Survey-Flexibilitätsdaten verfügbar.")

    if appliances is None:
        appliances = [str(x) for x in sorted(df["device"].dropna().unique())]

    outp = Path(out_dir)
    outp.mkdir(parents=True, exist_ok=True)

    cmax = _global_cmax(
        df,
        appliances,
        incentive_steps=incentive_steps,
        max_incentive_pct=max_incentive_pct,
        max_event_duration_h=max_event_duration_h,
    )
    print(f"[INFO] Globale Farbskala: 0 .. {cmax:.0f} %")

    written: list[Path] = []
    for a in appliances:
        save_path = outp / f"flex_surface_{_slug(a)}.html"
        params = SurfaceParams(
            target_appliance=a,
            incentive_steps=int(incentive_steps),
            max_incentive_pct_on_plot=float(max_incentive_pct),
            max_event_duration_h_on_plot=float(max_event_duration_h),
            color_cmin=0.0,
            color_cmax=float(cmax),
            show=False,
            save_html_path=str(save_path),
        )
        generate_3d_flexibility_surface_plot(df, params)
        written.append(save_path)
        print(f"[OK] Geschrieben: {save_path}")
    return written

def main() -> None:
    ap = argparse.ArgumentParser(description="Generate 3D surface plots for all appliances.")
    ap.add_argument("--out-dir", default="steps/step06_sozio_technisches_simulationsmodell/flexibility_potential/figures")
    ap.add_argument("--steps", type=int, default=11, help="Anzahl Anreiz-Stufen (inkl. 0 %).")
    ap.add_argument("--max-incentive", type=float, default=50.0, help="Max. Anreiz in % auf der X-Achse.")
    ap.add_argument("--max-duration", type=float, default=30.0, help="Max. Event-Dauer (h) auf der Y-Achse.")
    ap.add_argument("--only", nargs="*", help="Optional: nur diese Geräte rendern (exakte Labels).")
    args = ap.parse_args()

    generate_all_surfaces(
        out_dir=args.out_dir,
        appliances=args.only,
        incentive_steps=args.steps,
        max_incentive_pct=args.max_incentive,
        max_event_duration_h=args.max_duration,
    )

if __name__ == "__main__":
    main()
