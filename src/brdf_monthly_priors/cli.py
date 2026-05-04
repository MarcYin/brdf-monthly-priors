from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional, Sequence

from brdf_monthly_priors import __version__
from brdf_monthly_priors.persistence import stac_item_path
from brdf_monthly_priors.provider import Provider, ProviderConfig
from brdf_monthly_priors.sources.earthaccess import EarthaccessSource, product_collections
from brdf_monthly_priors.sources.local import LocalNpzSource
from brdf_monthly_priors.sources.rasterio_reader import NativeRasterioStackReader
from brdf_monthly_priors.types import DEFAULT_BANDS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="brdf-monthly-priors",
        description="Build or retrieve native-grid BRDF prior composites as STAC/GeoTIFF products.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="Build or retrieve a BRDF prior product.")
    _add_request_args(build)
    build.add_argument("--cache-dir", default=None, help="Output/cache root.")
    build.add_argument("--source-name", default=None, help="Stable source/cache namespace.")
    build.add_argument(
        "--local-observations",
        default=None,
        help="Path to a local NPZ observation manifest for offline builds.",
    )
    build.add_argument(
        "--product",
        choices=("mcd43", "vnp43", "mcd19"),
        default=None,
        help="Earthaccess product preset to fetch on cache miss.",
    )
    build.add_argument(
        "--temporal-range",
        action="append",
        nargs=2,
        metavar=("START", "END"),
        default=[],
        help="Explicit Earthaccess temporal range. Repeat as needed. Planning remains caller-owned.",
    )
    build.add_argument(
        "--band-pattern",
        action="append",
        default=[],
        metavar="BAND=PATTERN",
        help="Rasterio subdataset match for Earthaccess reads. Repeat for every band.",
    )
    build.add_argument("--quality-pattern", default=None, help="Rasterio quality subdataset match.")
    build.add_argument("--sample-index-pattern", default=None, help="Rasterio sample-index subdataset match.")
    build.add_argument("--rebuild", action="store_true", help="Ignore any cached product.")
    build.add_argument("--json", action="store_true", help="Print the STAC Item JSON.")

    request_hash = subparsers.add_parser("request-hash", help="Compute the provider cache key.")
    _add_request_args(request_hash)
    request_hash.add_argument("--cache-dir", default=None, help="Output/cache root.")
    request_hash.add_argument("--source-name", default=None, help="Stable source/cache namespace.")

    show = subparsers.add_parser("stac-item-path", help="Print the expected STAC Item path.")
    _add_request_args(show)
    show.add_argument("--cache-dir", default=None, help="Output/cache root.")
    show.add_argument("--source-name", default=None, help="Stable source/cache namespace.")
    return parser


def _add_request_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--product-id", required=True)
    parser.add_argument("--bounds", nargs=4, type=float, required=True, metavar=("XMIN", "YMIN", "XMAX", "YMAX"))
    parser.add_argument("--crs", required=True)
    parser.add_argument("--resolution", type=float, required=True)
    parser.add_argument("--band", action="append", dest="bands", default=None, help="Band name. Repeat to override defaults.")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "build":
        return _build(args)
    if args.command == "request-hash":
        provider = Provider(_provider_config(args))
        print(_request_hash(provider, args))
        return 0
    if args.command == "stac-item-path":
        provider = Provider(_provider_config(args))
        print(stac_item_path(provider.store.root, _request_hash(provider, args)))
        return 0
    parser.error(f"unknown command {args.command!r}")
    return 2


def _build(args: argparse.Namespace) -> int:
    config = _provider_config(args)
    provider = Provider(config)
    band_names = tuple(args.bands or DEFAULT_BANDS)
    product = provider.build_prior(
        bounds=args.bounds,
        crs=args.crs,
        resolution=args.resolution,
        product_id=args.product_id,
        band_names=band_names,
        rebuild=args.rebuild,
    )
    if args.json:
        print(json.dumps(product.stac_item, indent=2, sort_keys=True))
    else:
        request_hash = product.request["request_hash"]
        path = stac_item_path(provider.store.root, request_hash)
        print(f"request_hash={request_hash}")
        print(f"stac_item={path}")
        print("assets=prior.tif,uncertainty.tif")
    return 0


def _provider_config(args: argparse.Namespace) -> ProviderConfig:
    source = None
    if getattr(args, "local_observations", None):
        source = LocalNpzSource(args.local_observations)
    elif getattr(args, "product", None):
        band_patterns = _parse_band_patterns(args.band_pattern)
        if not band_patterns or not args.quality_pattern or not args.temporal_range:
            raise SystemExit(
                "--product builds require explicit --temporal-range START END, "
                "--band-pattern BAND=PATTERN for every band, and --quality-pattern."
            )
        source = EarthaccessSource(
            collections=product_collections(args.product),
            temporal_ranges=tuple(tuple(value) for value in args.temporal_range),
            cache_dir=Path(args.cache_dir or ".brdf-earthdata-cache") / "earthdata",
            reader=NativeRasterioStackReader(
                band_patterns=band_patterns,
                quality_pattern=args.quality_pattern,
                sample_index_pattern=args.sample_index_pattern,
            ),
            name=f"earthaccess:{args.product}",
        )
    return ProviderConfig(
        cache_dir=args.cache_dir or Path.home() / ".cache" / "brdf-monthly-priors",
        source=source,
        source_name=getattr(args, "source_name", None),
    )


def _parse_band_patterns(values: Sequence[str]) -> dict[str, str]:
    parsed = {}
    for value in values:
        if "=" not in value:
            raise SystemExit(f"invalid --band-pattern {value!r}; expected BAND=PATTERN")
        band, pattern = value.split("=", 1)
        parsed[band] = pattern
    return parsed


def _request_hash(provider: Provider, args: argparse.Namespace) -> str:
    return provider.request_hash(
        bounds=args.bounds,
        crs=args.crs,
        resolution=args.resolution,
        product_id=args.product_id,
        band_names=tuple(args.bands or DEFAULT_BANDS),
    )


if __name__ == "__main__":
    raise SystemExit(main())

