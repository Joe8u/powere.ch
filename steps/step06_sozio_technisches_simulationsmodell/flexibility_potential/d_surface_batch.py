# steps/step06_sozio_technisches_simulationsmodell/flexibility_potential/d_surface_batch.py
#python -m steps.step06_sozio_technisches_simulationsmodell.flexibility_potential.d_surface_batch
# steps/step06_sozio_technisches_simulationsmodell/flexibility_potential/a_survey_data_preparer.py
from __future__ import annotations

import unicodedata
import re
from typing import Optional, Tuple
import numpy as np
import pandas as pd

# Step-4 Dataloader
from steps.step04_dataloaders.dataloaders.survey import load_nonuse, load_incentives


# -------------------- Helfer: Normalisierung --------------------
def _strip_accents(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in s if not unicodedata.combining(ch))

def _norm_dev_key(s: str) -> str:
    if s is None:
        return ""
    s = _strip_accents(str(s)).lower().strip()
    s = s.replace("&", "und")
    s = re.sub(r"[--–—_/]+", " ", s)   # Bindestriche/Trenner vereinheitlichen
    s = re.sub(r"\s+", " ", s)
    return s

def _find_id_col(df: pd.DataFrame) -> str | None:
    """Finde die ID-Spalte robust (respondent_id / respondent / id / erste Spalte)."""
    if df is None or df.empty:
        return None
    df.columns = [str(c).strip() for c in df.columns]
    for c in df.columns:
        cn = str(c).strip().lower()
        if cn in {"respondent_id", "respondentid", "id"}:
            return c
        if "respondent" in cn or re.search(r"\bid\b", cn):
            return c
    return df.columns[0] if len(df.columns) > 0 else None

def _ensure_respondent_id(df: pd.DataFrame) -> pd.DataFrame:
    """Benennt die gefundene ID-Spalte nach 'respondent_id' und säubert Werte."""
    if df is None or df.empty:
        return df
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    id_col = _find_id_col(df)
    if id_col and id_col != "respondent_id":
        df = df.rename(columns={id_col: "respondent_id"})
    if "respondent_id" in df.columns:
        df["respondent_id"] = (
            df["respondent_id"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
        )
    return df


# -------------------- Gerätekonventionen & Aliase --------------------
APPLIANCE_ALIASES: dict[str, str] = {
    _norm_dev_key("Geschirrspüler"): "Geschirrspüler",
    _norm_dev_key("Backofen und Herd"): "Backofen und Herd",

    # Fernseh/Entertainment-Varianten → kanonisch
    _norm_dev_key("Fernseher und Entertainment-Systeme"): "Fernseher und Entertainment-Systeme",
    _norm_dev_key("Fernseher und Entertainment"): "Fernseher und Entertainment-Systeme",
    _norm_dev_key("Fernseh- und Entertainment-Systeme"): "Fernseher und Entertainment-Systeme",
    _norm_dev_key("TV und Entertainment"): "Fernseher und Entertainment-Systeme",
    _norm_dev_key("TV/Entertainment"): "Fernseher und Entertainment-Systeme",
    _norm_dev_key("Fernseher"): "Fernseher und Entertainment-Systeme",

    _norm_dev_key("Bürogeräte"): "Bürogeräte",
    _norm_dev_key("Waschmaschine"): "Waschmaschine",
    _norm_dev_key("Staubsauger"): "Staubsauger",
}
APPLIANCES: list[str] = sorted(set(APPLIANCE_ALIASES.values()))

def _resolve_device_name(name: str) -> str | None:
    return APPLIANCE_ALIASES.get(_norm_dev_key(name))

def _resolve_device_columns(df: pd.DataFrame) -> dict[str, str]:
    """Mappt vorhandene Spaltennamen → kanonischer Gerätename (jeder kanonische Name max. einmal)."""
    mapping: dict[str, str] = {}
    seen = set()
    for col in df.columns:
        canon = _resolve_device_name(col)
        if canon and canon not in seen:
            mapping[col] = canon
            seen.add(canon)
    return mapping

def _canonize_device_series(s: pd.Series) -> pd.Series:
    """Wendet Alias-Mapping auf eine Gerätespalte an (Safety-Net)."""
    def _map_one(x):
        if pd.isna(x):
            return x
        canon = _resolve_device_name(x)
        return canon if canon else str(x)
    return s.astype("string").map(_map_one)


# -------------------- Wide → Long (alias-robust) --------------------
def _melt_device_wide(df: pd.DataFrame, value_name: str) -> pd.DataFrame:
    """
    Wide → Long für Gerätespalten. Nutzt die *tatsächliche* ID-Spalte,
    benennt sie danach in 'respondent_id' um und kanonisiert 'device'.
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=["respondent_id", "device", value_name])

    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    id_col = _find_id_col(df)
    mapping = _resolve_device_columns(df)

    if id_col is None or not mapping:
        return pd.DataFrame(columns=["respondent_id", "device", value_name])

    work = df[[id_col] + list(mapping.keys())].copy()
    work = work.rename(columns=mapping)  # Gerätespalten jetzt kanonisch benannt
    value_vars = sorted(set(mapping.values()))
    if not value_vars:
        return pd.DataFrame(columns=["respondent_id", "device", value_name])

    tmp = pd.melt(
        work,
        id_vars=[id_col],
        value_vars=value_vars,
        var_name="device",
        value_name=value_name,
    ).rename(columns={id_col: "respondent_id"})

    # Säubern
    tmp["respondent_id"] = tmp["respondent_id"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    tmp["device"] = _canonize_device_series(tmp["device"])
    tmp[value_name] = tmp[value_name].astype("string").str.strip()
    tmp = tmp[tmp[value_name].notna() & (tmp[value_name] != "")]
    return tmp


# -------------------- Q9 laden --------------------
def load_q9_nonuse_long_from_step4() -> pd.DataFrame:
    df = load_nonuse()
    if df.empty:
        return pd.DataFrame(columns=["respondent_id", "device", "q9_duration_text"])
    long = _melt_device_wide(df, "q9_duration_text")
    return long


# -------------------- Q10 laden (mehrere Layouts) --------------------
_Q10_NUM_RE = re.compile(r"(\d+(?:[.,]\d+)?)")

def _parse_q10_cell(val: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None, None
    s = str(val).strip()
    if not s:
        return None, None
    s_low = s.lower()

    if _Q10_NUM_RE.fullmatch(s_low):
        m = _Q10_NUM_RE.search(s_low)
        return "Ja, +", (m.group(1).replace(",", ".") if m else None)
    if "nein" in s_low:
        return "Nein", None
    if "ja" in s_low and (s_low == "f" or "fix" in s_low or "pausch" in s_low or "fixe" in s_low or "pauschal" in s_low):
        return "Ja, f", "0"

    if "ja" in s_low or "+" in s_low or "%" in s_low or "prozent" in s_low or "pct" in s_low:
        m = _Q10_NUM_RE.search(s_low)
        pct = m.group(1).replace(",", ".") if m else None
        return ("Ja, +" if ("+" in s_low or pct is not None) else "Ja, f"), pct
    return None, None

def _melt_q10_wide_choice_pct(df: pd.DataFrame) -> pd.DataFrame:
    df = _ensure_respondent_id(df)
    if "respondent_id" not in df.columns:
        return pd.DataFrame(columns=["respondent_id", "device", "q10_choice_text", "q10_pct_required_text"])

    # dynamisch Prefixe aus *_choice/_pct sammeln
    bases: set[str] = set()
    for c in df.columns:
        if c.endswith("_choice"):
            bases.add(c[:-7])
        elif c.endswith("_pct"):
            bases.add(c[:-4])

    rows: list[pd.DataFrame] = []
    for base in bases:
        canon = _resolve_device_name(base)
        if not canon:
            continue
        choice_col = f"{base}_choice" if f"{base}_choice" in df.columns else None
        pct_col    = f"{base}_pct"    if f"{base}_pct"    in df.columns else None
        if not choice_col and not pct_col:
            continue

        tmp = df[["respondent_id"]].copy()
        tmp["device"] = canon  # ← KANONISCH!
        tmp["q10_choice_text"] = df[choice_col].astype("string").str.strip() if choice_col else pd.NA
        tmp["q10_pct_required_text"] = df[pct_col].astype("string").str.strip() if pct_col else pd.NA
        rows.append(tmp)

    if not rows:
        return pd.DataFrame(columns=["respondent_id", "device", "q10_choice_text", "q10_pct_required_text"])

    out = pd.concat(rows, ignore_index=True)
    out["q10_pct_required_text"] = (
        out["q10_pct_required_text"].astype("string").str.replace("%", "", regex=False).str.strip()
    )
    out.loc[out["q10_pct_required_text"] == "", "q10_pct_required_text"] = pd.NA
    out = out[out[["q10_choice_text", "q10_pct_required_text"]].notna().any(axis=1)]
    return out[["respondent_id", "device", "q10_choice_text", "q10_pct_required_text"]]

def load_q10_incentives_long_from_step4(q9_devices: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    df = load_incentives()
    if df.empty:
        return pd.DataFrame(columns=["respondent_id", "device", "q10_choice_text", "q10_pct_required_text"])
    df = _ensure_respondent_id(df)

    # Layout A1: *_choice/_pct
    has_choice_pct = any(c.endswith("_choice") or c.endswith("_pct") for c in df.columns)
    if has_choice_pct:
        return _melt_q10_wide_choice_pct(df)

    # Layout A2: Spalten heißen wie Geräte → kombiniertes Feld je Gerät
    mapping = _resolve_device_columns(df)
    if mapping:
        melted = _melt_device_wide(df, "raw_q10")
        parsed = melted["raw_q10"].map(_parse_q10_cell)
        melted["q10_choice_text"] = parsed.map(lambda t: t[0])
        melted["q10_pct_required_text"] = parsed.map(lambda t: t[1])
        melted.drop(columns=["raw_q10"], inplace=True)
        # Safety-Net: Gerät nochmal kanonisieren
        melted["device"] = _canonize_device_series(melted["device"])
        return melted[["respondent_id", "device", "q10_choice_text", "q10_pct_required_text"]]

    # Layout B: respondent-level Felder
    choice_col = None
    pct_col = None
    for c in df.columns:
        cl = str(c).lower()
        if choice_col is None and any(tok in cl for tok in ["choice", "entscheidung", "teilnahme", "option", "beding"]):
            choice_col = c
        if pct_col is None and any(tok in cl for tok in ["percent", "prozent", "pct", "%", "kompens", "zuschuss"]):
            pct_col = c

    base = df[["respondent_id"]].copy()
    base["q10_choice_text"] = df[choice_col].astype("string").str.strip() if choice_col else pd.NA
    base["q10_pct_required_text"] = (
        df[pct_col].astype("string").str.replace("%", "", regex=False).str.strip() if pct_col else pd.NA
    )

    if choice_col is None and pct_col is None:
        text_col = None
        for c in df.columns:
            cl = str(c).lower()
            if any(tok in cl for tok in ["q10", "incentive", "kompens", "zuschuss"]):
                text_col = c
                break
        if text_col:
            rows = []
            for rid, raw in zip(df["respondent_id"], df[text_col]):
                ch, pct = _parse_q10_cell(raw)
                rows.append((rid, ch, pct))
            base = pd.DataFrame(rows, columns=["respondent_id", "q10_choice_text", "q10_pct_required_text"])

    # Auf Geräte bringen
    if q9_devices is not None and not q9_devices.empty:
        long = q9_devices.merge(base, on="respondent_id", how="left")
    else:
        respondents = base["respondent_id"].dropna().unique().tolist()
        long = (
            pd.DataFrame([(rid, dev) for rid in respondents for dev in APPLIANCES],
                         columns=["respondent_id", "device"])
            .merge(base, on="respondent_id", how="left")
        )

    long["device"] = _canonize_device_series(long["device"])
    long["q10_pct_required_text"] = long["q10_pct_required_text"].astype("string").str.replace("%", "", regex=False).str.strip()
    long.loc[long["q10_pct_required_text"] == "", "q10_pct_required_text"] = pd.NA
    return long[["respondent_id", "device", "q10_choice_text", "q10_pct_required_text"]]


# -------------------- Choice-Normalisierung --------------------
def _canon_choice(val) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "unknown_choice"
    s = str(val).strip().lower()
    if s in {"yes_fixed", "yes_conditional", "no"}:
        return s
    if s.startswith("ja, f") or "fix" in s:
        return "yes_fixed"
    if s.startswith("ja, +") or "zus" in s or "conditional" in s:
        return "yes_conditional"
    if s.startswith("nein"):
        return "no"
    return "unknown_choice"


# -------------------- Q9-Text → Stunden --------------------
Q9_DURATION_MAPPING: dict[str, float] = {
    "Nein, auf keinen Fall": 0.0,
    "Ja, aber maximal für 3 Stunden": 1.5,
    "Ja, für 3 bis 6 Stunden": 4.5,
    "Ja, für 6 bis 12 Stunden": 9.0,
    "Ja, für maximal 24 Stunden": 24.0,
    "Ja, für mehr als 24 Stunden": 30.0,
}


# -------------------- Hauptfunktion --------------------
def prepare_survey_flexibility_data() -> pd.DataFrame:
    """
    Liefert pro respondent_id & device:
      respondent_id, device, survey_max_duration_h,
      survey_incentive_choice, survey_incentive_pct_required
    """
    print("[INFO] prepare_survey_flexibility_data: lade & verarbeite Q9 …")
    q9_long = load_q9_nonuse_long_from_step4()
    if q9_long.empty:
        print("[WARNUNG] Q9 leer.")
        q9_proc = pd.DataFrame(columns=["respondent_id", "device", "survey_max_duration_h"])
    else:
        q9_proc = q9_long.copy()
        q9_proc["device"] = _canonize_device_series(q9_proc["device"])
        q9_proc["survey_max_duration_h"] = q9_proc["q9_duration_text"].map(Q9_DURATION_MAPPING)
        q9_proc["survey_max_duration_h"] = pd.to_numeric(q9_proc["survey_max_duration_h"], errors="coerce")
        q9_proc = q9_proc[["respondent_id", "device", "survey_max_duration_h"]]
    print(f"  Q9 verarbeitet: {q9_proc.shape}")

    print("[INFO] prepare_survey_flexibility_data: lade & verarbeite Q10 …")
    q10_long = load_q10_incentives_long_from_step4(
        q9_devices=q9_long[["respondent_id", "device"]].drop_duplicates() if not q9_long.empty else None
    )
    if q10_long.empty:
        print("[WARNUNG] Q10 leer.")
        q10_proc = pd.DataFrame(columns=["respondent_id", "device", "survey_incentive_choice", "survey_incentive_pct_required"])
    else:
        q10_proc = q10_long.copy()
        q10_proc["device"] = _canonize_device_series(q10_proc["device"])

        # Choice normalisieren
        q10_proc["survey_incentive_choice"] = q10_proc["q10_choice_text"].apply(_canon_choice)

        # Prozent → numerisch
        q10_proc["q10_pct_required_text"] = (
            q10_proc["q10_pct_required_text"]
            .astype("string")
            .str.replace("%", "", regex=False)
            .str.replace(",", ".")
            .replace({"": pd.NA, "nan": pd.NA, "<NA>": pd.NA})
        )
        q10_proc["survey_incentive_pct_required"] = pd.to_numeric(
            q10_proc["q10_pct_required_text"], errors="coerce"
        )

        # yes_fixed ⇒ 0 %
        q10_proc.loc[q10_proc["survey_incentive_choice"] == "yes_fixed", "survey_incentive_pct_required"] = 0.0

        q10_proc = q10_proc[
            ["respondent_id", "device", "survey_incentive_choice", "survey_incentive_pct_required"]
        ]
    print(f"  Q10 verarbeitet: {q10_proc.shape}")

    print("[INFO] merge Q9+Q10 (outer) …")
    out = pd.merge(q9_proc, q10_proc, on=["respondent_id", "device"], how="outer")
    out["device"] = _canonize_device_series(out["device"])  # Safety-Net nach dem Merge

    # fehlende Choice füllen
    if "survey_incentive_choice" in out.columns:
        out["survey_incentive_choice"] = out["survey_incentive_choice"].fillna("unknown_choice_q10_missing")
    else:
        out["survey_incentive_choice"] = "unknown_choice_q10_missing"
        out["survey_incentive_pct_required"] = np.nan

    out.dropna(subset=["respondent_id", "device"], inplace=True)
    out = out[
        ["respondent_id", "device", "survey_max_duration_h", "survey_incentive_choice", "survey_incentive_pct_required"]
    ]
    print(f"[INFO] fertig. Shape: {out.shape}")
    return out


if __name__ == "__main__":
    df = prepare_survey_flexibility_data()
    print(df.head())
    print(df.shape)