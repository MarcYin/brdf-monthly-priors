"""Observation sources used by the monthly BRDF provider."""

from brdf_monthly_priors.sources.base import ObservationSource
from brdf_monthly_priors.sources.local import InMemorySource, LocalNpzSource

__all__ = ["InMemorySource", "LocalNpzSource", "ObservationSource"]

