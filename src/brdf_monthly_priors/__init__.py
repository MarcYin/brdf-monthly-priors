"""Build native-grid BRDF prior composites and persist them as STAC/GeoTIFF products."""

from brdf_monthly_priors._version import __version__
from brdf_monthly_priors.composite import MonthlyCompositor, PriorCompositor
from brdf_monthly_priors.encoding import (
    EncodingConfig,
    decode_prior,
    decode_relative_uncertainty,
    encode_prior,
    encode_relative_uncertainty,
)
from brdf_monthly_priors.provider import Provider, ProviderConfig
from brdf_monthly_priors.types import GridSpec, Observation, PriorComposite, PriorProduct

__all__ = [
    "__version__",
    "EncodingConfig",
    "GridSpec",
    "MonthlyCompositor",
    "Observation",
    "PriorComposite",
    "PriorCompositor",
    "PriorProduct",
    "Provider",
    "ProviderConfig",
    "decode_prior",
    "decode_relative_uncertainty",
    "encode_prior",
    "encode_relative_uncertainty",
]

