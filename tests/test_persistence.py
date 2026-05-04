import json

import numpy as np
import rasterio

from brdf_monthly_priors.persistence import CompositeStore, stable_json_hash
from brdf_monthly_priors.types import GridSpec, PriorComposite


def test_store_writes_tiled_deflate_geotiffs_and_stac_item(tmp_path):
    grid = GridSpec.from_bounds((0, 0, 2, 2), "EPSG:4326", 1)
    composite = PriorComposite(
        product_id="prior-fixture",
        grid=grid,
        band_names=("iso",),
        data=np.array([[[0.1, 0.2], [0.3, np.nan]]], dtype="float32"),
        uncertainty=np.array([[[5, 201], [200, np.nan]]], dtype="float32"),
        quality=np.zeros((2, 2), dtype="uint16"),
        sample_index=np.zeros((2, 2), dtype="int16"),
        selected_observation=np.zeros((2, 2), dtype="int16"),
        observation_count=np.ones((2, 2), dtype="uint16"),
    )
    request = {"product_id": "prior-fixture", "bounds": [0, 0, 2, 2], "crs": "EPSG:4326"}
    request_hash = stable_json_hash(request)

    store = CompositeStore(tmp_path)
    product = store.save(request_hash=request_hash, request=request, composite=composite)

    stac_path = tmp_path / request_hash / "stac-item.json"
    assert stac_path.exists()
    stac_item = json.loads(stac_path.read_text(encoding="utf-8"))
    assert stac_item["type"] == "Feature"
    assert stac_item["assets"]["prior"]["href"] == "assets/prior.tif"
    assert product.stac_item["id"] == "prior-fixture"

    with rasterio.open(tmp_path / request_hash / "assets" / "prior.tif") as dataset:
        assert dataset.dtypes == ("uint16",)
        assert dataset.nodata == 65535
        assert dataset.compression.value.lower() == "deflate"
        assert dataset.block_shapes[0] == (512, 512)
        assert dataset.overviews(1) == []
        assert dataset.scales == (0.0001,)
        assert dataset.read(1).tolist() == [[1000, 2000], [3000, 65535]]

    with rasterio.open(tmp_path / request_hash / "assets" / "uncertainty.tif") as dataset:
        assert dataset.dtypes == ("uint8",)
        assert dataset.nodata == 255
        assert dataset.compression.value.lower() == "deflate"
        assert dataset.block_shapes[0] == (512, 512)
        assert dataset.overviews(1) == []
        assert dataset.read(1).tolist() == [[5, 255], [200, 255]]
