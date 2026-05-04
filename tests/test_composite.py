import numpy as np

from brdf_monthly_priors.composite import PriorCompositor
from brdf_monthly_priors.types import GridSpec, Observation


def test_best_pixel_prefers_quality_then_sample_index_without_time():
    grid = GridSpec.from_bounds((0, 0, 2, 2), "EPSG:4326", 1)
    bands = ("iso",)
    first = Observation(
        data=np.array([[[10, 10], [10, 10]]], dtype="float32") / 100,
        quality=np.array([[1, 0], [0, 0]], dtype="uint16"),
        uncertainty=np.array([[[5, 5], [5, 5]]], dtype="float32"),
        sample_index=np.array([[5, 5], [5, 8]], dtype="int16"),
        band_names=bands,
        source_id="first",
    )
    second = Observation(
        data=np.array([[[20, 20], [20, 20]]], dtype="float32") / 100,
        quality=np.array([[0, 0], [0, 0]], dtype="uint16"),
        uncertainty=np.array([[[6, 6], [6, 6]]], dtype="float32"),
        sample_index=np.array([[9, 9], [2, 8]], dtype="int16"),
        band_names=bands,
        source_id="second",
    )

    composite = PriorCompositor().compose(
        product_id="fixture",
        grid=grid,
        band_names=bands,
        observations=(first, second),
    )

    assert composite.data.shape == (1, 2, 2)
    assert composite.data[0, 0, 0] == np.float32(0.20)
    assert composite.data[0, 0, 1] == np.float32(0.10)
    assert composite.data[0, 1, 0] == np.float32(0.20)
    assert composite.data[0, 1, 1] == np.float32(0.10)
    assert composite.uncertainty[0, 0, 0] == np.float32(6)
    assert np.all(composite.observation_count == 2)


def test_empty_composite_has_schema_arrays():
    grid = GridSpec.from_bounds((0, 0, 2, 2), "EPSG:4326", 1)

    composite = PriorCompositor().compose(
        product_id="empty",
        grid=grid,
        band_names=("iso", "vol"),
        observations=(),
    )

    assert composite.data.shape == (2, 2, 2)
    assert np.isnan(composite.data).all()
    assert np.all(composite.selected_observation == -1)

