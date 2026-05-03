from datetime import date

import numpy as np

from brdf_monthly_priors.composite import MonthlyCompositor
from brdf_monthly_priors.periods import plan_monthly_periods
from brdf_monthly_priors.types import GridSpec, Observation


def test_best_pixel_prefers_quality_then_date_then_sample_index():
    grid = GridSpec.from_bounds((0, 0, 2, 2), "EPSG:32631", 1)
    period = plan_monthly_periods(date(2025, 7, 12), months_window=(0,), history_years=2)[0]
    bands = ("iso",)
    older = Observation(
        acquired=date(2024, 7, 12),
        data=np.array([[[10, 10], [10, 10]]], dtype="float32"),
        quality=np.array([[1, 0], [0, 0]], dtype="uint16"),
        sample_index=np.array([[5, 5], [5, 8]], dtype="int16"),
        band_names=bands,
        source_id="older",
    )
    target = Observation(
        acquired=date(2025, 7, 12),
        data=np.array([[[20, 20], [20, 20]]], dtype="float32"),
        quality=np.array([[0, 0], [0, 0]], dtype="uint16"),
        sample_index=np.array([[9, 9], [2, 8]], dtype="int16"),
        band_names=bands,
        source_id="target",
    )

    composite = MonthlyCompositor().compose(
        period=period,
        grid=grid,
        band_names=bands,
        observations=(older, target),
        preferred_date=date(2025, 7, 12),
    )

    assert composite.data.shape == (1, 2, 2)
    assert composite.data[0, 0, 0] == 20
    assert composite.data[0, 0, 1] == 20
    assert composite.data[0, 1, 0] == 20
    assert composite.data[0, 1, 1] == 20
    assert np.all(composite.observation_count == 2)


def test_empty_composite_has_schema_arrays():
    grid = GridSpec.from_bounds((0, 0, 2, 2), "EPSG:32631", 1)
    period = plan_monthly_periods(date(2025, 7, 12), months_window=(0,), history_years=1)[0]

    composite = MonthlyCompositor().compose(
        period=period,
        grid=grid,
        band_names=("iso", "vol"),
        observations=(),
        preferred_date=date(2025, 7, 12),
    )

    assert composite.data.shape == (2, 2, 2)
    assert np.isnan(composite.data).all()
    assert np.all(composite.selected_observation == -1)

