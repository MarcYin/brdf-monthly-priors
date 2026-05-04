import pytest

from brdf_monthly_priors.sources.earthaccess import EarthaccessSource, EarthdataCollection
from brdf_monthly_priors.temporal import sample_temporal_ranges, temporal_ranges_name


def test_sample_temporal_ranges_preserves_ranges_by_default():
    ranges = (("2024-07-01", "2024-07-31"),)

    assert sample_temporal_ranges(ranges) == ranges


def test_sample_temporal_ranges_expands_to_one_day_stride_windows():
    assert sample_temporal_ranges(
        (("2024-07-01", "2024-07-31"),),
        sample_every_days=7,
    ) == (
        ("2024-07-01", "2024-07-01"),
        ("2024-07-08", "2024-07-08"),
        ("2024-07-15", "2024-07-15"),
        ("2024-07-22", "2024-07-22"),
        ("2024-07-29", "2024-07-29"),
    )


def test_sample_temporal_ranges_rejects_invalid_stride():
    with pytest.raises(ValueError, match="positive"):
        sample_temporal_ranges((("2024-07-01", "2024-07-31"),), sample_every_days=0)


def test_sample_temporal_ranges_rejects_reversed_range():
    with pytest.raises(ValueError, match="before start"):
        sample_temporal_ranges((("2024-07-31", "2024-07-01"),), sample_every_days=7)


def test_temporal_ranges_name_includes_sampling_policy():
    assert (
        temporal_ranges_name((("2024-07-01", "2024-07-31"),), sample_every_days=7)
        == "2024-07-01..2024-07-31:sample-every-7-days"
    )


def test_earthaccess_source_default_name_includes_sampling_policy(tmp_path):
    source = EarthaccessSource(
        collections=(EarthdataCollection("MCD43A1", version="061"),),
        cache_dir=tmp_path,
        reader=object(),
        temporal_ranges=(("2024-07-01", "2024-07-31"),),
        sample_every_days=7,
    )

    assert source.query_temporal_ranges[1] == ("2024-07-08", "2024-07-08")
    assert source.name == "earthaccess:MCD43A1.061:2024-07-01..2024-07-31:sample-every-7-days"
