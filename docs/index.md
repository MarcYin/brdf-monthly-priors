# BRDF Monthly Priors

`brdf-monthly-priors` builds native-grid BRDF prior composites and writes them as STAC/GeoTIFF products.

The package boundary is intentionally narrow:

- Accept observations that are already on the native MODIS/VIIRS grid, usually Sinusoidal.
- Composite the best pixel per BRDF band using quality and sample-index tie-breaks.
- Encode the prior as `uint16` with scale factor `10000`.
- Encode relative uncertainty as `uint8` percent from `0` to `200`, with `255` marking suspicious or missing uncertainty.
- Persist tiled, DEFLATE-compressed GeoTIFF assets with no overviews.
- Emit a STAC Item that points to those assets.

Calendar planning is not part of the builder. Target dates, adjacent months, seasons, and history years are usage policy owned by SIAC or another caller.

## Contract

```python
from brdf_monthly_priors import Provider, ProviderConfig
from brdf_monthly_priors.sources import InMemorySource

provider = Provider(ProviderConfig(cache_dir=".brdf-cache", source=source))

product = provider.build_prior(
    product_id="example-brdf-prior",
    bounds=(-20015109.354, 10007054.677, -20014609.354, 10007554.677),
    crs="+proj=sinu +R=6371007.181 +nadgrids=@null +wktext",
    resolution=500.0,
    band_names=("brdf_iso_red",),
)
```

The returned `PriorProduct` contains the in-memory composite, output directory, and STAC Item dictionary.

