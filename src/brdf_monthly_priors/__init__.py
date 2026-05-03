"""Build and cache monthly BRDF prior composites."""

from brdf_monthly_priors._version import __version__
from brdf_monthly_priors.composite import MonthlyCompositor
from brdf_monthly_priors.periods import MonthlyPeriod, plan_monthly_periods
from brdf_monthly_priors.provider import Provider, ProviderConfig
from brdf_monthly_priors.types import (
    GridSpec,
    MonthlyComposite,
    MonthlyCompositeCollection,
    Observation,
)

__all__ = [
    "__version__",
    "GridSpec",
    "MonthlyComposite",
    "MonthlyCompositeCollection",
    "MonthlyCompositor",
    "MonthlyPeriod",
    "Observation",
    "Provider",
    "ProviderConfig",
    "plan_monthly_periods",
]

