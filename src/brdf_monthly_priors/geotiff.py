from __future__ import annotations

import os
from pathlib import Path
from typing import Sequence

import numpy as np

from brdf_monthly_priors.encoding import (
    DEFAULT_ENCODING,
    EncodingConfig,
    encode_prior,
    encode_relative_uncertainty,
)
from brdf_monthly_priors.types import GridSpec, PriorComposite


def write_prior_geotiff(
    path: str | Path,
    *,
    composite: PriorComposite,
    encoding: EncodingConfig = DEFAULT_ENCODING,
    tile_size: int = 512,
) -> Path:
    return write_tiled_geotiff(
        path,
        grid=composite.grid,
        band_names=composite.band_names,
        array=encode_prior(composite.data, encoding),
        dtype="uint16",
        nodata=encoding.prior_nodata,
        scales=[1.0 / float(encoding.scale_factor)] * len(composite.band_names),
        units=["1"] * len(composite.band_names),
        tile_size=tile_size,
    )


def write_prior_band_geotiff(
    path: str | Path,
    *,
    composite: PriorComposite,
    band_index: int,
    encoding: EncodingConfig = DEFAULT_ENCODING,
    tile_size: int = 512,
) -> Path:
    band_name = composite.band_names[band_index]
    return write_tiled_geotiff(
        path,
        grid=composite.grid,
        band_names=(band_name,),
        array=encode_prior(composite.data[band_index : band_index + 1], encoding),
        dtype="uint16",
        nodata=encoding.prior_nodata,
        scales=(1.0 / float(encoding.scale_factor),),
        units=("1",),
        tile_size=tile_size,
    )


def write_uncertainty_geotiff(
    path: str | Path,
    *,
    composite: PriorComposite,
    encoding: EncodingConfig = DEFAULT_ENCODING,
    tile_size: int = 512,
) -> Path:
    return write_tiled_geotiff(
        path,
        grid=composite.grid,
        band_names=[f"{band}_relative_uncertainty" for band in composite.band_names],
        array=encode_relative_uncertainty(composite.uncertainty, encoding),
        dtype="uint8",
        nodata=encoding.uncertainty_nodata,
        scales=[1.0] * len(composite.band_names),
        units=["percent"] * len(composite.band_names),
        tile_size=tile_size,
    )


def write_uncertainty_band_geotiff(
    path: str | Path,
    *,
    composite: PriorComposite,
    band_index: int,
    encoding: EncodingConfig = DEFAULT_ENCODING,
    tile_size: int = 512,
) -> Path:
    band_name = f"{composite.band_names[band_index]}_relative_uncertainty"
    return write_tiled_geotiff(
        path,
        grid=composite.grid,
        band_names=(band_name,),
        array=encode_relative_uncertainty(
            composite.uncertainty[band_index : band_index + 1],
            encoding,
        ),
        dtype="uint8",
        nodata=encoding.uncertainty_nodata,
        scales=(1.0,),
        units=("percent",),
        tile_size=tile_size,
    )


def write_tiled_geotiff(
    path: str | Path,
    *,
    grid: GridSpec,
    band_names: Sequence[str],
    array: np.ndarray,
    dtype: str,
    nodata: int,
    scales: Sequence[float],
    units: Sequence[str],
    tile_size: int = 512,
) -> Path:
    try:
        import rasterio
        from rasterio.crs import CRS
        from rasterio.enums import ColorInterp
        from rasterio.shutil import copy as rio_copy
        from rasterio.transform import Affine
    except ImportError as exc:
        raise ImportError(
            "GeoTIFF persistence requires rasterio. Install brdf-monthly-priors with its default dependencies."
        ) from exc

    destination = Path(path).expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.with_suffix(destination.suffix + ".tmp")
    if temp_path.exists():
        temp_path.unlink()
    if destination.exists():
        destination.unlink()

    transform = Affine(*grid.transform_tuple)
    crs = CRS.from_user_input(grid.crs)
    profile = {
        "driver": "GTiff",
        "height": grid.height,
        "width": grid.width,
        "count": int(array.shape[0]),
        "dtype": dtype,
        "crs": crs,
        "transform": transform,
        "nodata": nodata,
        "tiled": True,
        "blockxsize": int(tile_size),
        "blockysize": int(tile_size),
        "compress": "DEFLATE",
        "predictor": 2 if dtype == "uint16" else 1,
        "interleave": "band",
        "bigtiff": "IF_SAFER",
    }
    with rasterio.open(temp_path, "w", **profile) as dataset:
        dataset.write(array.astype(dtype, copy=False))
        dataset.scales = tuple(scales)
        dataset.units = tuple(units)
        dataset.colorinterp = tuple(ColorInterp.gray for _ in band_names)
        for index, band_name in enumerate(band_names, start=1):
            dataset.set_band_description(index, band_name)

    if _has_cog_driver(rasterio):
        try:
            rio_copy(
                temp_path,
                destination,
                driver="COG",
                COMPRESS="DEFLATE",
                BLOCKSIZE=str(tile_size),
                OVERVIEWS="NONE",
                BIGTIFF="IF_SAFER",
            )
            temp_path.unlink()
            return destination
        except Exception:
            if destination.exists():
                destination.unlink()

    os.replace(temp_path, destination)
    return destination


def _has_cog_driver(rasterio_module: object) -> bool:
    try:
        with rasterio_module.Env() as env:
            return "COG" in env.drivers()
    except Exception:
        return False
