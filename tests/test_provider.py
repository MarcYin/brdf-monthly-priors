import numpy as np
import pytest

from brdf_monthly_priors import Provider, ProviderConfig
from brdf_monthly_priors.sources.local import InMemorySource
from brdf_monthly_priors.types import Observation


def _observation(value, quality=0, uncertainty=10):
    return Observation(
        data=np.full((1, 2, 2), value, dtype="float32"),
        quality=np.full((2, 2), quality, dtype="uint16"),
        uncertainty=np.full((1, 2, 2), uncertainty, dtype="float32"),
        sample_index=np.zeros((2, 2), dtype="int16"),
        band_names=("iso",),
        source_id=f"obs-{value}",
    )


def test_provider_builds_and_cache_only_provider_retrieves(tmp_path):
    source = InMemorySource(
        observations=(
            _observation(0.1, quality=1),
            _observation(0.2, quality=0),
        ),
        name="fixture",
    )
    provider = Provider(ProviderConfig(cache_dir=tmp_path, source=source))

    product = provider.build_prior(
        bounds=(0, 0, 2, 2),
        crs="EPSG:4326",
        resolution=1,
        product_id="fixture-prior",
        band_names=("iso",),
    )

    assert product.composite.data[0, 0, 0] == np.float32(0.2)
    assert (tmp_path / product.request["request_hash"] / "stac-item.json").exists()

    cache_only = Provider(ProviderConfig(cache_dir=tmp_path, source_name="fixture"))
    loaded = cache_only.build_prior(
        bounds=(0, 0, 2, 2),
        crs="EPSG:4326",
        resolution=1,
        product_id="fixture-prior",
        band_names=("iso",),
    )

    assert loaded.stac_item["id"] == "fixture-prior"
    assert loaded.composite.data[0, 0, 0] == np.float32(0.2)


def test_provider_cache_miss_without_source_raises(tmp_path):
    provider = Provider(ProviderConfig(cache_dir=tmp_path, source_name="fixture"))

    with pytest.raises(RuntimeError, match="cache miss"):
        provider.build_prior(
            bounds=(0, 0, 2, 2),
            crs="EPSG:4326",
            resolution=1,
            product_id="missing",
            band_names=("iso",),
        )

