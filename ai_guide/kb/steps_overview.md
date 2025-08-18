# Pipeline-Überblick (Steps 1–6)
- **Step 1:** TRE-Preis-Peaks im Jahr (UTC, 15-min) finden.
- **Step 2–4:** Fenster um Peaks, Kandidatentage & Ranking.
- **Step 5 (tre05):** Teilnahme-Iteration aus Umfrage → Angebots-% (Monatsbasis) → Event-Caps anwenden:
  - Zeit-Cap: `min(event_duration, 3h, cycle_hours)`
  - Energie-Cap: `min(cycle_kwh, cycle_power * paid_hours)`
  - Pro Event/HH maximal: `avg_tre_price_paid * event_kwh_cap`
- **Step 6 (tre06):** Netzsicht, verschiebbare Energiemenge:
  `shiftable_energy_mwh = min(window_limit, hh_limit)`