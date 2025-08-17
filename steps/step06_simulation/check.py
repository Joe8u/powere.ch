from datetime import datetime, timedelta
import pandas as pd

# Dataloader aus Step 4 verwenden
from steps.step04_dataloaders.dataloaders.lastprofile import load_appliances

# 1) Daten laden (Beispiel: 2 Tage, 2 Geräte, gruppiert)
start = datetime(2024, 1, 1)
end   = datetime(2024, 1, 3)
df = load_appliances(["Geschirrspüler", "Waschmaschine"], start, end, group=True)
assert isinstance(df, pd.DataFrame) and not df.empty and isinstance(df.index, pd.DatetimeIndex)
df = df.sort_index()

# 2) Naives DR-Fenster: Stunde mit höchster Gesamtlast
hourly_total = df.sum(axis=1).resample("1H").mean()
w_start = hourly_total.idxmax()
w_end   = w_start + timedelta(hours=1)

# 3) Mini-Simulation: 10% dieser Spitzenstunde in die Folgestunde verschieben
shift_frac = 0.10
hourly_shift = hourly_total.copy()
before = hourly_total.loc[w_start]

hourly_shift.loc[w_start] = hourly_shift.loc[w_start] * (1 - shift_frac)
next_hour = w_start + timedelta(hours=1)
if next_hour in hourly_shift.index:
    hourly_shift.loc[next_hour] = hourly_shift.loc[next_hour] + before * shift_frac
else:
    hourly_shift.loc[next_hour] = before * shift_frac
hourly_shift = hourly_shift.sort_index()

moved = before - hourly_shift.loc[w_start]

print(f"DR-Fenster: {w_start} → {w_end}")
print(f"Verschobene Energie (~): {float(moved):.3f} (Einheiten der Last)")
print("✅ Step 6 OK — Mini-Check ausgeführt.")
