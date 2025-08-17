
import os, subprocess
from powere.etl.common import repo_root

def main():
    env = dict(os.environ)
    env["ROOT"] = str(repo_root())
    subprocess.run(["python", "-m", "powere.etl.lastprofile.jobs.precompute_lastprofile_2024"], check=True, env=env)
    print("[OK] Lastprofile 2024 processed neu erzeugt.")

if __name__ == "__main__":
    main()
