from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence, Union

from surface_priors.composite import PriorCompositor
from surface_priors.persistence import CompositeStore, stable_json_hash
from surface_priors.sources.base import ObservationSource
from surface_priors.types import (
    DEFAULT_BANDS,
    DEFAULT_NATIVE_CRS,
    GridSpec,
    Observation,
    PriorProduct,
)


def default_cache_dir() -> Path:
    return Path.home() / ".cache" / "surface-priors"


@dataclass
class ProviderConfig:
    """Configuration for a surface prior provider."""

    cache_dir: Union[str, Path] = field(default_factory=default_cache_dir)
    source: Optional[ObservationSource] = None
    source_name: Optional[str] = None
    compositor: PriorCompositor = field(default_factory=PriorCompositor)
    metadata: Mapping[str, Any] = field(default_factory=dict)


class Provider:
    """Build or retrieve a native-grid surface prior product."""

    def __init__(self, config: Optional[ProviderConfig] = None):
        self.config = config or ProviderConfig()
        self.store = CompositeStore(self.config.cache_dir)

    def build_prior(
        self,
        *,
        wgs84_bounds: Sequence[float],
        resolution: float,
        product_id: str,
        native_crs: str = DEFAULT_NATIVE_CRS,
        brdf_crs: Optional[str] = None,
        band_names: Sequence[str] = DEFAULT_BANDS,
        composite_period: Optional[str] = None,
        observations: Optional[Sequence[Observation]] = None,
        rebuild: bool = False,
    ) -> PriorProduct:
        crs = native_crs if brdf_crs is None else brdf_crs
        band_names = tuple(str(band) for band in band_names)
        grid = self._grid_for_request(
            wgs84_bounds=wgs84_bounds,
            native_crs=crs,
            resolution=resolution,
            band_names=band_names,
        )
        request = self._request_payload(
            grid=grid,
            product_id=product_id,
            band_names=band_names,
            composite_period=composite_period,
        )
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
        native_crs: str = DEFAULT_NATIVE_CRS,
        brdf_crs: Optional[str] = None,
        band_names: Sequence[str] = DEFAULT_BANDS,
        composite_period: Optional[str] = None,
    ) -> str:
        crs = native_crs if brdf_crs is None else brdf_crs
        band_names = tuple(str(band) for band in band_names)
        grid = self._grid_for_request(
            wgs84_bounds=wgs84_bounds,
            native_crs=crs,
            resolution=resolution,
            band_names=band_names,
        )
        return stable_json_hash(
            self._request_payload(
                grid=grid,
                product_id=product_id,
                band_names=band_names,
                composite_period=composite_period,
            )
        )

    def _grid_for_request(
        self,
        *,
        wgs84_bounds: Sequence[float],
        native_crs: str,
        resolution: float,
        band_names: Sequence[str],
    ) -> GridSpec:
        if self.config.source is not None:
            resolver = getattr(self.config.source, "resolve_grid", None)
            if callable(resolver):
                crs_key = _native_crs_parameter_name(resolver)
                return resolver(
                    wgs84_bounds=wgs84_bounds,
                    **{crs_key: native_crs},
                    resolution=resolution,
                    band_names=band_names,
                )
        return GridSpec.from_wgs84_bounds(
            wgs84_bounds=wgs84_bounds,
            native_crs=native_crs,
            resolution=resolution,
        )

    def _request_payload(
        self,
        *,
        grid: GridSpec,
        product_id: str,
        band_names: Sequence[str],
        composite_period: Optional[str],
    ) -> dict[str, Any]:
        source_name = self.config.source_name
        if source_name is None:
            source_name = "direct-observations" if self.config.source is None else self.config.source.name
        payload: dict[str, Any] = {
            "product_id": str(product_id),
            "wgs84_bounds": None if grid.wgs84_bounds is None else list(grid.wgs84_bounds),
            "native_bounds": list(grid.bounds),
            "native_crs": grid.crs,
            "resolution": grid.resolution,
            "width": grid.width,
            "height": grid.height,
            "band_names": list(band_names),
            "source": source_name,
            "provider_metadata": dict(self.config.metadata),
        }
        if composite_period is not None:
            payload["composite_period"] = str(composite_period)
        return payload

    get_prior = build_prior


def _native_crs_parameter_name(resolver: Any) -> str:
    """Choose the source grid resolver CRS keyword with legacy compatibility."""

    try:
        parameters = inspect.signature(resolver).parameters
    except (TypeError, ValueError):
        return "native_crs"
    if "native_crs" in parameters:
        return "native_crs"
    if "brdf_crs" in parameters:
        return "brdf_crs"
    return "native_crs"
