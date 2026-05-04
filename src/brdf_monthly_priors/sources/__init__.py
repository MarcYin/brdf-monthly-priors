"""Observation sources used by the monthly BRDF provider."""

from brdf_monthly_priors.sources.base import ObservationSource
from brdf_monthly_priors.sources.gee import (
    EdownGeeSource,
    EdownSource,
    GeeEdownSource,
    GeeProductPreset,
    gee_product_preset,
)
from brdf_monthly_priors.sources.local import InMemorySource, LocalNpzSource

__all__ = [
    "EdownGeeSource",
    "EdownSource",
    "GeeEdownSource",
    "GeeProductPreset",
    "InMemorySource",
    "LocalNpzSource",
    "ObservationSource",
    "gee_product_preset",
]
