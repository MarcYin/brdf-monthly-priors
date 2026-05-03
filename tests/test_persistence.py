from datetime import date

import numpy as np

from brdf_monthly_priors.persistence import CompositeStore, stable_json_hash
from brdf_monthly_priors.types import GridSpec, MonthlyComposite, MonthlyCompositeCollection


def test_store_round_trips_collection(tmp_path):
    grid = GridSpec.from_bounds((0, 0, 2, 2), "EPSG:32631", 1)
    composite = MonthlyComposite(
        month_start=date(2025, 7, 1),
        month_end=date(2025, 7, 31),
        history_months=(date(2024, 7, 1), date(2025, 7, 1)),
        grid=grid,
        band_names=("iso",),
        data=np.ones((1, 2, 2), dtype="float32"),
        quality=np.zeros((2, 2), dtype="uint16"),
        sample_index=np.zeros((2, 2), dtype="int16"),
        selected_observation=np.zeros((2, 2), dtype="int16"),
        observation_count=np.ones((2, 2), dtype="uint16"),
    )
    request = {"bounds": [0, 0, 2, 2], "crs": "EPSG:32631"}
    collection = MonthlyCompositeCollection(request=request, grid=grid, composites=(composite,))
    request_hash = stable_json_hash(request)

    store = CompositeStore(tmp_path)
    store.save(request_hash, collection)
    loaded = store.load(request_hash)

    assert loaded.schema_version == collection.schema_version
    assert loaded.grid == grid
    assert loaded.composite_for_month("2025-07").data[0, 0, 0] == 1

