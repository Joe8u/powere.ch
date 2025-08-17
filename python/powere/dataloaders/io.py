from pathlib import Path
# Datei liegt unter .../python/powere/dataloaders/io.py
_pkg_root = Path(__file__).resolve().parents[1]  # .../python/powere
pkg_data  = _pkg_root / "data"                   # -> Symlink auf ../../data
repo_data = _pkg_root.parents[1] / "data"        # .../powere.ch/data (Fallback)
DATA_ROOT = pkg_data if pkg_data.exists() else repo_data
