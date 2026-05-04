from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence, Union

from brdf_monthly_priors.composite import PriorCompositor
from brdf_monthly_priors.persistence import CompositeStore, stable_json_hash
from brdf_monthly_priors.sources.base import ObservationSource
from brdf_monthly_priors.types import (
    DEFAULT_BANDS,
    DEFAULT_BRDF_CRS,
    GridSpec,
    Observation,
    PriorProduct,
)


def default_cache_dir() -> Path:
    return Path.home() / ".cache" / "brdf-monthly-priors"


@dataclass
class ProviderConfig:
    """Configuration for the BRDF prior provider."""

    cache_dir: Union[str, Path] = field(default_factory=default_cache_dir)
    source: Optional[ObservationSource] = None
    source_name: Optional[str] = None
    compositor: PriorCompositor = field(default_factory=PriorCompositor)
    metadata: Mapping[str, Any] = field(default_factory=dict)


class Provider:
    """Build or retrieve a native-grid BRDF prior product."""

    def __init__(self, config: Optional[ProviderConfig] = None):
        self.config = config or ProviderConfig()
        self.store = CompositeStore(self.config.cache_dir)

    def build_prior(
        self,
        *,
        wgs84_bounds: Sequence[float],
        resolution: float,
        product_id: str,
        brdf_crs: str = DEFAULT_BRDF_CRS,
        band_names: Sequence[str] = DEFAULT_BANDS,
        observations: Optional[Sequence[Observation]] = None,
        rebuild: bool = False,
    ) -> PriorProduct:
        band_names = tuple(str(band) for band in band_names)
        grid = GridSpec.from_wgs84_bounds(
            wgs84_bounds=wgs84_bounds,
            brdf_crs=brdf_crs,
            resolution=resolution,
        )
        request = self._request_payload(grid=grid, product_id=product_id, band_names=band_names)
        request_hash = stable_json_hash(request)
        if not rebuild and self.store.has_product(request_hash):
            return self.store.load(request_hash, request={**request, "request_hash": request_hash})

        if observations is None:
            if self.config.source is None:
                stac_path = self.store.product_dir(request_hash) / "stac-item.json"
                raise RuntimeError(
                    "cache miss and no observations or ObservationSource configured. "
                    f"Configure ProviderConfig(source=...), pass observations=..., or create {stac_path} first."
                )
            observations = self.config.source.load_observations(grid=grid, band_names=band_names)

        composite = self.config.compositor.compose(
            product_id=product_id,
            grid=grid,
            band_names=band_names,
            observations=observations,
        )
        return self.store.save(
            request_hash=request_hash,
            request=request,
            composite=composite,
        )

    def request_hash(
        self,
        *,
        wgs84_bounds: Sequence[float],
        resolution: float,
        product_id: str,
        brdf_crs: str = DEFAULT_BRDF_CRS,
        band_names: Sequence[str] = DEFAULT_BANDS,
    ) -> str:
        grid = GridSpec.from_wgs84_bounds(
            wgs84_bounds=wgs84_bounds,
            brdf_crs=brdf_crs,
            resolution=resolution,
        )
        return stable_json_hash(
            self._request_payload(
                grid=grid,
                product_id=product_id,
                band_names=tuple(str(band) for band in band_names),
            )
        )

    def _request_payload(
        self,
        *,
        grid: GridSpec,
        product_id: str,
        band_names: Sequence[str],
    ) -> dict[str, Any]:
        source_name = self.config.source_name
        if source_name is None:
            source_name = "direct-observations" if self.config.source is None else self.config.source.name
        return {
            "product_id": str(product_id),
            "wgs84_bounds": None if grid.wgs84_bounds is None else list(grid.wgs84_bounds),
            "native_bounds": list(grid.bounds),
            "brdf_crs": grid.crs,
            "resolution": grid.resolution,
            "width": grid.width,
            "height": grid.height,
            "band_names": list(band_names),
            "source": source_name,
            "provider_metadata": dict(self.config.metadata),
        }

    get_prior = build_prior
