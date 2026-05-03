from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence, Union

from brdf_monthly_priors._version import __version__
from brdf_monthly_priors.composite import MonthlyCompositor
from brdf_monthly_priors.periods import plan_monthly_periods
from brdf_monthly_priors.persistence import CompositeStore, stable_json_hash
from brdf_monthly_priors.sources.base import ObservationSource
from brdf_monthly_priors.types import (
    DEFAULT_BANDS,
    GridSpec,
    MonthlyCompositeCollection,
    parse_date,
    utc_now_iso,
)


def default_cache_dir() -> Path:
    return Path.home() / ".cache" / "brdf-monthly-priors"


@dataclass
class ProviderConfig:
    """Configuration for the monthly BRDF prior provider."""

    cache_dir: Union[str, Path] = field(default_factory=default_cache_dir)
    source: Optional[ObservationSource] = None
    source_name: Optional[str] = None
    compositor: MonthlyCompositor = field(default_factory=MonthlyCompositor)
    metadata: Mapping[str, Any] = field(default_factory=dict)


class Provider:
    """Build or retrieve monthly BRDF prior composites."""

    def __init__(self, config: Optional[ProviderConfig] = None):
        self.config = config or ProviderConfig()
        self.store = CompositeStore(self.config.cache_dir)

    def get_monthly_composites(
        self,
        *,
        bounds: Sequence[float],
        crs: str,
        observation_date: Union[date, str],
        resolution: float,
        months_window: Sequence[int] = (-1, 0, 1),
        history_years: int = 5,
        band_names: Sequence[str] = DEFAULT_BANDS,
        rebuild: bool = False,
    ) -> MonthlyCompositeCollection:
        observation_date = parse_date(observation_date)
        band_names = tuple(str(band) for band in band_names)
        grid = GridSpec.from_bounds(bounds=bounds, crs=crs, resolution=resolution)
        request = self._request_payload(
            grid=grid,
            observation_date=observation_date,
            months_window=months_window,
            history_years=history_years,
            band_names=band_names,
        )
        request_hash = stable_json_hash(request)
        if not rebuild and self.store.has_collection(request_hash):
            return self.store.load(request_hash)

        if self.config.source is None:
            manifest = self.store.collection_dir(request_hash) / "manifest.json"
            raise RuntimeError(
                "cache miss and no ObservationSource configured. "
                f"Configure ProviderConfig(source=...) or create {manifest} first."
            )

        periods = plan_monthly_periods(
            observation_date=observation_date,
            months_window=months_window,
            history_years=history_years,
        )
        composites = []
        for period in periods:
            observations = self.config.source.load_observations(
                period=period,
                grid=grid,
                band_names=band_names,
            )
            composites.append(
                self.config.compositor.compose(
                    period=period,
                    grid=grid,
                    band_names=band_names,
                    observations=observations,
                    preferred_date=observation_date,
                )
            )

        collection = MonthlyCompositeCollection(
            request={**request, "request_hash": request_hash},
            grid=grid,
            composites=tuple(composites),
            created_at=utc_now_iso(),
            package_version=__version__,
        )
        self.store.save(request_hash, collection)
        return collection

    def request_hash(
        self,
        *,
        bounds: Sequence[float],
        crs: str,
        observation_date: Union[date, str],
        resolution: float,
        months_window: Sequence[int] = (-1, 0, 1),
        history_years: int = 5,
        band_names: Sequence[str] = DEFAULT_BANDS,
    ) -> str:
        grid = GridSpec.from_bounds(bounds=bounds, crs=crs, resolution=resolution)
        request = self._request_payload(
            grid=grid,
            observation_date=parse_date(observation_date),
            months_window=months_window,
            history_years=history_years,
            band_names=tuple(str(band) for band in band_names),
        )
        return stable_json_hash(request)

    def _request_payload(
        self,
        *,
        grid: GridSpec,
        observation_date: date,
        months_window: Sequence[int],
        history_years: int,
        band_names: Sequence[str],
    ) -> dict[str, Any]:
        source_name = self.config.source_name
        if source_name is None:
            source_name = "default" if self.config.source is None else self.config.source.name
        return {
            "bounds": list(grid.bounds),
            "crs": grid.crs,
            "resolution": grid.resolution,
            "width": grid.width,
            "height": grid.height,
            "observation_date": observation_date.isoformat(),
            "months_window": [int(value) for value in months_window],
            "history_years": int(history_years),
            "band_names": list(band_names),
            "source": source_name,
            "provider_metadata": dict(self.config.metadata),
        }
