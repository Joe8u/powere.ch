"""Survey dataloaders."""
from .attitudes import load_attitudes, load_challenges, load_consequence
from .demand_response import (
    load_demand_response, load_importance, load_notification, load_smart_plug
)
from .demographics import (
    load_demographics, load_age, load_gender, load_household_size,
    load_accommodation, load_electricity
)

__all__ = [
    "load_attitudes", "load_challenges", "load_consequence",
    "load_demand_response", "load_importance", "load_notification", "load_smart_plug",
    "load_demographics", "load_age", "load_gender", "load_household_size",
    "load_accommodation", "load_electricity",
]
