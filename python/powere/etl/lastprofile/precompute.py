from pathlib import Path
import subprocess
from powere.etl.common import repo_root

def main():
    root = repo_root()
    job = root / "processing" / "lastprofile" / "jobs" / "precompute_lastprofile_2024.py"
    if not job.exists():
        raise SystemExit(f"Job nicht gefunden: {job}")
    print(f"[ETL] running {job.name}")
    subprocess.run(["python3", str(job)], check=True)
    print("[OK] Lastprofile 2024 processed neu erzeugt.")

if __name__ == "__main__":
    main()
