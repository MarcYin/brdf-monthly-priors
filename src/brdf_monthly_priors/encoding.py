from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from brdf_monthly_priors.types import (
    DEFAULT_PRIOR_NODATA,
    DEFAULT_SCALE_FACTOR,
    DEFAULT_UNCERTAINTY_NODATA,
)


@dataclass(frozen=True)
class EncodingConfig:
    """Raster encoding parameters for persisted BRDF priors."""

    scale_factor: int = DEFAULT_SCALE_FACTOR
    prior_nodata: int = DEFAULT_PRIOR_NODATA
    uncertainty_nodata: int = DEFAULT_UNCERTAINTY_NODATA
    max_relative_uncertainty: int = 200


DEFAULT_ENCODING = EncodingConfig()


def encode_prior(data: np.ndarray, config: EncodingConfig = DEFAULT_ENCODING) -> np.ndarray:
    """Encode floating BRDF coefficients as uint16 with scale factor 10000."""

    data = np.asarray(data)
    encoded = np.full(data.shape, config.prior_nodata, dtype="uint16")
    max_value = (config.prior_nodata - 1) / float(config.scale_factor)
    valid = np.isfinite(data) & (data >= 0.0) & (data <= max_value)
    encoded[valid] = np.rint(data[valid] * config.scale_factor).astype("uint16")
    return encoded


def decode_prior(data: np.ndarray, config: EncodingConfig = DEFAULT_ENCODING) -> np.ndarray:
    decoded = np.asarray(data).astype("float32") / float(config.scale_factor)
    return np.where(np.asarray(data) == config.prior_nodata, np.nan, decoded)


def encode_relative_uncertainty(
    uncertainty_percent: np.ndarray,
    config: EncodingConfig = DEFAULT_ENCODING,
) -> np.ndarray:
    """Encode relative uncertainty percent as uint8.

    Values from 0 to 200 are stored directly as rounded percent. Negative,
    non-finite, and >200% uncertainties are encoded as 255.
    """

    uncertainty_percent = np.asarray(uncertainty_percent)
    encoded = np.full(uncertainty_percent.shape, config.uncertainty_nodata, dtype="uint8")
    valid = (
        np.isfinite(uncertainty_percent)
        & (uncertainty_percent >= 0.0)
        & (uncertainty_percent <= float(config.max_relative_uncertainty))
    )
    encoded[valid] = np.rint(uncertainty_percent[valid]).astype("uint8")
    return encoded

def decode_relative_uncertainty(
    uncertainty: np.ndarray,
    config: EncodingConfig = DEFAULT_ENCODING,
) -> np.ndarray:
    decoded = np.asarray(uncertainty).astype("float32")
    return np.where(np.asarray(uncertainty) == config.uncertainty_nodata, np.nan, decoded)
