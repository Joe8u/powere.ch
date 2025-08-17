from pathlib import Path

# 1. bevorzugt: .../python/powere/data  (Symlink -> ../../data)
pkg_data = Path(__file__).resolve().parents[2] / "data"

# 2. Fallback: Repo-Root / data
repo_data = Path(__file__).resolve().parents[4] / "data"

DATA_ROOT = pkg_data if pkg_data.exists() else repo_data
