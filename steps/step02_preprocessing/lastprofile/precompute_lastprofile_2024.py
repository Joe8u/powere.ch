#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Precompute 2024 last profiles (15-min) by interpolating between 2015 and 2035.
Input (raw):        data/lastprofile/raw/Swiss_load_curves_2015_2035_2050.csv
Output (processed): data/lastprofile/processed/2024/2024-01.csv ... 2024-12.csv

Maschinenunabhängig: alle Pfade relativ zum Repo-Root (aus __file__ ermittelt).
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
import calendar
import pandas as pd


def find_repo_root(start: Path) -> Path:
    """
    Geht nach oben, bis ein plausibler Repo-Root gefunden wird ('.git' oder typische Ordner).
    Fallback: drei Ebenen hoch (…/processing/lastprofile/jobs -> Repo-Root).
    """
    for p in [start, *start.parents]:
        if (p / ".git").exists() or ((p / "apps").is_dir() and (p / "data").is_dir()):
            return p
    # erwartete Tiefe: jobs -> lastprofile -> processing -> REPO
    return start.parents[2]


def month_expected_rows(year: int, month: int) -> int:
    days = calendar.monthrange(year, month)[1]
    return days * 96  # 96 * 15min-Slots pro Tag


def main() -> int:
    ap = argparse.ArgumentParser(description="Precompute 2024 monthly lastprofile CSVs (processed).")
    ap.add_argument("--year", type=int, default=2024, help="Zieljahr (Default: 2024)")
    ap.add_argument("--infile", type=str, default="data/lastprofile/raw/Swiss_load_curves_2015_2035_2050.csv",
                    help="Pfad (relativ zum Repo) zur Rohdatei")
    ap.add_argument("--outdir", type=str, default=None,
                    help="Ausgabeordner (relativ zum Repo), Default: data/lastprofile/processed/<year>/")
    args = ap.parse_args()

    script_path = Path(__file__).resolve()
    repo_root = find_repo_root(script_path.parent)

    year = args.year
    in_rel = Path(args.infile)
    out_rel = Path(args.outdir) if args.outdir else Path("data/lastprofile/processed") / str(year)

    in_csv = (repo_root / in_rel).resolve()
    out_dir = (repo_root / out_rel).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # Interpolationsfaktor zwischen 2015 und 2035, um year zu erzeugen
    f = (year - 2015) / (2035 - 2015)

    print(f"[INFO] Repo-Root:   {repo_root}")
    print(f"[INFO] Input CSV:   {in_csv}")
    print(f"[INFO] Output dir:  {out_dir}")
    print(f"[INFO] Interp-Faktor f={f:.4f} (zwischen 2015 und 2035)")

    if not in_csv.exists():
        print(f"[ERROR] Rohdatendatei nicht gefunden: {in_csv}")
        return 1

    # --- 1) Raw einlesen -----------------------------------------------------
    try:
        df_raw = pd.read_csv(
            in_csv,
            sep=";",
            dtype={
                "Year": int,
                "Month": int,
                "Day type": str,
                "Time": str,
                "Appliances": str,
                "Power (MW)": float,
            },
            encoding="utf-8",
        )
    except Exception as e:
        print(f"[ERROR] Konnte Rohdaten nicht lesen: {e}")
        return 1

    # Spaltennamen normalisieren
    df_raw.columns = (
        df_raw.columns
        .str.strip().str.lower()
        .str.replace(" ", "_")
    )
    # Erwartete Spalten prüfen (minimal)
    expected_cols = {"year", "month", "day_type", "time", "appliances", "power_(mw)"}
    missing = expected_cols - set(df_raw.columns)
    if missing:
        print(f"[ERROR] Fehlende Spalten in Rohdaten: {missing}")
        return 1

    # --- 2) Pivot-Tabellen für 2015/2035 ------------------------------------
    def pivot_year(df: pd.DataFrame, y: int) -> pd.DataFrame:
        df_y = df[df["year"] == y]
        if df_y.empty:
            raise ValueError(f"Keine Daten für Jahr {y} in Rohdatei gefunden.")
        df_y = (
            df_y
            .groupby(["month", "day_type", "time", "appliances"], as_index=False)["power_(mw)"].mean()
        )
        df_y["power_mw_val"] = df_y["power_(mw)"]
        out = (
            df_y
            .pivot(index=["month", "day_type", "time"], columns="appliances", values="power_mw_val")
            .sort_index()
        )
        return out

    print("[INFO] Erzeuge Pivot 2015/2035 …")
    try:
        pivot15 = pivot_year(df_raw, 2015)
        pivot35 = pivot_year(df_raw, 2035)
    except Exception as e:
        print(f"[ERROR] Pivot fehlgeschlagen: {e}")
        return 1

    # --- 3) Interpolation ----------------------------------------------------
    print(f"[INFO] Interpoliere Jahr {year} …")
    pivotY = (1 - f) * pivot15 + f * pivot35

    # --- 4) Kalender (15-min, naive Zeit) -----------------------------------
    print(f"[INFO] Erzeuge 15-min Kalender für {year} …")
    rng = pd.date_range(f"{year}-01-01", f"{year}-12-31 23:45:00", freq="15min")  # naive Zeit
    df_cal = pd.DataFrame({"timestamp": rng})
    df_cal["month"] = df_cal["timestamp"].dt.month
    df_cal["day_type"] = df_cal["timestamp"].dt.weekday.map(lambda d: "weekday" if d < 5 else "weekend")
    # Wichtig: wir mappen 15-min Slots auf die Stunde der Rohdaten
    df_cal["time"] = df_cal["timestamp"].dt.strftime("%H:00:00")

    # --- 5) Merge & Gruppierung ---------------------------------------------
    print("[INFO] Merge Kalender mit interpolierten Werten …")
    df_merged = (
        df_cal
        .merge(pivotY.reset_index(), on=["month", "day_type", "time"], how="left")
        .drop(columns=["month", "day_type", "time"])
    )

    print("[INFO] Summiere Appliances in Survey-Kategorien …")
    group_map = {
        "Geschirrspüler":                      ["Dishwasher"],
        "Backofen und Herd":                   ["Cooking"],
        "Fernseher und Entertainment-Systeme": ["TV", "STB", "DVB", "Music"],
        "Bürogeräte":                          ["Computer"],
        "Waschmaschine":                       ["Washing machine"],
    }
    df_grouped = pd.DataFrame({"timestamp": df_merged["timestamp"]})
    for cat, cols in group_map.items():
        present = [c for c in cols if c in df_merged.columns]
        if not present:
            print(f"[WARN] Keine der Spalten {cols} für Kategorie '{cat}' gefunden.")
            df_grouped[cat] = 0.0
        else:
            df_grouped[cat] = df_merged[present].sum(axis=1)

    # --- 6) Split & Write ----------------------------------------------------
    print("[INFO] Schreibe Monats-CSV-Dateien …")
    if not pd.api.types.is_datetime64_any_dtype(df_grouped["timestamp"]):
        df_grouped["timestamp"] = pd.to_datetime(df_grouped["timestamp"])

    written = []
    for m in range(1, 13):
        df_month = df_grouped[df_grouped["timestamp"].dt.month == m].copy()
        df_month.sort_values("timestamp", inplace=True)
        outpath = out_dir / f"{year}-{m:02d}.csv"
        df_month.to_csv(outpath, index=False)
        exp = month_expected_rows(year, m)
        ok = "OK" if len(df_month) == exp else f"CHECK rows={len(df_month)} expected={exp}"
        print(f"[INFO] Wrote {outpath} ({ok})")
        written.append(outpath)

    print(f"\n[INFO] Fertig. Geschriebene Dateien: {len(written)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())