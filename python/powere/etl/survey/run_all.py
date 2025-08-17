from pathlib import Path
import subprocess
from powere.etl.common import repo_root

def main():
    root = repo_root()
    jobs = [
        "preprocess_q1_age.py",
        "preprocess_q2_gender.py",
        "preprocess_q3_household_size.py",
        "preprocess_q4_accommodation.py",
        "preprocess_q5_electricity.py",
        "preprocess_q6_challenges.py",
        "preprocess_q7_consequence.py",
        "preprocess_q8_importance_wide.py",
        "preprocess_q9_nonuse_wide.py",
        "preprocess_q10_incentive_wide.py",
        "preprocess_q11_notify_optin.py",
        "preprocess_q12_smartplug.py",
        "preprocess_q13_income.py",
        "preprocess_q14_education.py",
        "preprocess_q15_party.py",
    ]
    jobdir = root / "processing" / "survey" / "jobs"
    for j in jobs:
        print(f"[ETL] running {j}")
        subprocess.run(["python3", str(jobdir / j)], check=True)
    print("[OK] Survey processed neu erzeugt.")

if __name__ == "__main__":
    main()
