from .io import (
    q1_age, q2_gender, q3_household_size, q4_accommodation, q5_electricity,
    q6_challenges, q7_consequence, q8_importance_wide, q9_nonuse_wide,
    q10_incentive_wide, q11_notify_optin, q12_smartplug, q13_income,
)
__all__ = [
    "q1_age","q2_gender","q3_household_size","q4_accommodation","q5_electricity",
    "q6_challenges","q7_consequence","q8_importance_wide","q9_nonuse_wide",
    "q10_incentive_wide","q11_notify_optin","q12_smartplug","q13_income",
]

from .attitudes import load_attitudes, load_challenges, load_consequence  # Q6/Q7

try:
    __all__.extend(["load_attitudes", "load_challenges", "load_consequence"])
except NameError:  # falls __all__ oben nicht definiert wäre
    __all__ = ["load_attitudes", "load_challenges", "load_consequence"]

)
try:
    __all__.extend([
    ])
except NameError:
    __all__ = [
    ]

try:
except NameError:
