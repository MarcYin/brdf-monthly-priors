import sys
import types
from pathlib import Path
from typing import Optional

import numpy as np
import rasterio
from rasterio.transform import from_origin

from brdf_monthly_priors.provider import Provider, ProviderConfig
from brdf_monthly_priors.sources.gee import EdownGeeSource, gee_product_preset


def test_gee_product_preset_maps_default_brdf_bands():
    preset = gee_product_preset("mcd43a1")

    assert preset.collection_id == "MODIS/061/MCD43A1"
    assert preset.band_map["brdf_iso_red"] == "BRDF_Albedo_Parameters_Band1_iso"
    assert preset.band_map["brdf_iso_green"] == "BRDF_Albedo_Parameters_Band4_iso"
    assert preset.band_map["brdf_iso_blue"] == "BRDF_Albedo_Parameters_Band3_iso"
    assert preset.quality_band_map["brdf_iso_red"] == "BRDF_Albedo_Band_Mandatory_Quality_Band1"
    assert preset.quality_band_map["brdf_iso_swir2"] == "BRDF_Albedo_Band_Mandatory_Quality_Band7"
    assert preset.scale_map["BRDF_Albedo_Parameters_Band1_iso"] == 0.001


def test_provider_builds_from_edown_source_native_grid(tmp_path, monkeypatch):
    install_fake_edown(monkeypatch, tmp_path)
    source = EdownGeeSource(
        collection_id="FAKE/COLLECTION",
        temporal_ranges=(("2024-01-01", "2024-01-03"),),
        output_root=tmp_path / "edown",
        band_map={"iso": "GEE_ISO"},
        quality_band_map={"iso": "GEE_QA"},
        scale_map={"GEE_ISO": 0.001},
    )
    provider = Provider(ProviderConfig(cache_dir=tmp_path / "cache", source=source))

    product = provider.build_prior(
        product_id="gee-prior",
        wgs84_bounds=(0, 0, 1, 1),
        brdf_crs="EPSG:4326",
        resolution=999,
        band_names=("iso",),
    )

    assert product.grid.bounds == (10.0, 18.0, 12.0, 20.0)
    assert product.grid.resolution == 1.0
    assert product.composite.data.shape == (1, 2, 2)
    assert float(product.composite.data[0, 0, 0]) == 0.25
    assert product.composite.quality[0, 1] == 1
    assert product.request["source"] == "gee-edown:FAKE/COLLECTION:2024-01-01..2024-01-03"


def test_gee_source_maps_quality_fill_to_nodata(tmp_path, monkeypatch):
    install_fake_edown(
        monkeypatch,
        tmp_path,
        data=np.array([[0.0, 0.0], [0.25, 0.25]], dtype="float32"),
        quality=np.array([[255, 255], [0, 0]], dtype="float32"),
    )
    source = EdownGeeSource(
        collection_id="FAKE/COLLECTION",
        temporal_ranges=(("2024-01-01", "2024-01-01"),),
        output_root=tmp_path / "edown",
        band_map={"iso": "GEE_ISO"},
        quality_band_map={"iso": "GEE_QA"},
        quality_nodata_values=(255,),
    )
    provider = Provider(ProviderConfig(cache_dir=tmp_path / "cache", source=source))

    product = provider.build_prior(
        product_id="gee-prior",
        wgs84_bounds=(0, 0, 1, 1),
        resolution=999,
        band_names=("iso",),
    )

    assert np.isnan(product.composite.data[0, 0]).all()
    assert np.all(product.composite.data[0, 1] == np.float32(0.25))
    assert np.all(product.composite.observation_count[0] == 0)
    assert np.all(product.composite.observation_count[1] == 1)


def install_fake_edown(
    monkeypatch,
    tmp_path: Path,
    *,
    data: Optional[np.ndarray] = None,
    quality: Optional[np.ndarray] = None,
) -> None:
    module = types.ModuleType("edown")

    class AOI:
        @classmethod
        def from_bbox(cls, bbox):
            return tuple(bbox)

    class DownloadConfig:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class Result:
        def __init__(self, path):
            self.image_id = "fake-image"
            self.status = "downloaded"
            self.tiff_path = path
            self.error = None

    class Summary:
        def __init__(self, path):
            self.results = (Result(path),)
            self.failed = 0

    def download_images(config):
        assert config.collection_id == "FAKE/COLLECTION"
        assert config.bands == ("GEE_ISO", "GEE_QA")
        assert config.rename_map == {"GEE_ISO": "iso"}
        path = tmp_path / "edown" / "images" / "fake.tif"
        path.parent.mkdir(parents=True, exist_ok=True)
        data_array = (
            np.array([[0.25, 0.50], [0.75, 1.0]], dtype="float32") if data is None else data
        )
        quality_array = np.array([[0, 1], [0, 1]], dtype="float32") if quality is None else quality
        with rasterio.open(
            path,
            "w",
            driver="GTiff",
            height=2,
            width=2,
            count=2,
            dtype="float32",
            crs="EPSG:4326",
            transform=from_origin(10, 20, 1, 1),
            nodata=np.nan,
        ) as dataset:
            dataset.descriptions = ("iso", "GEE_QA")
            dataset.write(
                np.array(
                    [data_array, quality_array],
                    dtype="float32",
                )
            )
        return Summary(path)

    module.AOI = AOI
    module.DownloadConfig = DownloadConfig
    module.download_images = download_images
    monkeypatch.setitem(sys.modules, "edown", module)
