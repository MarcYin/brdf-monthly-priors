from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

import numpy as np

SCHEMA_VERSION = "brdf-monthly-priors/v2"
STAC_VERSION = "1.0.0"
PROJECTION_EXTENSION = "https://stac-extensions.github.io/projection/v1.1.0/schema.json"
RASTER_EXTENSION = "https://stac-extensions.github.io/raster/v1.1.0/schema.json"
DEFAULT_SCALE_FACTOR = 10000
DEFAULT_PRIOR_NODATA = 65535
DEFAULT_UNCERTAINTY_NODATA = 255
DEFAULT_BANDS = (
    "brdf_iso_red",
    "brdf_vol_red",
    "brdf_geo_red",
    "brdf_iso_nir",
    "brdf_vol_nir",
    "brdf_geo_nir",
    "brdf_iso_swir1",
    "brdf_vol_swir1",
    "brdf_geo_swir1",
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _tuple_float4(value: Sequence[float]) -> Tuple[float, float, float, float]:
    if len(value) != 4:
        raise ValueError("bounds must contain exactly four values: xmin, ymin, xmax, ymax")
    xmin, ymin, xmax, ymax = (float(v) for v in value)
    if xmax <= xmin or ymax <= ymin:
        raise ValueError("bounds must satisfy xmax > xmin and ymax > ymin")
    return xmin, ymin, xmax, ymax


@dataclass(frozen=True)
class GridSpec:
    """Native processing grid.

    The builder assumes observations are already on this grid. It does not
    reproject MODIS/VIIRS Sinusoidal data or any other source projection.
    """

    bounds: Tuple[float, float, float, float]
    crs: str
    resolution: float
    width: int
    height: int

    @classmethod
    def from_bounds(
        cls,
        bounds: Sequence[float],
        crs: str,
        resolution: float,
    ) -> "GridSpec":
        normalized_bounds = _tuple_float4(bounds)
        if resolution <= 0:
            raise ValueError("resolution must be positive")
        xmin, ymin, xmax, ymax = normalized_bounds
        width = int(np.ceil((xmax - xmin) / float(resolution)))
        height = int(np.ceil((ymax - ymin) / float(resolution)))
        if width <= 0 or height <= 0:
            raise ValueError("bounds and resolution produced an empty grid")
        return cls(
            bounds=normalized_bounds,
            crs=str(crs),
            resolution=float(resolution),
            width=width,
            height=height,
        )

    @property
    def shape(self) -> Tuple[int, int]:
        return self.height, self.width

    @property
    def transform_tuple(self) -> Tuple[float, float, float, float, float, float]:
        xmin, _ymin, _xmax, ymax = self.bounds
        return (self.resolution, 0.0, xmin, 0.0, -self.resolution, ymax)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bounds": list(self.bounds),
            "crs": self.crs,
            "resolution": self.resolution,
            "width": self.width,
            "height": self.height,
            "transform": list(self.transform_tuple),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "GridSpec":
        return cls(
            bounds=_tuple_float4(payload["bounds"]),
            crs=str(payload["crs"]),
            resolution=float(payload["resolution"]),
            width=int(payload["width"]),
            height=int(payload["height"]),
        )


@dataclass(frozen=True)
class Observation:
    """One BRDF observation already aligned to the native processing grid.

    `uncertainty` is relative uncertainty in percent. It may be shaped either
    `(bands, height, width)` or `(height, width)`.
    """

    data: np.ndarray
    quality: np.ndarray
    band_names: Sequence[str] = DEFAULT_BANDS
    uncertainty: Optional[np.ndarray] = None
    sample_index: Optional[np.ndarray] = None
    source_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        data = np.asarray(self.data)
        quality = np.asarray(self.quality)
        band_names = tuple(str(band) for band in self.band_names)
        if data.ndim != 3:
            raise ValueError("observation data must have shape (bands, height, width)")
        if len(band_names) != data.shape[0]:
            raise ValueError("band_names length must match data band dimension")
        if quality.shape != data.shape[1:]:
            raise ValueError("quality must have shape (height, width)")
        sample_index = None if self.sample_index is None else np.asarray(self.sample_index)
        if sample_index is not None and sample_index.shape != quality.shape:
            raise ValueError("sample_index must have shape (height, width)")
        uncertainty = None if self.uncertainty is None else np.asarray(self.uncertainty)
        if uncertainty is not None and uncertainty.shape not in {quality.shape, data.shape}:
            raise ValueError("uncertainty must have shape (height, width) or (bands, height, width)")
        object.__setattr__(self, "data", data)
        object.__setattr__(self, "quality", quality)
        object.__setattr__(self, "band_names", band_names)
        object.__setattr__(self, "uncertainty", uncertainty)
        object.__setattr__(self, "sample_index", sample_index)
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True)
class PriorComposite:
    """Best-pixel BRDF prior composite before GeoTIFF encoding."""

    product_id: str
    grid: GridSpec
    band_names: Sequence[str]
    data: np.ndarray
    uncertainty: np.ndarray
    quality: np.ndarray
    sample_index: np.ndarray
    selected_observation: np.ndarray
    observation_count: np.ndarray
    source_items: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    attrs: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        band_names = tuple(str(band) for band in self.band_names)
        data = np.asarray(self.data)
        uncertainty = np.asarray(self.uncertainty)
        quality = np.asarray(self.quality)
        sample_index = np.asarray(self.sample_index)
        selected_observation = np.asarray(self.selected_observation)
        observation_count = np.asarray(self.observation_count)
        if data.ndim != 3:
            raise ValueError("composite data must have shape (bands, height, width)")
        if uncertainty.shape != data.shape:
            raise ValueError("uncertainty must have shape (bands, height, width)")
        if data.shape[0] != len(band_names):
            raise ValueError("band_names length must match data band dimension")
        expected_shape = self.grid.shape
        for name, array in {
            "quality": quality,
            "sample_index": sample_index,
            "selected_observation": selected_observation,
            "observation_count": observation_count,
        }.items():
            if array.shape != expected_shape:
                raise ValueError(f"{name} must have shape {expected_shape}")
        if data.shape[1:] != expected_shape:
            raise ValueError(f"data must have shape (bands, {expected_shape[0]}, {expected_shape[1]})")
        object.__setattr__(self, "band_names", band_names)
        object.__setattr__(self, "data", data)
        object.__setattr__(self, "uncertainty", uncertainty)
        object.__setattr__(self, "quality", quality)
        object.__setattr__(self, "sample_index", sample_index)
        object.__setattr__(self, "selected_observation", selected_observation)
        object.__setattr__(self, "observation_count", observation_count)
        object.__setattr__(self, "source_items", tuple(dict(item) for item in self.source_items))
        object.__setattr__(self, "attrs", dict(self.attrs))


@dataclass(frozen=True)
class PriorProduct:
    """Persisted BRDF prior product represented as a STAC Item."""

    request: Mapping[str, Any]
    grid: GridSpec
    composite: PriorComposite
    stac_item: Mapping[str, Any]
    output_dir: str
    schema_version: str = SCHEMA_VERSION
    created_at: str = field(default_factory=utc_now_iso)
    package_version: str = "unknown"

    def __post_init__(self) -> None:
        object.__setattr__(self, "request", dict(self.request))
        object.__setattr__(self, "stac_item", dict(self.stac_item))

    def __iter__(self) -> Iterable[PriorComposite]:
        return iter((self.composite,))

    def manifest(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "package_version": self.package_version,
            "created_at": self.created_at,
            "request": dict(self.request),
            "grid": self.grid.to_dict(),
            "stac_item": dict(self.stac_item),
        }

