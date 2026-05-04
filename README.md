# BRDF Monthly Priors

`brdf-monthly-priors` builds native-grid BRDF prior composites and persists them as a STAC Item with tiled, DEFLATE-compressed GeoTIFF assets. Despite the package name, calendar planning is intentionally outside the core builder: callers decide which observations should enter a prior, then this package composites those observations and writes a consistent product.

```python
import numpy as np

from brdf_monthly_priors import Observation, Provider, ProviderConfig
from brdf_monthly_priors.sources import InMemorySource

obs = Observation(
    data=np.ones((1, 2, 2), dtype="float32") * 0.25,
    quality=np.zeros((2, 2), dtype="uint16"),
    uncertainty=np.ones((1, 2, 2), dtype="float32") * 12,
    band_names=("brdf_iso_red",),
)

provider = Provider(
    ProviderConfig(
        cache_dir=".brdf-cache",
        source=InMemorySource((obs,), name="example"),
    )
)

product = provider.build_prior(
    product_id="example-brdf-prior",
    wgs84_bounds=(-1.0, 51.0, -0.99, 51.01),
    resolution=500.0,
    band_names=("brdf_iso_red",),
)
```

The output directory contains:

```text
<cache-root>/<request-hash>/
  stac-item.json
  assets/
    prior/
      01-brdf_iso_red.tif
    uncertainty/
      01-brdf_iso_red.tif
```

## Contract

This package owns:

- WGS84 AOI bounds conversion into the native BRDF data CRS.
- Google Earth Engine BRDF product downloading through `edown`.
- Native-grid best-pixel compositing from caller-supplied BRDF observations.
- BRDF quality and sample-index tie-breaking.
- Relative uncertainty propagation or fallback estimation.
- `uint16` prior encoding with scale factor `10000` and nodata `65535`.
- `uint8` relative uncertainty encoding in percent from `0` to `200`; values above `200%`, negative values, and non-finite values are stored as `255`.
- One-band tiled, DEFLATE-compressed GeoTIFF persistence optimized for remote chunked reads, without overviews.
- STAC Item creation with `projection` and `raster` extension metadata.

Callers own:

- Which observations to use for a prior.
- Any observation-day, month, season, or year logic.
- NASA/Earthdata search policy and temporal filtering.
- SIAC atmospheric correction, SWIR refine routing, spectral mapping, and `SurfacePrior` construction.

The public AOI input is always WGS84 longitude/latitude bounds: `(west, south, east, north)`. The package converts those bounds to the configured BRDF data CRS, which defaults to MODIS/VIIRS Sinusoidal. The builder still does not reproject source arrays internally; observations must already match the derived native grid.

## Installation

```bash
pip install brdf-monthly-priors
```

Optional Earthdata search support:

```bash
pip install "brdf-monthly-priors[earthdata]"
```

Optional Google Earth Engine download support through `edown`:

```bash
pip install "brdf-monthly-priors[gee]"
```

Optional experiment dependencies for the GEE-vs-official comparison:

```bash
pip install "brdf-monthly-priors[experiments]"
```

Development install:

```bash
python -m pip install -e ".[dev,docs]"
pytest
```

## Google Earth Engine Input

The built-in GEE preset uses `edown` to download `MODIS/061/MCD43A1` native-grid GeoTIFF observations. By default it requests `iso`, `vol`, and `geo` BRDF coefficients for red, green, blue, NIR, SWIR1, and SWIR2. The caller still supplies explicit temporal ranges; this package does not decide which days, months, or history windows to use. To reduce downloads, pass `sample_every_days` to query one-day windows at a fixed stride inside each temporal range.

```python
from brdf_monthly_priors import Provider, ProviderConfig
from brdf_monthly_priors.sources import EdownGeeSource

source = EdownGeeSource.for_product(
    "mcd43a1",
    temporal_ranges=(("2024-07-01", "2024-07-31"),),
    sample_every_days=7,
    output_root=".brdf-gee-cache",
)

provider = Provider(ProviderConfig(cache_dir=".brdf-cache", source=source))
product = provider.build_prior(
    product_id="mcd43a1-prior",
    wgs84_bounds=(-2.0, 51.0, -1.0, 52.0),
    resolution=500.0,
)
```

With `sample_every_days=7`, the July range above queries `2024-07-01`,
`2024-07-08`, `2024-07-15`, `2024-07-22`, and `2024-07-29` instead of every
matching image in the month.

`edown` handles Earth Engine authentication using `GEE_SERVICE_ACCOUNT`/`GEE_SERVICE_ACCOUNT_KEY`, existing Earth Engine user credentials, or Google Application Default Credentials.

## CLI

```bash
brdf-monthly-priors build \
  --product-id example-brdf-prior \
  --wgs84-bounds -1.0 51.0 -0.99 51.01 \
  --resolution 500 \
  --band brdf_iso_red \
  --local-observations observations.json \
  --cache-dir .brdf-cache
```

GEE MCD43A1 through `edown`:

```bash
brdf-monthly-priors build \
  --product-id mcd43a1-prior \
  --gee-product mcd43a1 \
  --temporal-range 2024-07-01 2024-07-31 \
  --sample-every-days 7 \
  --wgs84-bounds -2.0 51.0 -1.0 52.0 \
  --resolution 500 \
  --cache-dir .brdf-cache \
  --edown-output-root .brdf-gee-cache
```

`observations.json` points to local native-grid NPZ observations used as input, not as output:

```json
{
  "name": "example",
  "band_names": ["brdf_iso_red"],
  "items": [
    {
      "path": "obs.npz",
      "data_key": "data",
      "quality_key": "quality",
      "uncertainty_key": "uncertainty",
      "sample_index_key": "sample_index"
    }
  ]
}
```

## Publishing

The repository includes GitHub Actions workflows for tests, package build checks, PyPI trusted publishing on GitHub releases, and MkDocs Material deployment to GitHub Pages.
