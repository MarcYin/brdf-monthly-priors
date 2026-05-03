from datetime import date

import numpy as np
import pytest

from brdf_monthly_priors import Provider, ProviderConfig
from brdf_monthly_priors.sources.local import InMemorySource
from brdf_monthly_priors.types import Observation


def _observation(acquired, value, quality=0):
    return Observation(
        acquired=acquired,
        data=np.full((1, 2, 2), value, dtype="float32"),
        quality=np.full((2, 2), quality, dtype="uint16"),
        sample_index=np.zeros((2, 2), dtype="int16"),
        band_names=("iso",),
        source_id=f"obs-{acquired}",
    )


def test_provider_builds_and_cache_only_provider_retrieves(tmp_path):
    source = InMemorySource(
        observations=(
            _observation(date(2024, 7, 15), 10, quality=1),
            _observation(date(2025, 7, 12), 20, quality=0),
        ),
        name="fixture",
    )
    provider = Provider(ProviderConfig(cache_dir=tmp_path, source=source))

    collection = provider.get_monthly_composites(
        bounds=(0, 0, 2, 2),
        crs="EPSG:32631",
        observation_date=date(2025, 7, 12),
        resolution=1,
        months_window=(0,),
        history_years=2,
        band_names=("iso",),
    )

    assert collection.composite_for_month("2025-07").data[0, 0, 0] == 20

    cache_only = Provider(ProviderConfig(cache_dir=tmp_path, source_name="fixture"))
    loaded = cache_only.get_monthly_composites(
        bounds=(0, 0, 2, 2),
        crs="EPSG:32631",
        observation_date="2025-07-12",
        resolution=1,
        months_window=(0,),
        history_years=2,
        band_names=("iso",),
    )

    assert loaded.composite_for_month("2025-07").data[0, 0, 0] == 20


def test_provider_cache_miss_without_source_raises(tmp_path):
    provider = Provider(ProviderConfig(cache_dir=tmp_path, source_name="fixture"))

    with pytest.raises(RuntimeError, match="cache miss"):
        provider.get_monthly_composites(
            bounds=(0, 0, 2, 2),
            crs="EPSG:32631",
            observation_date="2025-07-12",
            resolution=1,
            months_window=(0,),
            history_years=2,
            band_names=("iso",),
        )

