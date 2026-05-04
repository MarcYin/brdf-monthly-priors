from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Sequence

import numpy as np

from surface_priors.sources.earthaccess import FetchedGranule
from surface_priors.types import GridSpec, Observation


@dataclass(frozen=True)
class NativeRasterioStackReader:
    """Read native-projection raster products by matching GDAL subdataset names.

    This reader never reprojects. Source rasters must already match the target
    grid shape and CRS.
    """

    band_patterns: Mapping[str, str]
    quality_pattern: str
    sample_index_pattern: Optional[str] = None
    uncertainty_patterns: Optional[Mapping[str, str]] = None
    scale_factor: float = 1.0
    nodata: Optional[float] = None

    def read(
        self,
        *,
        granules: Sequence[FetchedGranule],
        grid: GridSpec,
        band_names: Sequence[str],
    ) -> Sequence[Observation]:
        try:
            import rasterio
        except ImportError as exc:
            raise ImportError(
                "NativeRasterioStackReader requires rasterio. "
                "Install surface-priors with its default dependencies."
            ) from exc

        observations = []
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
                uncertainty_sources = None
                if self.uncertainty_patterns is not None:
                    uncertainty_sources = [
                        _find_dataset(dataset_lookup, self.uncertainty_patterns[band])
                        for band in band_names
                    ]
            except KeyError:
                continue

            data = np.empty((len(band_names), grid.height, grid.width), dtype="float32")
            for index, source in enumerate(band_sources):
                data[index] = _read_native(
                    source=source,
                    grid=grid,
                    dtype="float32",
                    nodata=self.nodata,
                )
                data[index] *= self.scale_factor
            quality = _read_native(source=quality_source, grid=grid, dtype="uint16", nodata=None)
            sample_index = None
            if sample_source is not None:
                sample_index = _read_native(source=sample_source, grid=grid, dtype="int16", nodata=None)
            uncertainty = None
            if uncertainty_sources is not None:
                uncertainty = np.empty((len(band_names), grid.height, grid.width), dtype="float32")
                for index, source in enumerate(uncertainty_sources):
                    uncertainty[index] = _read_native(source=source, grid=grid, dtype="float32", nodata=None)
            observations.append(
                Observation(
                    data=data,
                    quality=quality,
                    uncertainty=uncertainty,
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


RasterioStackReader = NativeRasterioStackReader


def _find_dataset(datasets: Mapping[str, str], pattern: str) -> str:
    pattern_lower = pattern.lower()
    for name, value in datasets.items():
        if pattern_lower in name.lower():
            return value
    raise KeyError(pattern)


def _read_native(
    *,
    source: str,
    grid: GridSpec,
    dtype: str,
    nodata: Optional[float],
) -> np.ndarray:
    import rasterio

    with rasterio.open(source) as dataset:
        if dataset.width != grid.width or dataset.height != grid.height:
            raise ValueError(
                f"{source} has shape {(dataset.height, dataset.width)}, expected {grid.shape}"
            )
        if dataset.crs and dataset.crs.to_string() != rasterio.crs.CRS.from_user_input(grid.crs).to_string():
            raise ValueError(f"{source} CRS {dataset.crs} does not match native grid CRS {grid.crs}")
        source_array = dataset.read(1).astype(dtype, copy=False)
        if nodata is not None:
            source_array = np.where(source_array == nodata, np.nan, source_array)
        return source_array

