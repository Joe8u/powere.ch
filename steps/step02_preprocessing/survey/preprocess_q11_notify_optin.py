#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Preprocess Survey Q11 (Notify opt-in):
- liest das Survey-CSV (SurveyMonkey: zweite Kopfzeile wird übersprungen),
- findet 'respondent_id' und die Benachrichtigungs-Frage robust (tolerant ggü. NBSP, „z. B.“ etc.),
- normalisiert Antworten auf {Ja, Nein, Weiss nicht},
- schreibt data/survey/processed/question_11_notify_optin.csv.

Aufruf (Repo-Root):
  python3 processing/survey/jobs/preprocess_q11_notify_optin.py
  # optional:
  python3 processing/survey/jobs/preprocess_q11_notify_optin.py --infile ... --outfile ... --debug
"""

from __future__ import annotations
import argparse
from pathlib import Path
import sys
import re
import pandas as pd

def project_root() -> Path:
    try:
        return Path(__file__).resolve().parents[3]
    except NameError:
        return Path.cwd()

def read_raw_csv(path: Path) -> pd.DataFrame:
    # SurveyMonkey: zweite Kopfzeile (Options-/Response-Zeile) überspringen
    try:
        return pd.read_csv(path, encoding="utf-8", sep=",", header=0, skiprows=[1], dtype=str)
    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="latin-1", sep=",", header=0, skiprows=[1], dtype=str)

def _slug(s: str) -> str:
    """Sehr robuste Normalisierung: Kleinbuchstaben, Umlaute → ae/oe/ue/ss,
    alle Whitespaces (inkl. NBSP/NBTHINSP) und Nicht-Wortzeichen raus."""
    if s is None:
        return ""
    t = str(s).lower()
    t = t.replace("ä","ae").replace("ö","oe").replace("ü","ue").replace("ß","ss")
    t = re.sub(r"\s+", "", t, flags=re.UNICODE)          # entfernt alle Whitespaces inkl. NBSP
    t = re.sub(r"[^\w]+", "", t, flags=re.UNICODE)       # entfernt Satzzeichen etc.
    return t

def find_col_by_names(columns, candidates):
    # 1) exakte Treffer
    for c in candidates:
        if c in columns:
            return c
    # 2) slug-basierte Treffer
    norm = {_slug(col): col for col in columns}
    for c in candidates:
        k = _slug(c)
        if k in norm:
            return norm[k]
    return None

def fallback_keyword_search(columns) -> str | None:
    """Wählt die Spalte mit der höchsten Token-Trefferrate."""
    token_sets = [
        ("benachrichtigt","sms","app"),
        ("benachrichtigung","sms"),
        ("notify","sms"),
        ("benachrichtigt","stromnetz","ausgelastet"),
    ]
    best = (0, None)
    for col in columns:
        s = _slug(col)
        score = max(sum(tok in s for tok in toks) for toks in token_sets)
        if score > best[0]:
            best = (score, col)
    return best[1] if best[0] >= 2 else None  # mind. 2 Tokens als Sicherheit

def normalize_answer(val):
    """Mappt diverse Schreibweisen auf {Ja, Nein, Weiss nicht} oder <NA>."""
    if val is None or pd.isna(val):
        return pd.NA
    s = str(val).strip().lower()
    if s in {"ja", "yes", "y"}:
        return "Ja"
    if s in {"nein", "no", "n"}:
        return "Nein"
    if s in {"weiss nicht", "weiß nicht", "weis nicht", "wn", "dont know", "don't know", "dk"}:
        return "Weiss nicht"
    # Falls schon sauber:
    if s == "ja": return "Ja"
    if s == "nein": return "Nein"
    return pd.NA

def preprocess(infile: Path, outfile: Path, debug: bool=False) -> None:
    print(f"[INFO] Repo-Root: {project_root()}")
    print(f"[INFO] Input CSV: {infile}")
    print(f"[INFO] Output:    {outfile}")

    df = read_raw_csv(infile)

    # respondent_id robust finden
    resp_col = find_col_by_names(df.columns, ["respondent_id", "Respondent ID", "respondent id"])
    if not resp_col:
        raise KeyError("respondent_id-Spalte nicht gefunden.")

    # Q11 – Kandidaten (deutsche/verkürzte Varianten + mögliche Tippfehler)
    q11_candidates = [
        "Könnten Sie sich vorstellen, von Ihrem Elektrizitätswerk benachrichtigt zu werden (z. B. per SMS oder App), wenn das Stromnetz stark ausgelastet ist?",
        "Koennten Sie sich vorstellen, von Ihrem Elektrizitaetswerk benachrichtigt zu werden (z. B. per SMS oder App), wenn das Stromnetz stark ausgelastet ist?",
        "Benachrichtigung per SMS oder App",
        "Benachrichtigt zu werden (z. B. per SMS oder App)",
        "Elektrizitätswerk benachrichtigt",
        "stark ausgelastet ist",
    ]
    q11_col = find_col_by_names(df.columns, q11_candidates)
    if not q11_col:
        q11_col = fallback_keyword_search(df.columns)
    if not q11_col:
        if debug:
            print("[DEBUG] Konnte Q11 nicht erkennen. Verfügbare Spaltennamen:")
            for c in df.columns:
                print("  -", c)
        raise KeyError("Q11 (Benachrichtigung) Spalte nicht gefunden.")

    if debug:
        print(f"[DEBUG] Q11-Spalte erkannt als: {q11_col}")

    out = df[[resp_col, q11_col]].copy()
    out.rename(columns={resp_col: "respondent_id", q11_col: "notify_optin"}, inplace=True)

    # Antworten normalisieren
    s = out["notify_optin"].astype("string").str.strip()
    s = s.replace({"": pd.NA, "nan": pd.NA, "NaN": pd.NA})
    out["notify_optin"] = s.apply(normalize_answer)

    outfile.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(outfile, index=False, encoding="utf-8")

    total = len(out)
    counts = out["notify_optin"].value_counts(dropna=False).to_dict()
    print(f"[OK] Geschrieben: {outfile}  (rows={total})")
    print(f"[INFO] Verteilung: {counts}")

def main():
    root = project_root()
    default_in = root / "data/survey/raw/Energieverbrauch und Teilnahmebereitschaft an Demand-Response-Programmen in Haushalten.csv"
    default_out = root / "data/survey/processed/question_11_notify_optin.csv"

    ap = argparse.ArgumentParser(description="Preprocess Survey Q11 (Notify opt-in)")
    ap.add_argument("--infile", type=str, default=str(default_in), help="Pfad zur Roh-CSV")
    ap.add_argument("--outfile", type=str, default=str(default_out), help="Pfad zur Ausgabe-CSV")
    ap.add_argument("--debug", action="store_true", help="Mehr Logs ausgeben")
    args = ap.parse_args()

    infile = Path(args.infile).resolve()
    outfile = Path(args.outfile).resolve()
    if not infile.exists():
        print(f"[ERROR] Input nicht gefunden: {infile}", file=sys.stderr)
        sys.exit(1)

    preprocess(infile, outfile, debug=args.debug)

if __name__ == "__main__":
    main()
