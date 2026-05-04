from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from brdf_monthly_priors.types import (
    PROJECTION_EXTENSION,
    RASTER_EXTENSION,
    STAC_VERSION,
    GridSpec,
    PriorComposite,
    utc_now_iso,
)


def build_stac_item(
    *,
    composite: PriorComposite,
    request_hash: str,
    prior_href: str,
    uncertainty_href: str,
    created_at: Optional[str] = None,
) -> Dict[str, Any]:
    grid = composite.grid
    geometry, bbox = _wgs84_geometry_and_bbox(grid)
    item: Dict[str, Any] = {
        "type": "Feature",
        "stac_version": STAC_VERSION,
        "stac_extensions": [PROJECTION_EXTENSION, RASTER_EXTENSION],
        "id": composite.product_id,
        "geometry": geometry,
        "properties": {
            "datetime": None,
            "created": created_at or utc_now_iso(),
            "brdf:request_hash": request_hash,
            "brdf:schema_version": "brdf-monthly-priors/v2",
            "brdf:compositor": composite.attrs.get("compositor", "best_pixel_v2"),
            "brdf:source_count": len(composite.source_items),
        },
        "links": [],
        "assets": {
            "prior": _prior_asset(prior_href, composite.band_names),
            "uncertainty": _uncertainty_asset(uncertainty_href, composite.band_names),
        },
        "proj:shape": [grid.height, grid.width],
        "proj:transform": list(grid.transform_tuple),
        "proj:bbox": list(grid.bounds),
        "proj:wkt2": grid.crs,
    }
    if bbox is not None:
        item["bbox"] = bbox
    return item


def normalize_href(path: str | Path, root: str | Path) -> str:
    path = Path(path).resolve()
    root = Path(root).resolve()
    try:
        return str(path.relative_to(root))
    except ValueError:
        return path.as_uri()


def _prior_asset(href: str, band_names: Sequence[str]) -> Dict[str, Any]:
    return {
        "href": href,
        "type": "image/tiff; application=geotiff; profile=cloud-optimized",
        "title": "Scaled BRDF prior",
        "roles": ["data"],
        "raster:bands": [
            {
                "name": band_name,
                "data_type": "uint16",
                "scale": 0.0001,
                "nodata": 65535,
            }
            for band_name in band_names
        ],
    }


def _uncertainty_asset(href: str, band_names: Sequence[str]) -> Dict[str, Any]:
    return {
        "href": href,
        "type": "image/tiff; application=geotiff; profile=cloud-optimized",
        "title": "Relative BRDF prior uncertainty",
        "roles": ["metadata", "uncertainty"],
        "raster:bands": [
            {
                "name": f"{band_name}_relative_uncertainty",
                "data_type": "uint8",
                "unit": "percent",
                "nodata": 255,
                "statistics": {"minimum": 0, "maximum": 200},
            }
            for band_name in band_names
        ],
    }


def _wgs84_geometry_and_bbox(grid: GridSpec) -> tuple[Optional[Mapping[str, Any]], Optional[list[float]]]:
    if grid.wgs84_bounds is not None:
        west, south, east, north = grid.wgs84_bounds
        bbox = [float(west), float(south), float(east), float(north)]
        return _bbox_geometry(bbox), bbox

    try:
        from pyproj import Transformer
    except ImportError:
        return None, None

    try:
        transformer = Transformer.from_crs(grid.crs, "EPSG:4326", always_xy=True)
        west, south, east, north = transformer.transform_bounds(*grid.bounds, densify_pts=21)
    except Exception:
        return None, None

    bbox = [float(west), float(south), float(east), float(north)]
    return _bbox_geometry(bbox), bbox


def _bbox_geometry(bbox: Sequence[float]) -> Mapping[str, Any]:
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [bbox[0], bbox[1]],
                [bbox[2], bbox[1]],
                [bbox[2], bbox[3]],
                [bbox[0], bbox[3]],
                [bbox[0], bbox[1]],
            ]
        ],
    }
