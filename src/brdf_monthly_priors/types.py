from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple, Union

import numpy as np

SCHEMA_VERSION = "brdf-monthly-priors/v1"
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


def parse_date(value: Union[date, str]) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def _tuple_float4(value: Sequence[float]) -> Tuple[float, float, float, float]:
    if len(value) != 4:
        raise ValueError("bounds must contain exactly four values: xmin, ymin, xmax, ymax")
    xmin, ymin, xmax, ymax = (float(v) for v in value)
    if xmax <= xmin or ymax <= ymin:
        raise ValueError("bounds must satisfy xmax > xmin and ymax > ymin")
    return xmin, ymin, xmax, ymax


@dataclass(frozen=True)
class GridSpec:
    """Target grid definition used for neutral composite products."""

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
    """One BRDF product observation already aligned to a target grid."""

    acquired: Union[date, str]
    data: np.ndarray
    quality: np.ndarray
    band_names: Sequence[str] = DEFAULT_BANDS
    sample_index: Optional[np.ndarray] = None
    source_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        acquired = parse_date(self.acquired)
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
        object.__setattr__(self, "acquired", acquired)
        object.__setattr__(self, "data", data)
        object.__setattr__(self, "quality", quality)
        object.__setattr__(self, "band_names", band_names)
        object.__setattr__(self, "sample_index", sample_index)
        object.__setattr__(self, "metadata", dict(self.metadata))

    @property
    def height(self) -> int:
        return int(self.data.shape[1])

    @property
    def width(self) -> int:
        return int(self.data.shape[2])


@dataclass(frozen=True)
class MonthlyComposite:
    """Best-pixel monthly composite for one requested month."""

    month_start: Union[date, str]
    month_end: Union[date, str]
    history_months: Sequence[Union[date, str]]
    grid: GridSpec
    band_names: Sequence[str]
    data: np.ndarray
    quality: np.ndarray
    sample_index: np.ndarray
    selected_observation: np.ndarray
    observation_count: np.ndarray
    source_items: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    attrs: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        month_start = parse_date(self.month_start)
        month_end = parse_date(self.month_end)
        history_months = tuple(parse_date(value) for value in self.history_months)
        band_names = tuple(str(band) for band in self.band_names)
        data = np.asarray(self.data)
        quality = np.asarray(self.quality)
        sample_index = np.asarray(self.sample_index)
        selected_observation = np.asarray(self.selected_observation)
        observation_count = np.asarray(self.observation_count)
        if data.ndim != 3:
            raise ValueError("composite data must have shape (bands, height, width)")
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
        object.__setattr__(self, "month_start", month_start)
        object.__setattr__(self, "month_end", month_end)
        object.__setattr__(self, "history_months", history_months)
        object.__setattr__(self, "band_names", band_names)
        object.__setattr__(self, "data", data)
        object.__setattr__(self, "quality", quality)
        object.__setattr__(self, "sample_index", sample_index)
        object.__setattr__(self, "selected_observation", selected_observation)
        object.__setattr__(self, "observation_count", observation_count)
        object.__setattr__(self, "source_items", tuple(dict(item) for item in self.source_items))
        object.__setattr__(self, "attrs", dict(self.attrs))

    @property
    def month_key(self) -> str:
        return self.month_start.strftime("%Y-%m")

    def manifest_entry(self, array_path: Optional[str] = None) -> Dict[str, Any]:
        entry: Dict[str, Any] = {
            "month": self.month_key,
            "month_start": self.month_start.isoformat(),
            "month_end": self.month_end.isoformat(),
            "history_months": [value.isoformat() for value in self.history_months],
            "band_names": list(self.band_names),
            "data_dtype": str(self.data.dtype),
            "quality_dtype": str(self.quality.dtype),
            "sample_index_dtype": str(self.sample_index.dtype),
            "shape": list(self.data.shape),
            "valid_pixels": int(np.count_nonzero(self.observation_count)),
            "source_items": list(self.source_items),
            "attrs": dict(self.attrs),
        }
        if array_path is not None:
            entry["array_path"] = array_path
        return entry


@dataclass(frozen=True)
class MonthlyCompositeCollection:
    """Schema-versioned collection returned by the provider."""

    request: Mapping[str, Any]
    grid: GridSpec
    composites: Sequence[MonthlyComposite]
    schema_version: str = SCHEMA_VERSION
    created_at: str = field(default_factory=utc_now_iso)
    package_version: str = "unknown"

    def __post_init__(self) -> None:
        composites = tuple(self.composites)
        object.__setattr__(self, "request", dict(self.request))
        object.__setattr__(self, "composites", composites)

    def __len__(self) -> int:
        return len(self.composites)

    def __iter__(self) -> Iterable[MonthlyComposite]:
        return iter(self.composites)

    def composite_for_month(self, month: Union[date, str]) -> MonthlyComposite:
        month_date = parse_date(f"{month}-01") if isinstance(month, str) and len(month) == 7 else parse_date(month)
        month_key = month_date.strftime("%Y-%m")
        for composite in self.composites:
            if composite.month_key == month_key:
                return composite
        raise KeyError(f"no composite for month {month_key}")

    def manifest(self, array_paths: Optional[Mapping[str, str]] = None) -> Dict[str, Any]:
        array_paths = {} if array_paths is None else dict(array_paths)
        return {
            "schema_version": self.schema_version,
            "package_version": self.package_version,
            "created_at": self.created_at,
            "request": dict(self.request),
            "grid": self.grid.to_dict(),
            "composites": [
                composite.manifest_entry(array_paths.get(composite.month_key))
                for composite in self.composites
            ],
        }
