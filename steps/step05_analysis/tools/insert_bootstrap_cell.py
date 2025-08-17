import json, sys
from pathlib import Path
import importlib, types

BOOTSTRAP = """\
# --- powere.ch bootstrap: 'src' Shim für Dataloader ---
from pathlib import Path
import sys, types, importlib

# Repo-Root suchen (max. 6 Ebenen hoch), sodass 'steps/' existiert
p = Path.cwd()
for _ in range(6):
    if (p / "steps").exists():
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
        break
    p = p.parent

# Dataloader aus Step 4 als 'src' verfügbar machen
survey = importlib.import_module("steps.step04_dataloaders.dataloaders.survey")
lastprofile = importlib.import_module("steps.step04_dataloaders.dataloaders.lastprofile")

src = types.ModuleType("src")
src.survey = survey
src.lastprofile = lastprofile
sys.modules["src"] = src

print("Bootstrap aktiv: 'src.survey' & 'src.lastprofile' verfügbar.")
"""

def insert_bootstrap(nb_path: Path):
    nb = json.loads(nb_path.read_text(encoding="utf-8"))
    for cell in nb.get("cells", []):
        if cell.get("cell_type") == "code" and "powere.ch bootstrap" in "".join(cell.get("source", [])):
            print(f"[INFO] Bootstrap bereits vorhanden: {nb_path.name}")
            break
    else:
        cell = {
            "cell_type": "code",
            "execution_count": None,
            "metadata": {"powere_bootstrap": True},
            "outputs": [],
            "source": BOOTSTRAP.splitlines(keepends=True),
        }
        nb["cells"].insert(0, cell)
        nb_path.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[OK] Bootstrap hinzugefügt: {nb_path.name}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python insert_bootstrap_cell.py <notebook.ipynb>")
        sys.exit(2)
    for p in sys.argv[1:]:
        insert_bootstrap(Path(p))
