from __future__ import annotations

import re
import datetime as dt
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd


# ---------------------------------------------------------------------
# Pfade & Utilities
# ---------------------------------------------------------------------
def _project_root_from_file() -> Path:
    here = Path(__file__).resolve()
    for p in here.parents:
        if p.name == "steps":
            return p.parent
    return here.parents[4] if len(here.parents) >= 5 else Path.cwd()

PROJECT_ROOT = _project_root_from_file()
BASE_DIR = PROJECT_ROOT / "data" / "market" / "processed" / "dr_windows"

def _slugify(name: str) -> str:
    s = name.lower()
    repl = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
            "é": "e", "è": "e", "ê": "e", "à": "a", "á": "a", "ô": "o", "î": "i"}
    for k, v in repl.items():
        s = s.replace(k, v)
    return "".join(ch if ch.isalnum() else "_" for ch in s).strip("_")

def _fx_tag(fx: Optional[float]) -> str:
    return f"_fx{fx:.2f}" if fx is not None and abs(fx - 1.0) > 1e-9 else ""

def _err_with_available(pattern_desc: str, available: Iterable[Path]) -> FileNotFoundError:
    avail = ", ".join(sorted(p.name for p in available))
    return FileNotFoundError(f"Keine Datei passend zu {pattern_desc} gefunden.\nVorhanden: [{avail}]")

def _parse_time(val: str) -> dt.time:
    val = str(val).strip()
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return dt.datetime.strptime(val, fmt).time()
        except Exception:
            pass
    raise ValueError(f"Kann Uhrzeit nicht parsen: {val!r}")

def _resolve_col(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    return None


# ---------------------------------------------------------------------
# TOP-PERIODEN (tre01)
# ---------------------------------------------------------------------
def _fname_top_periods(year: int, fx: Optional[float]) -> str:
    return f"tre_top_periods_{year}{_fx_tag(fx)}.csv"

def list_top_periods_files(year: int) -> List[Path]:
    return sorted(BASE_DIR.glob(f"tre_top_periods_{year}*.csv"))

# Backward-compat name (frühere Skizze hatte unglücklichen Namen)
def list_tre_windows_files(year: int) -> List[Path]:
    return list_top_periods_files(year)

def load_tre_top_periods(year: int, fx: Optional[float] = None) -> pd.DataFrame:
    """
    Lädt tre01-Output: 'tre_top_periods_<YEAR>[ _fx<FX> ].csv'
    Rückgabe: DataFrame mit Index=timestamp.
    """
    path = BASE_DIR / _fname_top_periods(year, fx)
    if not path.exists():
        # Fallback: wenn keine exakte FX-Variante existiert, liste alle zur Diagnose
        raise _err_with_available(f"'tre_top_periods_{year}{_fx_tag(fx)}.csv'", list_top_periods_files(year))
    df = pd.read_csv(path, parse_dates=["timestamp"])
    return df.set_index("timestamp").sort_index()


# ---------------------------------------------------------------------
# JASM-Teilmatrix (tre02) — z.B. tre_jasm_geschirrspueler_2024_top24[_fx0.97].csv
# ---------------------------------------------------------------------
def list_jasm_files(year: int, appliance: Optional[str] = None) -> List[Path]:
    if appliance:
        slug = _slugify(appliance)
        pat = f"tre_jasm_{slug}_{year}_top*.csv"
    else:
        pat = f"tre_jasm_*_{year}_top*.csv"
    return sorted(BASE_DIR.glob(pat))

def load_tre_jasm_timeseries(
    year: int,
    appliance: str,
    top: Optional[int] = None,
    fx: Optional[float] = None,
) -> pd.DataFrame:
    """
    Lädt tre02-Output (Timeseries für ausgewählte Tage):
      tre_jasm_<slug>_<YEAR>_top<TOP>[ _fx<FX> ].csv
    Rückgabe: DataFrame mit Index=timestamp und Spalte=<appliance-slug oder -name>.
    """
    slug = _slugify(appliance)
    # exakter Name, falls top (und ggf. fx) bekannt:
    if top is not None:
        fname = f"tre_jasm_{slug}_{year}_top{int(top)}{_fx_tag(fx)}.csv"
        path = BASE_DIR / fname
        if path.exists():
            df = pd.read_csv(path, parse_dates=["timestamp"])
            return df.set_index("timestamp").sort_index()

    # sonst: versuche best match (höchstes TOP, ggf. passender FX)
    candidates = list_jasm_files(year, appliance)
    if fx is not None:
        candidates = [p for p in candidates if f"_fx{fx:.2f}" in p.stem]
    if not candidates:
        raise _err_with_available(f"tre_jasm_{slug}_{year}_top*{_fx_tag(fx)}.csv", list_jasm_files(year, appliance))

    # wähle mit größtem TOP
    def _top_from_name(p: Path) -> int:
        m = re.search(r"_top(\d+)", p.stem)
        return int(m.group(1)) if m else -1

    best = max(candidates, key=_top_from_name)
    df = pd.read_csv(best, parse_dates=["timestamp"])
    return df.set_index("timestamp").sort_index()


# ---------------------------------------------------------------------
# Fenster (tre03) — tre_windows_<slug>_<YEAR>_top<TOP>_thr<THR>[_fx<FX>].csv
# DR-Tage (tre03) — tre_dr_days_<slug>_<YEAR>_top<TOP>_thr<THR>[_fx<FX>].csv
# ---------------------------------------------------------------------
def list_windows_files(year: int, appliance: Optional[str] = None) -> List[Path]:
    if appliance:
        slug = _slugify(appliance)
        pat = f"tre_windows_{slug}_{year}_top*_thr*.csv"
    else:
        pat = f"tre_windows_*_{year}_top*_thr*.csv"
    return sorted(BASE_DIR.glob(pat))



def list_dr_days_files(year: int, appliance: Optional[str] = None) -> List[Path]:
    if appliance:
        slug = _slugify(appliance)
        pat = f"tre_dr_days_{slug}_{year}_top*_thr*.csv"
    else:
        pat = f"tre_dr_days_*_{year}_top*_thr*.csv"
    return sorted(BASE_DIR.glob(pat))

def _fname_windows(year: int, appliance: str, top: int, thr: int, fx: Optional[float]) -> str:
    slug = _slugify(appliance)
    return f"tre_windows_{slug}_{year}_top{int(top)}_thr{int(thr)}{_fx_tag(fx)}.csv"

def _fname_dr_days(year: int, appliance: str, top: int, thr: int, fx: Optional[float]) -> str:
    slug = _slugify(appliance)
    return f"tre_dr_days_{slug}_{year}_top{int(top)}_thr{int(thr)}{_fx_tag(fx)}.csv"

def load_tre_windows(
    year: int,
    appliance: str,
    top: int,
    thr: int,
    fx: Optional[float] = None,
    *,
    as_dict: bool = False,
) -> pd.DataFrame | Dict[dt.date, Tuple[dt.time, dt.time, float, float]]:
    """
    Lädt tre03-Fenster:
      Spalten-Varianten werden robust erkannt:
        - date / day / day_date
        - start / appliance_window_start / window_start
        - end / appliance_window_end / window_end
        - duration_h / appliance_window_duration_h / window_duration_h
        - energy_mwh / appliance_window_energy_sum / energy_sum_mwh
        - energy_pct / appliance_window_energy_pct / window_energy_pct
    Rückgabe: DataFrame (date als datetime64[ns], start/end als string) oder dict[date] = (start_time, end_time, sum_mwh, pct)
    """
    fname = _fname_windows(year, appliance, top, thr, fx)
    path = BASE_DIR / fname
    if not path.exists():
        raise _err_with_available(fname, list_windows_files(year, appliance))

    df = pd.read_csv(path)
    date_col = _resolve_col(df, ["date", "day", "day_date"])
    start_col = _resolve_col(df, ["start", "appliance_window_start", "window_start", "start_time"])
    end_col   = _resolve_col(df, ["end", "appliance_window_end", "window_end", "end_time"])
    dur_col   = _resolve_col(df, ["duration_h", "appliance_window_duration_h", "window_duration_h"])
    sum_col   = _resolve_col(df, ["energy_mwh", "appliance_window_energy_sum", "energy_sum_mwh"])
    pct_col   = _resolve_col(df, ["energy_pct", "appliance_window_energy_pct", "window_energy_pct"])

    if not date_col or not start_col or not end_col:
        raise ValueError(f"Erwarte mindestens date/start/end in {path.name}, gefunden: {list(df.columns)}")

    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col]).dt.date

    if as_dict:
        out: Dict[dt.date, Tuple[dt.time, dt.time, float, float]] = {}
        for _, r in df.iterrows():
            d = r[date_col]
            st = _parse_time(r[start_col])
            en = _parse_time(r[end_col])
            sm = float(r[sum_col]) if sum_col else float("nan")
            pc = float(r[pct_col]) if pct_col else float("nan")
            out[d] = (st, en, sm, pc)
        return out

    # Für DataFrame-Variante Start/Ende als HH:MM belassen, Date als datetime64[ns]
    df[date_col] = pd.to_datetime(df[date_col])
    return df[[c for c in [date_col, start_col, end_col, dur_col, sum_col, pct_col] if c]]


def load_tre_dr_days(
    year: int,
    appliance: str,
    top: int,
    thr: int,
    fx: Optional[float] = None,
) -> List[dt.date]:
    """
    Lädt tre03-DR-Tage (Liste von Datumstagen).
    """
    fname = _fname_dr_days(year, appliance, top, thr, fx)
    path = BASE_DIR / fname
    if not path.exists():
        raise _err_with_available(fname, list_dr_days_files(year, appliance))
    df = pd.read_csv(path)
    date_col = _resolve_col(df, ["date", "day", "day_date"])
    if not date_col:
        # Falls die Datei nur eine Einspaltige Liste hat
        date_col = df.columns[0]
    return [ts.date() for ts in pd.to_datetime(df[date_col])]


# ---------------------------------------------------------------------
# Ranking (tre04) — tre_ranked_days_<slug>_<YEAR>_top<TOP>_thr<THR>[_fx<FX>].csv
# (robust auch gegen alte Benennung '..._thr70_.csv')
# ---------------------------------------------------------------------
def list_ranked_days_files(year: int, appliance: Optional[str] = None) -> List[Path]:
    if appliance:
        slug = _slugify(appliance)
        pat = f"tre_ranked_days_{slug}_{year}_top*_thr*.csv"
    else:
        pat = f"tre_ranked_days_*_{year}_top*_thr*.csv"
    return sorted(BASE_DIR.glob(pat))

def _fname_ranked(year: int, appliance: str, top: int, thr: int, fx: Optional[float]) -> str:
    slug = _slugify(appliance)
    if fx is None:
        # neue Benennung (ohne hässliches '_')
        return f"tre_ranked_days_{slug}_{year}_top{int(top)}_thr{int(thr)}.csv"
    return f"tre_ranked_days_{slug}_{year}_top{int(top)}_thr{int(thr)}_fx{fx:.2f}.csv"

def load_tre_ranked_days(
    year: int,
    appliance: str,
    top: int,
    thr: int,
    fx: Optional[float] = None,
) -> pd.DataFrame:
    """
    Lädt tre04-Ranking als DataFrame. 'date' wird zu datetime64[ns] geparst.
    Unterstützt sowohl neue (…_thr70.csv) als auch alte (…_thr70_.csv) Benennung.
    """
    # 1) Neuer Name
    path = BASE_DIR / _fname_ranked(year, appliance, top, thr, fx)
    if not path.exists() and fx is None:
        # 2) Alter Bug-Name: ..._thr70_.csv
        slug = _slugify(appliance)
        legacy = BASE_DIR / f"tre_ranked_days_{slug}_{year}_top{int(top)}_thr{int(thr)}_.csv"
        if legacy.exists():
            path = legacy

    if not path.exists():
        raise _err_with_available(path.name, list_ranked_days_files(year, appliance))

    df = pd.read_csv(path)
    # 'date' robust parsen
    date_col = _resolve_col(df, ["date", "day", "day_date"])
    if date_col:
        df[date_col] = pd.to_datetime(df[date_col])
    return df