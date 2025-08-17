from pathlib import Path

def repo_root() -> Path:
    p = Path(__file__).resolve()
    for _ in range(12):
        if (p / ".git").exists():
            return p
        p = p.parent
    return Path.cwd()
