from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Mapping, Optional, Sequence

import numpy as np

from brdf_monthly_priors.periods import MonthlyPeriod
from brdf_monthly_priors.sources.earthaccess import FetchedGranule
from brdf_monthly_priors.types import GridSpec, Observation


@dataclass(frozen=True)
class RasterioStackReader:
    """Read single-file raster products by matching GDAL subdataset names.

    This reader handles products where the requested BRDF bands, quality band,
    and optional sample-index band are available in the same raster container.
    MCD43/VNP43 pairings that split parameters and quality across collections
    can use the same `ProductReader` protocol with a project-specific reader.
    """

    band_patterns: Mapping[str, str]
    quality_pattern: str
    sample_index_pattern: Optional[str] = None
    scale_factor: float = 1.0
    nodata: Optional[float] = None

    def read(
        self,
        *,
        granules: Sequence[FetchedGranule],
        period: MonthlyPeriod,
        grid: GridSpec,
        band_names: Sequence[str],
    ) -> Sequence[Observation]:
        del period
        try:
            import rasterio
            from rasterio.transform import Affine
            from rasterio.warp import Resampling, reproject
        except ImportError as exc:
            raise ImportError(
                "RasterioStackReader requires the 'raster' extra: "
                "pip install 'brdf-monthly-priors[raster]'"
            ) from exc

        observations = []
        dst_transform = Affine(*grid.transform_tuple)
        dst_crs = grid.crs
        for granule in granules:
            with rasterio.open(granule.path) as container:
                subdatasets = list(container.subdatasets)
            if subdatasets:
                dataset_lookup = {name: name for name in subdatasets}
            else:
                dataset_lookup = {str(granule.path): str(granule.path)}

            try:
                band_sources = [
                    _find_dataset(dataset_lookup, self.band_patterns[band]) for band in band_names
                ]
                quality_source = _find_dataset(dataset_lookup, self.quality_pattern)
                sample_source = (
                    None
                    if self.sample_index_pattern is None
                    else _find_dataset(dataset_lookup, self.sample_index_pattern)
                )
            except KeyError:
                continue

            data = np.empty((len(band_names), grid.height, grid.width), dtype="float32")
            for index, source in enumerate(band_sources):
                data[index] = _read_reprojected(
                    source=source,
                    shape=grid.shape,
                    dst_transform=dst_transform,
                    dst_crs=dst_crs,
                    resampling=Resampling.bilinear,
                    dtype="float32",
                    reproject=reproject,
                    nodata=self.nodata,
                )
                data[index] *= self.scale_factor
            quality = _read_reprojected(
                source=quality_source,
                shape=grid.shape,
                dst_transform=dst_transform,
                dst_crs=dst_crs,
                resampling=Resampling.nearest,
                dtype="uint16",
                reproject=reproject,
                nodata=None,
            )
            sample_index = None
            if sample_source is not None:
                sample_index = _read_reprojected(
                    source=sample_source,
                    shape=grid.shape,
                    dst_transform=dst_transform,
                    dst_crs=dst_crs,
                    resampling=Resampling.nearest,
                    dtype="int16",
                    reproject=reproject,
                    nodata=None,
                )
            observations.append(
                Observation(
                    acquired=granule.acquired or date(1900, 1, 1),
                    data=data,
                    quality=quality,
                    sample_index=sample_index,
                    band_names=band_names,
                    source_id=granule.granule_id or granule.path.name,
                    metadata={
                        "path": str(granule.path),
                        "collection": granule.collection.short_name,
                    },
                )
            )
        return tuple(observations)


def _find_dataset(datasets: Mapping[str, str], pattern: str) -> str:
    pattern_lower = pattern.lower()
    for name, value in datasets.items():
        if pattern_lower in name.lower():
            return value
    raise KeyError(pattern)


def _read_reprojected(
    *,
    source: str,
    shape: tuple[int, int],
    dst_transform: object,
    dst_crs: str,
    resampling: object,
    dtype: str,
    reproject: object,
    nodata: Optional[float],
) -> np.ndarray:
    import rasterio

    destination = np.zeros(shape, dtype=dtype)
    with rasterio.open(source) as dataset:
        source_array = dataset.read(1)
        if nodata is not None:
            source_array = np.where(source_array == nodata, np.nan, source_array)
        reproject(
            source_array,
            destination,
            src_transform=dataset.transform,
            src_crs=dataset.crs,
            dst_transform=dst_transform,
            dst_crs=dst_crs,
            resampling=resampling,
        )
    return destination
