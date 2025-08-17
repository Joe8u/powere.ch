from pathlib import Path
import os

def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]

DATA_ROOT = Path(os.environ.get("POWERE_DATA_ROOT", repo_root() / "data"))
