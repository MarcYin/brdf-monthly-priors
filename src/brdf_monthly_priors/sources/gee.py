from __future__ import annotations

import hashlib
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence, Tuple, Union

import numpy as np

from brdf_monthly_priors.types import MODIS_SINUSOIDAL_CRS, GridSpec, Observation

MCD43A1_COLLECTION_ID = "MODIS/061/MCD43A1"
MCD43A1_SCALE_FACTOR = 0.001
MCD43A1_BAND_MAP: Mapping[str, str] = {
    "brdf_iso_red": "BRDF_Albedo_Parameters_Band1_iso",
    "brdf_vol_red": "BRDF_Albedo_Parameters_Band1_vol",
    "brdf_geo_red": "BRDF_Albedo_Parameters_Band1_geo",
    "brdf_iso_green": "BRDF_Albedo_Parameters_Band4_iso",
    "brdf_vol_green": "BRDF_Albedo_Parameters_Band4_vol",
    "brdf_geo_green": "BRDF_Albedo_Parameters_Band4_geo",
    "brdf_iso_blue": "BRDF_Albedo_Parameters_Band3_iso",
    "brdf_vol_blue": "BRDF_Albedo_Parameters_Band3_vol",
    "brdf_geo_blue": "BRDF_Albedo_Parameters_Band3_geo",
    "brdf_iso_nir": "BRDF_Albedo_Parameters_Band2_iso",
    "brdf_vol_nir": "BRDF_Albedo_Parameters_Band2_vol",
    "brdf_geo_nir": "BRDF_Albedo_Parameters_Band2_geo",
    "brdf_iso_swir1": "BRDF_Albedo_Parameters_Band6_iso",
    "brdf_vol_swir1": "BRDF_Albedo_Parameters_Band6_vol",
    "brdf_geo_swir1": "BRDF_Albedo_Parameters_Band6_geo",
    "brdf_iso_swir2": "BRDF_Albedo_Parameters_Band7_iso",
    "brdf_vol_swir2": "BRDF_Albedo_Parameters_Band7_vol",
    "brdf_geo_swir2": "BRDF_Albedo_Parameters_Band7_geo",
}
MCD43A1_QUALITY_BAND_MAP: Mapping[str, str] = {
    "brdf_iso_red": "BRDF_Albedo_Band_Mandatory_Quality_Band1",
    "brdf_vol_red": "BRDF_Albedo_Band_Mandatory_Quality_Band1",
    "brdf_geo_red": "BRDF_Albedo_Band_Mandatory_Quality_Band1",
    "brdf_iso_green": "BRDF_Albedo_Band_Mandatory_Quality_Band4",
    "brdf_vol_green": "BRDF_Albedo_Band_Mandatory_Quality_Band4",
    "brdf_geo_green": "BRDF_Albedo_Band_Mandatory_Quality_Band4",
    "brdf_iso_blue": "BRDF_Albedo_Band_Mandatory_Quality_Band3",
    "brdf_vol_blue": "BRDF_Albedo_Band_Mandatory_Quality_Band3",
    "brdf_geo_blue": "BRDF_Albedo_Band_Mandatory_Quality_Band3",
    "brdf_iso_nir": "BRDF_Albedo_Band_Mandatory_Quality_Band2",
    "brdf_vol_nir": "BRDF_Albedo_Band_Mandatory_Quality_Band2",
    "brdf_geo_nir": "BRDF_Albedo_Band_Mandatory_Quality_Band2",
    "brdf_iso_swir1": "BRDF_Albedo_Band_Mandatory_Quality_Band6",
    "brdf_vol_swir1": "BRDF_Albedo_Band_Mandatory_Quality_Band6",
    "brdf_geo_swir1": "BRDF_Albedo_Band_Mandatory_Quality_Band6",
    "brdf_iso_swir2": "BRDF_Albedo_Band_Mandatory_Quality_Band7",
    "brdf_vol_swir2": "BRDF_Albedo_Band_Mandatory_Quality_Band7",
    "brdf_geo_swir2": "BRDF_Albedo_Band_Mandatory_Quality_Band7",
}


@dataclass(frozen=True)
class GeeProductPreset:
    """Earth Engine ImageCollection preset for a BRDF observation source."""

    collection_id: str
    band_map: Mapping[str, str]
    quality_band_map: Mapping[str, str]
    scale_map: Mapping[str, float] = field(default_factory=dict)
    quality_nodata_values: Tuple[int, ...] = ()


MCD43A1_PRESET = GeeProductPreset(
    collection_id=MCD43A1_COLLECTION_ID,
    band_map=MCD43A1_BAND_MAP,
    quality_band_map=MCD43A1_QUALITY_BAND_MAP,
    scale_map=dict.fromkeys(MCD43A1_BAND_MAP.values(), MCD43A1_SCALE_FACTOR),
    quality_nodata_values=(255,),
)


def gee_product_preset(product: str) -> GeeProductPreset:
    normalized = product.lower()
    if normalized in {"mcd43", "mcd43a1"}:
        return MCD43A1_PRESET
    raise ValueError("GEE product must be one of: mcd43a1")


class EdownGeeSource:
    """Fetch Google Earth Engine BRDF observations with edown.

    Date-window selection remains caller-owned. This source only downloads the
    requested native-grid Earth Engine images and converts the resulting
    GeoTIFFs into package-neutral observations for the compositor.
    """

    def __init__(
        self,
        *,
        collection_id: str,
        temporal_ranges: Sequence[Tuple[str, str]],
        output_root: Union[str, Path],
        band_map: Mapping[str, str],
        quality_band_map: Mapping[str, str],
        scale_map: Optional[Mapping[str, float]] = None,
        name: Optional[str] = None,
        manifest_dir: Optional[Union[str, Path]] = None,
        prepare_workers: int = 10,
        download_workers: int = 10,
        max_inflight_chunks: int = 32,
        chunk_size: Optional[int] = None,
        chunk_size_mode: str = "auto",
        request_byte_limit: int = 48 * 1024 * 1024,
        overwrite: bool = False,
        fail_on_download_error: bool = True,
        quality_nodata_values: Optional[Sequence[int]] = None,
    ):
        if not temporal_ranges:
            raise ValueError("EdownGeeSource requires explicit temporal_ranges supplied by the caller")
        self.collection_id = str(collection_id)
        self.temporal_ranges = tuple((str(start), str(end)) for start, end in temporal_ranges)
        self.output_root = Path(output_root).expanduser().resolve()
        self.band_map = dict(band_map)
        self.quality_band_map = dict(quality_band_map)
        self.scale_map = dict(scale_map or {})
        temporal_key = ",".join(f"{start}..{end}" for start, end in self.temporal_ranges)
        self._name = name or f"gee-edown:{self.collection_id}:{temporal_key}"
        self.manifest_dir = (
            Path(manifest_dir).expanduser().resolve()
            if manifest_dir is not None
            else self.output_root / "manifests"
        )
        self.prepare_workers = int(prepare_workers)
        self.download_workers = int(download_workers)
        self.max_inflight_chunks = int(max_inflight_chunks)
        self.chunk_size = chunk_size
        self.chunk_size_mode = str(chunk_size_mode)
        self.request_byte_limit = int(request_byte_limit)
        self.overwrite = bool(overwrite)
        self.fail_on_download_error = bool(fail_on_download_error)
        self.quality_nodata_values = tuple(int(value) for value in (quality_nodata_values or ()))
        self._download_cache_key: Optional[tuple[Any, ...]] = None
        self._download_cache: tuple[Any, ...] = ()

    @classmethod
    def for_product(
        cls,
        product: str,
        *,
        temporal_ranges: Sequence[Tuple[str, str]],
        output_root: Union[str, Path],
        name: Optional[str] = None,
        **kwargs: Any,
    ) -> "EdownGeeSource":
        preset = gee_product_preset(product)
        return cls(
            collection_id=preset.collection_id,
            temporal_ranges=temporal_ranges,
            output_root=output_root,
            band_map=preset.band_map,
            quality_band_map=preset.quality_band_map,
            scale_map=preset.scale_map,
            quality_nodata_values=preset.quality_nodata_values,
            name=name,
            **kwargs,
        )

    @property
    def name(self) -> str:
        return self._name

    def resolve_grid(
        self,
        *,
        wgs84_bounds: Sequence[float],
        brdf_crs: str,
        resolution: float,
        band_names: Sequence[str],
    ) -> GridSpec:
        del brdf_crs, resolution
        summaries = self._download(wgs84_bounds=wgs84_bounds, band_names=band_names)
        first_path = _first_successful_tiff(summaries)
        return _grid_from_tiff(first_path, wgs84_bounds=wgs84_bounds)

    def load_observations(
        self,
        *,
        grid: GridSpec,
        band_names: Sequence[str],
    ) -> Sequence[Observation]:
        if grid.wgs84_bounds is None:
            raise ValueError("EdownGeeSource requires a GridSpec with WGS84 bounds")
        summaries = self._download(wgs84_bounds=grid.wgs84_bounds, band_names=band_names)
        observations = []
        for result in _successful_results(summaries):
            if result.tiff_path is None:
                continue
            observations.append(
                _read_edown_tiff(
                    path=Path(result.tiff_path),
                    grid=grid,
                    band_names=tuple(str(band) for band in band_names),
                    band_map=self.band_map,
                    quality_band_map=self.quality_band_map,
                    quality_nodata_values=self.quality_nodata_values,
                    source_id=str(result.image_id),
                )
            )
        return tuple(observations)

    def _download(
        self,
        *,
        wgs84_bounds: Sequence[float],
        band_names: Sequence[str],
    ) -> tuple[Any, ...]:
        requested_bands = tuple(str(band) for band in band_names)
        bands = _edown_band_selection(
            band_names=requested_bands,
            band_map=self.band_map,
            quality_band_map=self.quality_band_map,
        )
        key = (tuple(float(value) for value in wgs84_bounds), requested_bands, bands)
        if self._download_cache_key == key and self._download_cache:
            return self._download_cache

        try:
            from edown import AOI, DownloadConfig, download_images
        except ImportError as exc:
            raise ImportError(
                "EdownGeeSource requires the 'gee' extra: "
                "pip install 'brdf-monthly-priors[gee]'"
            ) from exc
        with suppress(ModuleNotFoundError):
            _install_edown_sinusoidal_compatibility()

        summaries = []
        for start, end in self.temporal_ranges:
            manifest_path = self.manifest_dir / _manifest_name(
                collection_id=self.collection_id,
                start=start,
                end=end,
                bands=bands,
            )
            config = DownloadConfig(
                collection_id=self.collection_id,
                start_date=start,
                end_date=end,
                aoi=AOI.from_bbox(tuple(float(value) for value in wgs84_bounds)),
                bands=bands,
                rename_map={gee_band: output for output, gee_band in self.band_map.items()},
                scale_map=self.scale_map,
                output_root=self.output_root,
                manifest_path=manifest_path,
                prepare_workers=self.prepare_workers,
                download_workers=self.download_workers,
                max_inflight_chunks=self.max_inflight_chunks,
                chunk_size=self.chunk_size,
                chunk_size_mode=self.chunk_size_mode,
                request_byte_limit=self.request_byte_limit,
                overwrite=self.overwrite,
                resume=True,
            )
            summary = download_images(config)
            if self.fail_on_download_error and summary.failed:
                failures = [result.error for result in summary.results if result.status == "failed"]
                raise RuntimeError(
                    "edown failed to download one or more GEE images: "
                    + "; ".join(str(error) for error in failures if error)
                )
            summaries.append(summary)
        self._download_cache_key = key
        self._download_cache = tuple(summaries)
        return self._download_cache


def _edown_band_selection(
    *,
    band_names: Sequence[str],
    band_map: Mapping[str, str],
    quality_band_map: Mapping[str, str],
) -> tuple[str, ...]:
    missing = [band for band in band_names if band not in band_map]
    if missing:
        raise ValueError(f"no GEE band mapping configured for requested bands: {missing}")
    missing_quality = [band for band in band_names if band not in quality_band_map]
    if missing_quality:
        raise ValueError(f"no GEE quality band mapping configured for requested bands: {missing_quality}")
    selected = [band_map[band] for band in band_names]
    for quality_band in (quality_band_map[band] for band in band_names):
        if quality_band not in selected:
            selected.append(quality_band)
    return tuple(selected)


def _install_edown_sinusoidal_compatibility() -> None:
    try:
        import edown.discovery as edown_discovery
        import edown.download as edown_download
        import edown.grid as edown_grid
    except ImportError:
        raise

    if getattr(edown_download, "_brdf_monthly_priors_sin_patch", False):
        return

    original_get_image_grid_info = edown_grid.get_image_grid_info

    def get_image_grid_info(image_info: Mapping[str, Any]) -> dict[str, Any]:
        grid = dict(original_get_image_grid_info(image_info))
        if _is_modis_sinusoidal_code(grid.get("crs")):
            grid["ee_crs"] = grid["crs"]
            grid["crs"] = MODIS_SINUSOIDAL_CRS
        return grid

    def fetch_chunk(job: Any, task: Any, config: Any) -> Any:
        import time

        import ee
        from edown.grid import structured_to_hwc_array

        row, col, chunk_h, chunk_w = task
        request = {
            "fileFormat": "NUMPY_NDARRAY",
            "bandIds": list(job.image.selected_band_ids),
            "grid": {
                "dimensions": {"width": int(chunk_w), "height": int(chunk_h)},
                "crsCode": job.grid.get("ee_crs", job.grid["crs"]),
                "affineTransform": {
                    "scaleX": job.grid["x_scale"],
                    "shearX": 0,
                    "translateX": job.grid["origin_x"] + col * job.grid["x_scale"],
                    "shearY": 0,
                    "scaleY": job.grid["y_scale"],
                    "translateY": job.grid["origin_y"] + row * job.grid["y_scale"],
                },
            },
        }
        if job.expression is None:
            request["assetId"] = job.image.image_id
        else:
            request["expression"] = job.expression

        delay_seconds = config.retry_delay_seconds
        for attempt in range(1, config.max_retries + 1):
            try:
                raw = (
                    ee.data.getPixels(request)
                    if "assetId" in request
                    else ee.data.computePixels(request)
                )
                data = np.array(
                    structured_to_hwc_array(raw, job.image.selected_band_ids),
                    dtype=np.dtype(job.image.output_dtype),
                    copy=True,
                )
                return row, col, data
            except Exception:
                if attempt == config.max_retries:
                    raise
                time.sleep(delay_seconds)
                delay_seconds *= 2
        raise edown_download.DownloadError("Unexpected retry termination while downloading chunks.")

    edown_grid.get_image_grid_info = get_image_grid_info
    edown_discovery.get_image_grid_info = get_image_grid_info
    edown_download.get_image_grid_info = get_image_grid_info
    edown_download._fetch_chunk = fetch_chunk
    edown_download._brdf_monthly_priors_sin_patch = True


def _is_modis_sinusoidal_code(value: Any) -> bool:
    return str(value).upper() in {"SR-ORG:6974", "SR_ORG:6974"}


def _successful_results(summaries: Sequence[Any]) -> tuple[Any, ...]:
    results = []
    for summary in summaries:
        for result in summary.results:
            if result.status in {"downloaded", "skipped_existing"} and result.tiff_path is not None:
                results.append(result)
    return tuple(results)


def _first_successful_tiff(summaries: Sequence[Any]) -> Path:
    for result in _successful_results(summaries):
        if result.tiff_path is not None:
            return Path(result.tiff_path)
    raise RuntimeError("edown did not produce any downloadable GeoTIFFs")


def _grid_from_tiff(path: Path, *, wgs84_bounds: Sequence[float]) -> GridSpec:
    import rasterio

    with rasterio.open(path) as dataset:
        if dataset.crs is None:
            raise ValueError(f"{path} has no CRS")
        if dataset.transform.b != 0 or dataset.transform.d != 0:
            raise ValueError(f"{path} has a sheared transform; only north-up rasters are supported")
        resolution = abs(float(dataset.transform.a))
        y_resolution = abs(float(dataset.transform.e))
        if not np.isclose(resolution, y_resolution):
            raise ValueError(f"{path} has non-square pixels: {resolution} x {y_resolution}")
        bounds = dataset.bounds
        grid = GridSpec.from_bounds(
            bounds=(bounds.left, bounds.bottom, bounds.right, bounds.top),
            crs=dataset.crs.to_string(),
            resolution=resolution,
            wgs84_bounds=wgs84_bounds,
        )
        if grid.width != dataset.width or grid.height != dataset.height:
            return GridSpec(
                bounds=grid.bounds,
                crs=grid.crs,
                resolution=grid.resolution,
                width=int(dataset.width),
                height=int(dataset.height),
                wgs84_bounds=grid.wgs84_bounds,
            )
        return grid


def _read_edown_tiff(
    *,
    path: Path,
    grid: GridSpec,
    band_names: Sequence[str],
    band_map: Mapping[str, str],
    quality_band_map: Mapping[str, str],
    quality_nodata_values: Sequence[int],
    source_id: str,
) -> Observation:
    import rasterio

    with rasterio.open(path) as dataset:
        _validate_dataset_grid(dataset=dataset, grid=grid, path=path)
        lookup = _band_lookup(dataset)
        data = np.empty((len(band_names), grid.height, grid.width), dtype="float32")
        for index, band in enumerate(band_names):
            data[index] = _read_band(
                dataset=dataset,
                band_index=lookup[band],
                as_float=True,
            )
        quality_arrays = []
        for quality_band in _unique([quality_band_map[band] for band in band_names]):
            quality_arrays.append(
                _read_band(
                    dataset=dataset,
                    band_index=lookup[quality_band],
                    as_float=False,
                ).astype("uint16", copy=False)
            )
        if not quality_arrays:
            quality = np.zeros(grid.shape, dtype="uint16")
        else:
            quality = np.maximum.reduce(quality_arrays).astype("uint16", copy=False)
        if quality_nodata_values:
            quality = np.where(np.isin(quality, quality_nodata_values), 65535, quality).astype(
                "uint16",
                copy=False,
            )
        return Observation(
            data=data,
            quality=quality,
            band_names=band_names,
            source_id=source_id,
            metadata={
                "path": str(path),
                "collection": dataset.tags().get("ee_id", ""),
                "source": "gee-edown",
                "gee_bands": {band: band_map[band] for band in band_names},
            },
        )


def _validate_dataset_grid(*, dataset: Any, grid: GridSpec, path: Path) -> None:
    import rasterio

    if dataset.width != grid.width or dataset.height != grid.height:
        raise ValueError(f"{path} has shape {(dataset.height, dataset.width)}, expected {grid.shape}")
    if dataset.crs is None:
        raise ValueError(f"{path} has no CRS")
    expected_crs = rasterio.crs.CRS.from_user_input(grid.crs).to_string()
    if dataset.crs.to_string() != expected_crs:
        raise ValueError(f"{path} CRS {dataset.crs} does not match native grid CRS {grid.crs}")
    expected = tuple(round(value, 9) for value in grid.transform_tuple)
    transform = dataset.transform
    observed = tuple(
        round(value, 9)
        for value in (
            transform.a,
            transform.b,
            transform.c,
            transform.d,
            transform.e,
            transform.f,
        )
    )
    if observed != expected:
        raise ValueError(f"{path} transform {observed} does not match native grid transform {expected}")


def _band_lookup(dataset: Any) -> dict[str, int]:
    lookup = {}
    for index in range(1, dataset.count + 1):
        description = dataset.descriptions[index - 1]
        if description:
            lookup[str(description)] = index
    if len(lookup) != dataset.count:
        for index in range(1, dataset.count + 1):
            lookup.setdefault(str(index), index)
    return lookup


def _read_band(*, dataset: Any, band_index: int, as_float: bool) -> np.ndarray:
    array = dataset.read(band_index)
    nodata = dataset.nodata
    if as_float:
        out = array.astype("float32", copy=False)
        if nodata is not None and np.isfinite(nodata):
            out = np.where(out == nodata, np.nan, out).astype("float32", copy=False)
        return out
    if nodata is not None and np.isfinite(nodata):
        return np.where(array == nodata, 65535, array)
    return array


def _manifest_name(
    *,
    collection_id: str,
    start: str,
    end: str,
    bands: Sequence[str],
) -> str:
    safe = "".join(char if char.isalnum() else "-" for char in collection_id).strip("-")
    safe_start = "".join(char if char.isalnum() else "-" for char in start).strip("-")
    safe_end = "".join(char if char.isalnum() else "-" for char in end).strip("-")
    band_key = hashlib.sha1("|".join(bands).encode("utf-8")).hexdigest()[:12]
    return f"gee-{safe}-{safe_start}-{safe_end}-{band_key}.json"


def _unique(values: Sequence[str]) -> tuple[str, ...]:
    unique = []
    for value in values:
        if value not in unique:
            unique.append(value)
    return tuple(unique)


EdownSource = EdownGeeSource
GeeEdownSource = EdownGeeSource
