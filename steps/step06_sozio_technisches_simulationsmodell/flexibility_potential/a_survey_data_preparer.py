# steps/step06_sozio_technisches_simulationsmodell/flexibility_potential/a_survey_data_preparer.py
from __future__ import annotations

import re
from typing import Optional, Tuple
import numpy as np
import pandas as pd

# ⬇️ nutzt die Step-4-Dataloader
from steps.step04_dataloaders.dataloaders.survey import load_nonuse, load_incentives


# -------------------- Kanonische Gerätespalten --------------------
APPLIANCES = [
    "Geschirrspüler",
    "Backofen und Herd",
    "Fernseher und Entertainment-Systeme",
    "Bürogeräte",
    "Waschmaschine",
    "Staubsauger",
]

# Nur für Q10-*_choice/_pct: base->kanonisch (Quick-Fix TV)
_Q10_BASE_TO_CANON = {
    "Fernseher und Entertainment": "Fernseher und Entertainment-Systeme",
    # weitere Sonderfälle hier ergänzen, falls nötig
}


# -------------------- Helper --------------------
def _device_cols(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c in APPLIANCES]


def _melt_device_wide(df: pd.DataFrame, value_name: str) -> pd.DataFrame:
    """Erwartet: 'respondent_id' und Gerätespalten exakt wie in APPLIANCES."""
    if df.empty or "respondent_id" not in df.columns:
        return pd.DataFrame(columns=["respondent_id", "device", value_name])
    dev_cols = _device_cols(df)
    if not dev_cols:
        return pd.DataFrame(columns=["respondent_id", "device", value_name])

    tmp = pd.melt(
        df[["respondent_id"] + dev_cols],
        id_vars=["respondent_id"],
        value_vars=dev_cols,
        var_name="device",
        value_name=value_name,
    )
    tmp[value_name] = tmp[value_name].astype("string").str.strip()
    tmp.dropna(subset=[value_name], inplace=True)
    tmp = tmp[tmp[value_name] != ""]
    return tmp


def _melt_q10_wide_choice_pct(df: pd.DataFrame) -> pd.DataFrame:
    """
    NEU (schlank): Erkenne *_choice / *_pct automatisch, mappe den Basisnamen ggf. auf
    den kanonischen Gerätenamen (Quick-Fix für TV), und baue ein long-DF.
    """
    if df.empty or "respondent_id" not in df.columns:
        return pd.DataFrame(columns=["respondent_id", "device", "q10_choice_text", "q10_pct_required_text"])

    bases: set[str] = set()
    for c in df.columns:
        if c.endswith("_choice"):
            bases.add(c[:-7])
        elif c.endswith("_pct"):
            bases.add(c[:-4])

    rows = []
    for base in bases:
        # Basisname -> kanonisch (nur wenn nötig)
        canon = _Q10_BASE_TO_CANON.get(base, base)
        if canon not in APPLIANCES:
            # wenn der gemappte Name nicht in APPLIANCES ist, überspringen
            continue

        choice_col = f"{base}_choice" if f"{base}_choice" in df.columns else None
        pct_col    = f"{base}_pct"    if f"{base}_pct"    in df.columns else None
        if not choice_col and not pct_col:
            continue

        tmp = df[["respondent_id"]].copy()
        tmp["device"] = canon
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
    return out[["respondent_id", "device", "q10_choice_text", "q10_pct_required_text"]]


# ---------- Q9 aus Step-4 laden (Wide→Long) ----------
def load_q9_nonuse_long_from_step4() -> pd.DataFrame:
    df = load_nonuse()
    if df.empty or "respondent_id" not in df.columns:
        return pd.DataFrame(columns=["respondent_id", "device", "q9_duration_text"])
    long = _melt_device_wide(df, "q9_duration_text")
    return long


# ---------- Q10 aus Step-4 laden (robust, Wide oder Respondent-Level) ----------
_Q10_NUM_RE = re.compile(r"(\d+(?:[.,]\d+)?)")

def _parse_q10_cell(val: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """Text/Numeric -> ('Ja, f' | 'Ja, +' | 'Nein' | None, pct_text|None)"""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None, None
    s = str(val).strip()
    if not s:
        return None, None
    s_low = s.lower()

    # nur Zahl -> Prozent
    if _Q10_NUM_RE.fullmatch(s_low):
        m = _Q10_NUM_RE.search(s_low)
        return "Ja, +", (m.group(1).replace(",", ".") if m else None)

    if "nein" in s_low:
        return "Nein", None

    # „fixed“ (pauschal)
    if "ja" in s_low and (s_low == "f" or "fix" in s_low or "pausch" in s_low or "fixe" in s_low or "pauschal" in s_low):
        return "Ja, f", "0"

    if "ja" in s_low or "+" in s_low or "%" in s_low or "prozent" in s_low or "pct" in s_low:
        m = _Q10_NUM_RE.search(s_low)
        pct = m.group(1).replace(",", ".") if m else None
        return ("Ja, +" if ("+" in s_low or pct is not None) else "Ja, f"), pct

    return None, None


def load_q10_incentives_long_from_step4(q9_devices: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """
    Liefert long-Format mit Spalten:
      respondent_id, device, q10_choice_text, q10_pct_required_text

    Erkennt automatisch:
      - A1: Wide mit '<device>_choice' / '<device>_pct' (über Column-Scan + Quick-Fix TV)
      - A2: Wide mit einem kombinierten Feld je Gerät (Spalten-Namen genau wie Geräte)
      - B : Respondent-Level → auf Geräte expandieren
    """
    df = load_incentives()
    if df.empty or "respondent_id" not in df.columns:
        return pd.DataFrame(columns=["respondent_id", "device", "q10_choice_text", "q10_pct_required_text"])

    # A1: *_choice/_pct (NEU: nicht über APPLIANCES raten, sondern scannen)
    has_choice_pct = any(c.endswith("_choice") or c.endswith("_pct") for c in df.columns)
    if has_choice_pct:
        return _melt_q10_wide_choice_pct(df)

    # A2: Gerätespalten heißen exakt wie APPLIANCES → kombiniertes Feld je Gerät
    dev_cols = _device_cols(df)
    if dev_cols:
        melted = _melt_device_wide(df, "raw_q10")
        parsed = melted["raw_q10"].map(_parse_q10_cell)
        melted["q10_choice_text"] = parsed.map(lambda t: t[0])
        melted["q10_pct_required_text"] = parsed.map(lambda t: t[1])
        melted.drop(columns=["raw_q10"], inplace=True)
        return melted[["respondent_id", "device", "q10_choice_text", "q10_pct_required_text"]]

    # B: respondent-level Felder finden und auf Geräte expandieren
    choice_col = None
    pct_col = None
    for c in df.columns:
        cl = c.lower()
        if choice_col is None and any(tok in cl for tok in ["choice", "entscheidung", "teilnahme", "option", "beding"]):
            choice_col = c
        if pct_col is None and any(tok in cl for tok in ["percent", "prozent", "pct", "%", "kompens", "zuschuss"]):
            pct_col = c

    base = df[["respondent_id"]].copy()
    base["q10_choice_text"] = df[choice_col].astype("string").str.strip() if choice_col else pd.NA
    base["q10_pct_required_text"] = (
        df[pct_col].astype("string").str.replace("%", "", regex=False).str.strip() if pct_col else pd.NA
    )

    # Fallback: ein kombiniertes Textfeld parsen
    if choice_col is None and pct_col is None:
        text_col = None
        for c in df.columns:
            cl = c.lower()
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
        long = pd.DataFrame([(rid, dev) for rid in respondents for dev in APPLIANCES],
                            columns=["respondent_id", "device"]).merge(base, on="respondent_id", how="left")

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
    Liefert zusammengeführt pro respondent_id & device:
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
        q9_proc["survey_max_duration_h"] = q9_proc["q9_duration_text"].map(Q9_DURATION_MAPPING)
        q9_proc["survey_max_duration_h"] = pd.to_numeric(q9_proc["survey_max_duration_h"], errors="coerce")
        q9_proc = q9_proc[["respondent_id", "device", "survey_max_duration_h"]]
    print(f"  Q9 verarbeitet: {q9_proc.shape}")

    print("[INFO] prepare_survey_flexibility_data: lade & verarbeite Q10 …")
    q10_long = load_q10_incentives_long_from_step4(q9_devices=q9_long[["respondent_id", "device"]].drop_duplicates() if not q9_long.empty else None)
    if q10_long.empty:
        print("[WARNUNG] Q10 leer.")
        q10_proc = pd.DataFrame(columns=["respondent_id", "device", "survey_incentive_choice", "survey_incentive_pct_required"])
    else:
        q10_proc = q10_long.copy()

        # Choice → kanonisch
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

        # yes_fixed ⇒ 0.0 %
        q10_proc.loc[q10_proc["survey_incentive_choice"] == "yes_fixed", "survey_incentive_pct_required"] = 0.0

        q10_proc = q10_proc[
            ["respondent_id", "device", "survey_incentive_choice", "survey_incentive_pct_required"]
        ]
    print(f"  Q10 verarbeitet: {q10_proc.shape}")

    print("[INFO] merge Q9+Q10 (outer) …")
    out = pd.merge(q9_proc, q10_proc, on=["respondent_id", "device"], how="outer")

    # fehlende Choice füllen (wenn Zeile nur aus Q9 kam)
    if "survey_incentive_choice" in out.columns:
        out["survey_incentive_choice"] = out["survey_incentive_choice"].fillna("unknown_choice_q10_missing")
    else:
        out["survey_incentive_choice"] = "unknown_choice_q10_missing"
        out["survey_incentive_pct_required"] = np.nan

    out.dropna(subset=["respondent_id", "device"], inplace=True)
    out = out[["respondent_id", "device", "survey_max_duration_h", "survey_incentive_choice", "survey_incentive_pct_required"]]
    print(f"[INFO] fertig. Shape: {out.shape}")
    return out


if __name__ == "__main__":
    df = prepare_survey_flexibility_data()
    print(df.head())
    print(df.shape)