import numpy as np

from brdf_monthly_priors.encoding import encode_prior, encode_relative_uncertainty


def test_prior_encoding_uses_uint16_scale_factor():
    encoded = encode_prior(np.array([0.0, 0.1234, np.nan], dtype="float32"))
    assert encoded.dtype == np.uint16
    assert encoded.tolist() == [0, 1234, 65535]


def test_uncertainty_encoding_flags_larger_than_200_percent():
    encoded = encode_relative_uncertainty(np.array([0, 12.4, 200, 200.1, np.nan], dtype="float32"))
    assert encoded.dtype == np.uint8
    assert encoded.tolist() == [0, 12, 200, 255, 255]

