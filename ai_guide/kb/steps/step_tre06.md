# Step tre06 — Netzsicht: verschiebbare Energie

## Ziele
- Maximale verschiebbare Energie je Event/Tag:
window_limit_mwh = sum(jasm_mwh_window) * finale_teilnahmequote
hh_limit_mwh     = households_in_scope * finale_teilnahmequote * event_kwh_cap / 1000
shiftable_energy_mwh = min(window_limit_mwh, hh_limit_mwh)

- Bindende Restriktion ausweisen: `per_household_cap` oder `window_energy`.

## Einheiten/Parameter
- Teilnahmequote & Caps wie in tre05.
- HH-Scope = Anzahl HH mit Gerät (oder Penetrationsfaktor * Gesamt-HH).
