from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Optional, Union

import numpy as np

from brdf_monthly_priors._version import __version__
from brdf_monthly_priors.encoding import decode_prior, decode_relative_uncertainty
from brdf_monthly_priors.geotiff import write_prior_geotiff, write_uncertainty_geotiff
from brdf_monthly_priors.stac import build_stac_item, normalize_href
from brdf_monthly_priors.types import (
    DEFAULT_PRIOR_NODATA,
    SCHEMA_VERSION,
    GridSpec,
    PriorComposite,
    PriorProduct,
    utc_now_iso,
)

STAC_ITEM_NAME = "stac-item.json"


def stable_json_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:24]


class CompositeStore:
    """File-system store for STAC Item BRDF prior products."""

    def __init__(self, root: Union[str, Path]):
        self.root = Path(root).expanduser().resolve()

    def product_dir(self, request_hash: str) -> Path:
        return self.root / request_hash

    def has_product(self, request_hash: str) -> bool:
        return (self.product_dir(request_hash) / STAC_ITEM_NAME).exists()

    def save(
        self,
        *,
        request_hash: str,
        request: Mapping[str, Any],
        composite: PriorComposite,
    ) -> PriorProduct:
        destination = self.product_dir(request_hash)
        assets_dir = destination / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        prior_path = write_prior_geotiff(assets_dir / "prior.tif", composite=composite)
        uncertainty_path = write_uncertainty_geotiff(
            assets_dir / "uncertainty.tif",
            composite=composite,
        )
        created_at = utc_now_iso()
        stac_item = build_stac_item(
            composite=composite,
            request_hash=request_hash,
            prior_href=normalize_href(prior_path, destination),
            uncertainty_href=normalize_href(uncertainty_path, destination),
            created_at=created_at,
        )
        stac_item["properties"]["brdf:schema_version"] = SCHEMA_VERSION
        stac_item["properties"]["brdf:package_version"] = __version__
        stac_item["properties"]["brdf:source_items"] = list(composite.source_items)
        stac_item["properties"]["brdf:attrs"] = dict(composite.attrs)
        with (destination / STAC_ITEM_NAME).open("w", encoding="utf-8") as handle:
            json.dump(stac_item, handle, indent=2, sort_keys=True)
            handle.write("\n")
        return PriorProduct(
            request={**dict(request), "request_hash": request_hash},
            grid=composite.grid,
            composite=composite,
            stac_item=stac_item,
            output_dir=str(destination),
            created_at=created_at,
            package_version=__version__,
        )

    def load(self, request_hash: str, request: Optional[Mapping[str, Any]] = None) -> PriorProduct:
        source = self.product_dir(request_hash)
        stac_path = source / STAC_ITEM_NAME
        if not stac_path.exists():
            raise FileNotFoundError(f"no STAC item at {stac_path}")
        return load_product(source, request=request)


def load_product(path: Union[str, Path], request: Optional[Mapping[str, Any]] = None) -> PriorProduct:
    try:
        import rasterio
    except ImportError as exc:
        raise ImportError("Loading persisted GeoTIFF products requires rasterio.") from exc

    source = Path(path).expanduser().resolve()
    with (source / STAC_ITEM_NAME).open("r", encoding="utf-8") as handle:
        stac_item = json.load(handle)
    if stac_item["properties"].get("brdf:schema_version") != SCHEMA_VERSION:
        raise ValueError(
            "unsupported schema version "
            f"{stac_item['properties'].get('brdf:schema_version')!r}; expected {SCHEMA_VERSION!r}"
        )

    prior_path = source / stac_item["assets"]["prior"]["href"]
    uncertainty_path = source / stac_item["assets"]["uncertainty"]["href"]
    with rasterio.open(prior_path) as prior_dataset:
        prior_encoded = prior_dataset.read()
        grid = GridSpec(
            bounds=tuple(float(value) for value in stac_item["proj:bbox"]),
            crs=prior_dataset.crs.to_wkt() if prior_dataset.crs else stac_item["proj:wkt2"],
            resolution=abs(float(prior_dataset.transform.a)),
            width=prior_dataset.width,
            height=prior_dataset.height,
        )
        band_names = tuple(prior_dataset.descriptions)
    with rasterio.open(uncertainty_path) as uncertainty_dataset:
        uncertainty_encoded = uncertainty_dataset.read()

    data = decode_prior(prior_encoded)
    uncertainty = decode_relative_uncertainty(uncertainty_encoded)
    shape = grid.shape
    composite = PriorComposite(
        product_id=stac_item["id"],
        grid=grid,
        band_names=band_names,
        data=data,
        uncertainty=uncertainty,
        quality=np.full(shape, DEFAULT_PRIOR_NODATA, dtype="uint16"),
        sample_index=np.full(shape, -1, dtype="int16"),
        selected_observation=np.full(shape, -1, dtype="int16"),
        observation_count=np.zeros(shape, dtype="uint16"),
        source_items=stac_item["properties"].get("brdf:source_items", ()),
        attrs=stac_item["properties"].get("brdf:attrs", {}),
    )
    request_payload = {} if request is None else dict(request)
    request_payload.setdefault("request_hash", stac_item["properties"]["brdf:request_hash"])
    return PriorProduct(
        request=request_payload,
        grid=grid,
        composite=composite,
        stac_item=stac_item,
        output_dir=str(source),
        package_version=stac_item["properties"].get("brdf:package_version", "unknown"),
    )


def stac_item_path(path: Union[str, Path], request_hash: Optional[str] = None) -> Path:
    base = Path(path).expanduser().resolve()
    if request_hash is not None:
        base = base / request_hash
    return base / STAC_ITEM_NAME


manifest_path = stac_item_path

