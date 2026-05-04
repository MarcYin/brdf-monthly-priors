from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

import numpy as np

from brdf_monthly_priors import Provider, ProviderConfig
from brdf_monthly_priors.encoding import encode_prior, encode_relative_uncertainty
from brdf_monthly_priors.sources import EdownGeeSource
from brdf_monthly_priors.sources.gee import MCD43A1_QUALITY_BAND_MAP
from brdf_monthly_priors.types import DEFAULT_BANDS, GridSpec, Observation

MCD43A1_SHORT_NAME = "MCD43A1"
MCD43A1_VERSION = "061"
MCD43A1_FILL_VALUE = 32767
MCD43A1_SCALE_FACTOR = 0.001
MODIS_GLOBAL_X_MIN = -20015109.354
MODIS_GLOBAL_Y_MAX = 10007554.677003
MODIS_TILE_PIXELS = 2400

OFFICIAL_DATASETS: Mapping[str, tuple[str, int]] = {
    "brdf_iso_red": ("BRDF_Albedo_Parameters_Band1", 1),
    "brdf_vol_red": ("BRDF_Albedo_Parameters_Band1", 2),
    "brdf_geo_red": ("BRDF_Albedo_Parameters_Band1", 3),
    "brdf_iso_nir": ("BRDF_Albedo_Parameters_Band2", 1),
    "brdf_vol_nir": ("BRDF_Albedo_Parameters_Band2", 2),
    "brdf_geo_nir": ("BRDF_Albedo_Parameters_Band2", 3),
    "brdf_iso_swir1": ("BRDF_Albedo_Parameters_Band6", 1),
    "brdf_vol_swir1": ("BRDF_Albedo_Parameters_Band6", 2),
    "brdf_geo_swir1": ("BRDF_Albedo_Parameters_Band6", 3),
}


@dataclass(frozen=True)
class FixedObservationSource:
    name: str
    grid: GridSpec
    observations: Sequence[Observation]

    def resolve_grid(
        self,
        *,
        wgs84_bounds: Sequence[float],
        brdf_crs: str,
        resolution: float,
        band_names: Sequence[str],
    ) -> GridSpec:
        del wgs84_bounds, brdf_crs, resolution, band_names
        return self.grid

    def load_observations(
        self,
        *,
        grid: GridSpec,
        band_names: Sequence[str],
    ) -> Sequence[Observation]:
        requested = tuple(str(band) for band in band_names)
        for observation in self.observations:
            if tuple(observation.band_names) != requested:
                raise ValueError(f"{observation.source_id} has bands {observation.band_names}")
            if observation.data.shape[1:] != grid.shape:
                raise ValueError(f"{observation.source_id} is not aligned to {grid.shape}")
        return tuple(self.observations)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build and compare MCD43A1 BRDF priors from GEE/edown and official "
            "LP DAAC Earthdata HDF granules."
        )
    )
    parser.add_argument("--west", type=float, default=-0.15)
    parser.add_argument("--south", type=float, default=51.48)
    parser.add_argument("--east", type=float, default=-0.13)
    parser.add_argument("--north", type=float, default=51.50)
    parser.add_argument("--start-date", default="2024-07-01")
    parser.add_argument("--end-date", default="2024-07-31")
    parser.add_argument("--output-root", type=Path, default=Path("runs/gee-vs-official-mcd43a1"))
    parser.add_argument("--band", action="append", dest="bands", default=None)
    parser.add_argument("--earthaccess-strategy", default="all")
    parser.add_argument("--download-threads", type=int, default=4)
    parser.add_argument(
        "--max-official-granules",
        type=int,
        default=-1,
        help="Limit official granules for smoke tests. -1 means no limit.",
    )
    parser.add_argument(
        "--skip-figures",
        action="store_true",
        help="Do not write PNG/PDF/SVG comparison figures.",
    )
    parser.add_argument(
        "--figure-format",
        choices=("png", "pdf", "svg"),
        default="png",
        help="Figure format written under <output-root>/figures.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    wgs84_bounds = (args.west, args.south, args.east, args.north)
    temporal_ranges = ((args.start_date, args.end_date),)
    band_names = tuple(args.bands or DEFAULT_BANDS)
    output_root = args.output_root.expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    gee_source = EdownGeeSource.for_product(
        "mcd43a1",
        temporal_ranges=temporal_ranges,
        output_root=output_root / "gee-edown-downloads",
    )
    gee_provider = Provider(ProviderConfig(cache_dir=output_root / "gee-prior", source=gee_source))
    gee_product = gee_provider.build_prior(
        product_id="mcd43a1-gee-edown",
        wgs84_bounds=wgs84_bounds,
        resolution=500.0,
        band_names=band_names,
        rebuild=True,
    )

    official_paths = download_official_mcd43a1(
        wgs84_bounds=wgs84_bounds,
        start_date=args.start_date,
        end_date=args.end_date,
        output_dir=output_root / "official-earthdata-downloads",
        strategy=args.earthaccess_strategy,
        threads=args.download_threads,
        max_granules=args.max_official_granules,
    )
    official_observations = read_official_observations(
        paths=official_paths,
        grid=gee_product.grid,
        band_names=band_names,
    )
    official_source = FixedObservationSource(
        name=f"official-earthdata:MCD43A1:{args.start_date}..{args.end_date}",
        grid=gee_product.grid,
        observations=official_observations,
    )
    official_provider = Provider(
        ProviderConfig(cache_dir=output_root / "official-prior", source=official_source)
    )
    official_product = official_provider.build_prior(
        product_id="mcd43a1-official-earthdata",
        wgs84_bounds=wgs84_bounds,
        resolution=gee_product.grid.resolution,
        band_names=band_names,
        rebuild=True,
    )

    summary = compare_products(
        gee_product=gee_product,
        official_product=official_product,
        official_granule_count=len(official_paths),
        official_observation_count=len(official_observations),
    )
    if not args.skip_figures:
        figures = write_figures(
            gee_product=gee_product,
            official_product=official_product,
            summary=summary,
            output_dir=output_root / "figures",
            file_format=args.figure_format,
        )
        summary["figures"] = {name: str(path) for name, path in figures.items()}
    summary_path = output_root / "comparison-summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"comparison_summary={summary_path}")
    print(f"gee_stac={Path(gee_product.output_dir) / 'stac-item.json'}")
    print(f"official_stac={Path(official_product.output_dir) / 'stac-item.json'}")
    return 0


def download_official_mcd43a1(
    *,
    wgs84_bounds: Sequence[float],
    start_date: str,
    end_date: str,
    output_dir: Path,
    strategy: str,
    threads: int,
    max_granules: int,
) -> tuple[Path, ...]:
    try:
        import earthaccess
    except ImportError as exc:
        raise ImportError(
            "Install the experiment extra before running this experiment: "
            "pip install 'brdf-monthly-priors[experiments]'"
        ) from exc

    earthaccess.login(strategy=strategy)
    results = earthaccess.search_data(
        short_name=MCD43A1_SHORT_NAME,
        version=MCD43A1_VERSION,
        bounding_box=tuple(float(value) for value in wgs84_bounds),
        temporal=(start_date, end_date),
        count=-1,
    )
    results = filter_results_by_native_date(results, start_date=start_date, end_date=end_date)
    if max_granules >= 0:
        results = results[:max_granules]
    if not results:
        raise RuntimeError(
            "No official MCD43A1 granules with AYYYYDOY dates inside the requested date range"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = earthaccess.download(
        results,
        local_path=output_dir,
        threads=threads,
        show_progress=True,
    )
    return tuple(Path(path) for path in paths)


def filter_results_by_native_date(
    results: Sequence[Any],
    *,
    start_date: str,
    end_date: str,
) -> list[Any]:
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    filtered = []
    for result in results:
        native_date = native_mcd43_date(result)
        if native_date is not None and start <= native_date <= end:
            filtered.append(result)
    return filtered


def native_mcd43_date(result: Any) -> Optional[date]:
    candidates = []
    if isinstance(result, Mapping):
        meta = result.get("meta", {})
        umm = result.get("umm", {})
        if isinstance(meta, Mapping):
            candidates.append(str(meta.get("native-id", "")))
        if isinstance(umm, Mapping):
            candidates.append(str(umm.get("GranuleUR", "")))
    candidates.append(str(result))
    for candidate in candidates:
        match = re.search(r"\.A(?P<year>\d{4})(?P<doy>\d{3})\.", candidate)
        if match is not None:
            return datetime.strptime(match.group("year") + match.group("doy"), "%Y%j").date()
    return None


def read_official_observations(
    *,
    paths: Sequence[Path],
    grid: GridSpec,
    band_names: Sequence[str],
) -> tuple[Observation, ...]:
    observations = []
    for path in paths:
        observation = read_official_observation(path=path, grid=grid, band_names=band_names)
        if observation is not None:
            observations.append(observation)
    if not observations:
        raise RuntimeError("No official granules overlapped the GEE/edown native grid")
    return tuple(observations)


def read_official_observation(
    *,
    path: Path,
    grid: GridSpec,
    band_names: Sequence[str],
) -> Optional[Observation]:
    try:
        from pyhdf.SD import SD, SDC
    except ImportError as exc:
        raise ImportError(
            "Official MCD43A1 granules are HDF4. Install pyhdf for this experiment: "
            "pip install 'brdf-monthly-priors[experiments]'"
        ) from exc

    window = modis_tile_window(path=path, grid=grid)
    if window is None:
        return None
    row0, row1, col0, col1 = window
    hdf = SD(str(path), SDC.READ)

    data = np.empty((len(band_names), grid.height, grid.width), dtype="float32")
    try:
        for index, band in enumerate(band_names):
            dataset_name, layer_index = OFFICIAL_DATASETS[band]
            values = hdf.select(dataset_name)[row0:row1, col0:col1, layer_index - 1]
            values = values.astype("float32", copy=False)
            values = np.where(values >= MCD43A1_FILL_VALUE, np.nan, values)
            data[index] = values * MCD43A1_SCALE_FACTOR

        quality_arrays = []
        for quality_dataset in unique([MCD43A1_QUALITY_BAND_MAP[band] for band in band_names]):
            values = hdf.select(quality_dataset)[row0:row1, col0:col1]
            quality_arrays.append(values.astype("uint16", copy=False))
    except KeyError as exc:
        raise KeyError(f"{path} does not contain expected MCD43A1 dataset {exc}") from exc

    quality = np.maximum.reduce(quality_arrays).astype("uint16", copy=False)
    return Observation(
        data=data,
        quality=quality,
        band_names=tuple(band_names),
        source_id=path.name,
        metadata={
            "path": str(path),
            "collection": MCD43A1_SHORT_NAME,
            "version": MCD43A1_VERSION,
            "source": "official-earthdata",
        },
    )


def modis_tile_window(*, path: Path, grid: GridSpec) -> Optional[tuple[int, int, int, int]]:
    match = re.search(r"\.h(?P<h>\d{2})v(?P<v>\d{2})\.", path.name)
    if match is None:
        raise ValueError(f"Cannot parse MODIS h/v tile from {path.name}")
    h = int(match.group("h"))
    v = int(match.group("v"))
    tile_size = float(grid.resolution) * MODIS_TILE_PIXELS
    tile_minx = MODIS_GLOBAL_X_MIN + h * tile_size
    tile_maxy = MODIS_GLOBAL_Y_MAX - v * tile_size
    col0 = round((grid.bounds[0] - tile_minx) / grid.resolution)
    row0 = round((tile_maxy - grid.bounds[3]) / grid.resolution)
    col1 = col0 + grid.width
    row1 = row0 + grid.height
    if col0 < 0 or row0 < 0 or col1 > MODIS_TILE_PIXELS or row1 > MODIS_TILE_PIXELS:
        return None
    return int(row0), int(row1), int(col0), int(col1)


def compare_products(*, gee_product: Any, official_product: Any, **counts: int) -> dict[str, Any]:
    gee_data = gee_product.composite.data
    official_data = official_product.composite.data
    prior_a = encode_prior(gee_data)
    prior_b = encode_prior(official_data)
    uncertainty_a = encode_relative_uncertainty(gee_product.composite.uncertainty)
    uncertainty_b = encode_relative_uncertainty(official_product.composite.uncertainty)

    band_metrics = {}
    for index, band in enumerate(gee_product.composite.band_names):
        band_metrics[band] = band_comparison_metrics(
            gee=gee_data[index],
            official=official_data[index],
            gee_encoded=prior_a[index],
            official_encoded=prior_b[index],
        )

    return {
        "schema_version": 1,
        "aoi_wgs84": gee_product.grid.wgs84_bounds,
        "native_grid": gee_product.grid.to_dict(),
        "gee_output_dir": gee_product.output_dir,
        "official_output_dir": official_product.output_dir,
        "official_granule_count": counts["official_granule_count"],
        "official_observation_count": counts["official_observation_count"],
        "overall": {
            "encoded_prior_arrays_equal": bool(np.array_equal(prior_a, prior_b)),
            "encoded_uncertainty_arrays_equal": bool(np.array_equal(uncertainty_a, uncertainty_b)),
            "max_abs_prior_float_difference": max_abs_difference(gee_data, official_data),
            "max_abs_uncertainty_float_difference": max_abs_difference(
                gee_product.composite.uncertainty,
                official_product.composite.uncertainty,
            ),
        },
        "bands": band_metrics,
    }


def band_comparison_metrics(
    *,
    gee: np.ndarray,
    official: np.ndarray,
    gee_encoded: np.ndarray,
    official_encoded: np.ndarray,
) -> dict[str, Any]:
    gee = np.asarray(gee)
    official = np.asarray(official)
    finite_gee = np.isfinite(gee)
    finite_official = np.isfinite(official)
    joint = finite_gee & finite_official
    total_pixels = int(gee.size)
    encoded_equal_pixels = int(np.count_nonzero(gee_encoded == official_encoded))
    metrics: dict[str, Any] = {
        "total_pixels": total_pixels,
        "valid_pixels": int(np.count_nonzero(joint)),
        "joint_valid_pixels": int(np.count_nonzero(joint)),
        "gee_valid_pixels": int(np.count_nonzero(finite_gee)),
        "official_valid_pixels": int(np.count_nonzero(finite_official)),
        "gee_only_valid_pixels": int(np.count_nonzero(finite_gee & ~finite_official)),
        "official_only_valid_pixels": int(np.count_nonzero(~finite_gee & finite_official)),
        "both_nodata_pixels": int(np.count_nonzero(~finite_gee & ~finite_official)),
        "encoded_prior_equal_pixels": encoded_equal_pixels,
        "encoded_prior_unequal_pixels": total_pixels - encoded_equal_pixels,
        "encoded_prior_equal_fraction": encoded_equal_pixels / total_pixels if total_pixels else None,
        "max_abs_float_difference": None,
        "mean_abs_float_difference": None,
        "median_abs_float_difference": None,
        "p95_abs_float_difference": None,
        "rmse_float_difference": None,
        "mean_signed_float_difference": None,
        "pearson_r": None,
        "r2": None,
        "linear_fit_slope": None,
        "linear_fit_intercept": None,
    }
    if not np.any(joint):
        return metrics

    x = official[joint].astype("float64", copy=False)
    y = gee[joint].astype("float64", copy=False)
    diff = y - x
    abs_diff = np.abs(diff)
    metrics.update(
        {
            "max_abs_float_difference": float(np.max(abs_diff)),
            "mean_abs_float_difference": float(np.mean(abs_diff)),
            "median_abs_float_difference": float(np.median(abs_diff)),
            "p95_abs_float_difference": float(np.percentile(abs_diff, 95)),
            "rmse_float_difference": float(np.sqrt(np.mean(diff**2))),
            "mean_signed_float_difference": float(np.mean(diff)),
        }
    )
    if x.size > 1 and np.std(x) > 0 and np.std(y) > 0:
        pearson = float(np.corrcoef(x, y)[0, 1])
        slope, intercept = np.polyfit(x, y, 1)
        metrics.update(
            {
                "pearson_r": pearson,
                "r2": pearson**2,
                "linear_fit_slope": float(slope),
                "linear_fit_intercept": float(intercept),
            }
        )
    return metrics


def max_abs_difference(a: np.ndarray, b: np.ndarray) -> Optional[float]:
    mask = np.isfinite(a) & np.isfinite(b)
    if not np.any(mask):
        return None
    return float(np.nanmax(np.abs(a[mask] - b[mask])))


def write_figures(
    *,
    gee_product: Any,
    official_product: Any,
    summary: Mapping[str, Any],
    output_dir: Path,
    file_format: str,
) -> dict[str, Path]:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise ImportError(
            "Figure generation requires matplotlib. Install the experiment extra: "
            "pip install 'brdf-monthly-priors[experiments]'"
        ) from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "scatter_by_band": output_dir / f"scatter-by-band.{file_format}",
        "difference_by_band": output_dir / f"difference-by-band.{file_format}",
        "metrics_by_band": output_dir / f"metrics-by-band.{file_format}",
    }
    plot_scatter_by_band(
        plt=plt,
        gee_product=gee_product,
        official_product=official_product,
        summary=summary,
        path=paths["scatter_by_band"],
    )
    plot_difference_by_band(
        plt=plt,
        gee_product=gee_product,
        official_product=official_product,
        path=paths["difference_by_band"],
    )
    plot_metrics_by_band(plt=plt, summary=summary, path=paths["metrics_by_band"])
    return paths


def plot_scatter_by_band(
    *,
    plt: Any,
    gee_product: Any,
    official_product: Any,
    summary: Mapping[str, Any],
    path: Path,
) -> None:
    band_names = tuple(gee_product.composite.band_names)
    rows, cols = grid_layout(len(band_names))
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 4.2, rows * 3.8), squeeze=False)
    for axis in axes.ravel()[len(band_names) :]:
        axis.axis("off")

    for index, band in enumerate(band_names):
        axis = axes.ravel()[index]
        official = official_product.composite.data[index]
        gee = gee_product.composite.data[index]
        mask = np.isfinite(official) & np.isfinite(gee)
        metrics = summary["bands"][band]
        if np.any(mask):
            x = official[mask]
            y = gee[mask]
            axis.scatter(x, y, s=18, alpha=0.78, color="#1f77b4", edgecolors="none")
            lower = float(min(np.min(x), np.min(y)))
            upper = float(max(np.max(x), np.max(y)))
            pad = max(abs(lower) * 0.05, 0.001) if lower == upper else (upper - lower) * 0.08
            lower -= pad
            upper += pad
            axis.plot([lower, upper], [lower, upper], color="#333333", linewidth=1.0)
            axis.set_xlim(lower, upper)
            axis.set_ylim(lower, upper)
        axis.set_title(band)
        axis.set_xlabel("Official LP DAAC")
        axis.set_ylabel("GEE / edown")
        axis.grid(True, linewidth=0.4, alpha=0.4)
        axis.text(
            0.04,
            0.96,
            "\n".join(
                [
                    f"n={metrics['joint_valid_pixels']}",
                    f"RMSE={format_float(metrics['rmse_float_difference'])}",
                    f"R2={format_float(metrics['r2'])}",
                ]
            ),
            transform=axis.transAxes,
            va="top",
            ha="left",
            fontsize=8,
            bbox={
                "boxstyle": "round,pad=0.25",
                "facecolor": "white",
                "alpha": 0.85,
                "edgecolor": "#cccccc",
            },
        )
    fig.suptitle("GEE / edown vs official LP DAAC BRDF prior values by band", fontsize=14)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_difference_by_band(
    *,
    plt: Any,
    gee_product: Any,
    official_product: Any,
    path: Path,
) -> None:
    band_names = tuple(gee_product.composite.band_names)
    rows, cols = grid_layout(len(band_names))
    differences = []
    for index in range(len(band_names)):
        diff = gee_product.composite.data[index] - official_product.composite.data[index]
        differences.append(diff)
    finite_abs = [np.abs(diff[np.isfinite(diff)]) for diff in differences if np.any(np.isfinite(diff))]
    global_max = max((float(np.max(values)) for values in finite_abs if values.size), default=1.0)
    global_max = max(global_max, 1e-8)

    fig, axes = plt.subplots(rows, cols, figsize=(cols * 4.0, rows * 3.5), squeeze=False)
    image = None
    for axis in axes.ravel()[len(band_names) :]:
        axis.axis("off")
    for index, band in enumerate(band_names):
        axis = axes.ravel()[index]
        image = axis.imshow(differences[index], cmap="coolwarm", vmin=-global_max, vmax=global_max)
        axis.set_title(band)
        axis.set_xticks([])
        axis.set_yticks([])
    if image is not None:
        fig.colorbar(image, ax=axes.ravel().tolist(), shrink=0.82, label="GEE - official")
    fig.suptitle("Spatial difference maps by band", fontsize=14)
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def plot_metrics_by_band(*, plt: Any, summary: Mapping[str, Any], path: Path) -> None:
    bands = tuple(summary["bands"].keys())
    rmse = [value_or_zero(summary["bands"][band]["rmse_float_difference"]) for band in bands]
    max_abs = [value_or_zero(summary["bands"][band]["max_abs_float_difference"]) for band in bands]
    equal_fraction = [value_or_zero(summary["bands"][band]["encoded_prior_equal_fraction"]) for band in bands]
    positions = np.arange(len(bands))

    fig, axes = plt.subplots(1, 3, figsize=(15, max(4.5, len(bands) * 0.42)), sharey=True)
    axes[0].barh(positions, rmse, color="#4c78a8")
    axes[0].set_title("RMSE")
    axes[0].set_xlabel("BRDF coefficient")
    axes[1].barh(positions, max_abs, color="#f58518")
    axes[1].set_title("Max abs diff")
    axes[1].set_xlabel("BRDF coefficient")
    axes[2].barh(positions, equal_fraction, color="#54a24b")
    axes[2].set_title("Encoded equality")
    axes[2].set_xlabel("fraction")
    axes[2].set_xlim(0, 1.02)
    axes[0].set_yticks(positions)
    axes[0].set_yticklabels(bands)
    for axis in axes:
        axis.grid(True, axis="x", linewidth=0.4, alpha=0.4)
    fig.suptitle("Band-by-band comparison metrics", fontsize=14)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def grid_layout(count: int, max_cols: int = 3) -> tuple[int, int]:
    cols = min(max_cols, max(1, count))
    rows = int(np.ceil(count / cols))
    return rows, cols


def format_float(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.3g}"


def value_or_zero(value: Any) -> float:
    if value is None:
        return 0.0
    return float(value)


def unique(values: Sequence[str]) -> tuple[str, ...]:
    output = []
    for value in values:
        if value not in output:
            output.append(value)
    return tuple(output)


if __name__ == "__main__":
    raise SystemExit(main())
