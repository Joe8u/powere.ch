from pathlib import Path
import os

DATA_ROOT = Path(os.environ.get('POWERE_DATA_ROOT') or (Path(__file__).resolve().parents[3] / 'data'))
