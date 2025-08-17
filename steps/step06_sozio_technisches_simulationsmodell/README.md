# Step 6 – Sozio-technisches Simulationsmodell

- Paketpfad: `steps.step06_sozio_technisches_simulationsmodell`
- Bitte ASCII/Unterstriche für Modulnamen verwenden (keine Umlaute/Minus), damit `import` zuverlässig funktioniert.
- Zugriff auf Daten via `steps.step04_dataloaders.dataloaders.[survey|lastprofile]`.

## Quickstart
    from steps.step06_sozio_technisches_simulationsmodell import *
    from steps.step04_dataloaders.dataloaders.survey import load_incentives
    df_inc = load_incentives()
