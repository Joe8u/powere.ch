
import os, subprocess
from powere.etl.common import repo_root

def main():
    mods = [
        "powere.etl.survey.jobs.preprocess_q1_age",
        "powere.etl.survey.jobs.preprocess_q2_gender",
        "powere.etl.survey.jobs.preprocess_q3_household_size",
        "powere.etl.survey.jobs.preprocess_q4_accommodation",
        "powere.etl.survey.jobs.preprocess_q5_electricity",
        "powere.etl.survey.jobs.preprocess_q6_challenges",
        "powere.etl.survey.jobs.preprocess_q7_consequence",
        "powere.etl.survey.jobs.preprocess_q8_importance_wide",
        "powere.etl.survey.jobs.preprocess_q9_nonuse_wide",
        "powere.etl.survey.jobs.preprocess_q10_incentive_wide",
        "powere.etl.survey.jobs.preprocess_q11_notify_optin",
        "powere.etl.survey.jobs.preprocess_q12_smartplug",
        "powere.etl.survey.jobs.preprocess_q13_income",
        "powere.etl.survey.jobs.preprocess_q14_education",
        "powere.etl.survey.jobs.preprocess_q15_party",
    ]
    env = dict(os.environ)
    env["ROOT"] = str(repo_root())
    for m in mods:
        subprocess.run(["python", "-m", m], check=True, env=env)
    print("[OK] Survey processed neu erzeugt.")

if __name__ == "__main__":
    main()
