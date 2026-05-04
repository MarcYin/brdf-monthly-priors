# Surface Priors

`surface-priors` builds native-grid surface prior products and writes them as STAC/GeoTIFF assets.

The current implemented provider builds MODIS/VIIRS BRDF priors. The package
name and output schema are intentionally broader so future providers can add
direct surface reflectance priors from sensors such as Sentinel-2 or Landsat.

The package boundary is intentionally narrow:

- Accept observations that are already on the requested native grid.
- Fetch Google Earth Engine BRDF observations through `edown` when configured, optionally sampling one day every `N` days to reduce downloads.
- Composite the best pixel per BRDF band using quality and sample-index tie-breaks.
- Encode the prior as `uint16` with scale factor `10000`.
- Encode relative uncertainty as `uint8` percent from `0` to `200`, with `255` marking suspicious or missing uncertainty.
- Persist tiled, DEFLATE-compressed GeoTIFF assets with no overviews.
- Emit a STAC Item that points to those assets.

Calendar planning is not part of the builder. Target dates, adjacent months, seasons, and history years are usage policy owned by SIAC or another caller.

## Contract

```python
from surface_priors import Provider, ProviderConfig
from surface_priors.sources import InMemorySource

provider = Provider(ProviderConfig(cache_dir=".surface-cache", source=source))

product = provider.build_prior(
    product_id="example-brdf-prior",
    wgs84_bounds=(-1.0, 51.0, -0.99, 51.01),
    resolution=500.0,
    band_names=("brdf_iso_red",),
)
```

The returned `PriorProduct` contains the in-memory composite, output directory, and STAC Item dictionary.

Input AOI bounds are always WGS84 `(west, south, east, north)`. The package converts them to the configured native CRS internally; the current BRDF default is MODIS/VIIRS Sinusoidal.

Sources that can resolve their native grid, such as the `edown` Google Earth Engine source, may replace that fallback grid with the exact downloaded GeoTIFF grid. The compositor still receives native-grid arrays and does not reproject them.
