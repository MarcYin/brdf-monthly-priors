from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Optional, Protocol, Sequence, Tuple, Union

from brdf_monthly_priors.periods import MonthlyPeriod
from brdf_monthly_priors.types import GridSpec, Observation


@dataclass(frozen=True)
class EarthdataCollection:
    """NASA Earthdata collection used by an Earthaccess source."""

    short_name: str
    version: Optional[str] = None
    provider: Optional[str] = None


@dataclass(frozen=True)
class FetchedGranule:
    """Downloaded Earthdata granule metadata."""

    path: Path
    collection: EarthdataCollection
    acquired: Optional[date] = None
    granule_id: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)


class ProductReader(Protocol):
    """Reads downloaded granules into grid-aligned observations."""

    def read(
        self,
        *,
        granules: Sequence[FetchedGranule],
        period: MonthlyPeriod,
        grid: GridSpec,
        band_names: Sequence[str],
    ) -> Sequence[Observation]:
        """Return observations from downloaded product files."""


class EarthaccessSource:
    """Fetch/cache NASA Earthdata BRDF products with lazy Earthaccess imports."""

    def __init__(
        self,
        *,
        collections: Sequence[EarthdataCollection],
        cache_dir: Union[str, Path],
        reader: ProductReader,
        name: str = "earthaccess",
        login_strategy: str = "netrc",
    ):
        if not collections:
            raise ValueError("at least one EarthdataCollection is required")
        self.collections = tuple(collections)
        self.cache_dir = Path(cache_dir).expanduser().resolve()
        self.reader = reader
        self._name = name
        self.login_strategy = login_strategy

    @property
    def name(self) -> str:
        return self._name

    def load_observations(
        self,
        *,
        period: MonthlyPeriod,
        grid: GridSpec,
        band_names: Sequence[str],
    ) -> Sequence[Observation]:
        granules = self.fetch(period=period, grid=grid)
        return self.reader.read(
            granules=granules,
            period=period,
            grid=grid,
            band_names=band_names,
        )

    def fetch(self, *, period: MonthlyPeriod, grid: GridSpec) -> Sequence[FetchedGranule]:
        try:
            import earthaccess
        except ImportError as exc:
            raise ImportError(
                "EarthaccessSource requires the 'earthdata' extra: "
                "pip install 'brdf-monthly-priors[earthdata]'"
            ) from exc

        earthaccess.login(strategy=self.login_strategy)
        bbox = _bounds_to_wgs84(grid.bounds, grid.crs)
        fetched = []
        for collection in self.collections:
            collection_dir = self.cache_dir / collection.short_name
            collection_dir.mkdir(parents=True, exist_ok=True)
            for start, end in period.temporal_ranges:
                results = earthaccess.search_data(
                    short_name=collection.short_name,
                    version=collection.version,
                    provider=collection.provider,
                    bounding_box=bbox,
                    temporal=(start.isoformat(), end.isoformat()),
                )
                paths = earthaccess.download(results, local_path=str(collection_dir))
                for result, path in zip(results, paths):
                    fetched.append(
                        FetchedGranule(
                            path=Path(path),
                            collection=collection,
                            acquired=_date_from_result(result),
                            granule_id=_granule_id(result),
                            metadata={"temporal_start": start.isoformat(), "temporal_end": end.isoformat()},
                        )
                    )
        return tuple(fetched)


def _bounds_to_wgs84(
    bounds: Tuple[float, float, float, float],
    crs: str,
) -> Tuple[float, float, float, float]:
    if crs.upper() in {"EPSG:4326", "OGC:CRS84", "CRS84"}:
        return tuple(float(value) for value in bounds)
    try:
        from pyproj import Transformer
    except ImportError as exc:
        raise ImportError(
            "Non-WGS84 Earthdata searches require pyproj. Install the 'earthdata' extra."
        ) from exc
    transformer = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    return transformer.transform_bounds(*bounds, densify_pts=21)


def _date_from_result(result: Any) -> Optional[date]:
    umm = getattr(result, "umm", None)
    if isinstance(umm, Mapping):
        temporal = umm.get("TemporalExtent", {})
        ranges = temporal.get("RangeDateTime", {}) if isinstance(temporal, Mapping) else {}
        start = ranges.get("BeginningDateTime") if isinstance(ranges, Mapping) else None
        if isinstance(start, str) and len(start) >= 10:
            return date.fromisoformat(start[:10])
    return None


def _granule_id(result: Any) -> str:
    for attribute in ("granule_id", "producer_granule_id"):
        value = getattr(result, attribute, None)
        if value:
            return str(value)
    umm = getattr(result, "umm", None)
    if isinstance(umm, Mapping):
        value = umm.get("GranuleUR") or umm.get("ProducerGranuleId")
        if value:
            return str(value)
    return ""


def product_collections(product: str) -> Tuple[EarthdataCollection, ...]:
    normalized = product.lower()
    if normalized == "mcd43":
        return (
            EarthdataCollection("MCD43A1", version="061"),
            EarthdataCollection("MCD43A2", version="061"),
        )
    if normalized == "vnp43":
        return (
            EarthdataCollection("VNP43IA1", version="001"),
            EarthdataCollection("VNP43IA2", version="001"),
        )
    if normalized == "mcd19":
        return (
            EarthdataCollection("MCD19A3", version="061"),
        )
    raise ValueError("product must be one of: mcd43, vnp43, mcd19")
