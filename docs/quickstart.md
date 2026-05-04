# Quickstart

## Install

```bash
pip install surface-priors
```

Optional NASA Earthdata search support:

```bash
pip install "surface-priors[earthdata]"
```

Optional Google Earth Engine support through `edown`:

```bash
pip install "surface-priors[gee]"
```

## Build From Google Earth Engine

`EdownGeeSource` downloads native-grid GeoTIFF observations with `edown`, then passes those observations to the same prior compositor. The built-in `mcd43a1` preset maps the default BRDF kernel bands to `MODIS/061/MCD43A1`: red, green, blue, NIR, SWIR1, and SWIR2, each with `iso`, `vol`, and `geo` coefficients.

```python
from surface_priors import Provider, ProviderConfig
from surface_priors.sources import EdownGeeSource

source = EdownGeeSource.for_product(
    "mcd43a1",
    temporal_ranges=(("2024-07-01", "2024-07-31"),),
    sample_every_days=7,
    output_root=".surface-gee-cache",
)

provider = Provider(ProviderConfig(cache_dir=".surface-cache", source=source))
product = provider.build_prior(
    product_id="mcd43a1-prior",
    wgs84_bounds=(-2.0, 51.0, -1.0, 52.0),
    resolution=500,
)
```

The temporal range is explicit caller policy. `edown` may derive a source-native grid from the downloaded GeoTIFFs; no raster reprojection is done by this package. With `sample_every_days=7`, the source queries one-day windows on `2024-07-01`, `2024-07-08`, `2024-07-15`, `2024-07-22`, and `2024-07-29` instead of every matching image in July.

## Build From A Custom Source

Any source that implements `ObservationSource` can feed the provider. Observations must already match the requested grid; the builder does not reproject.

```python
import numpy as np

from surface_priors import Observation, Provider, ProviderConfig
from surface_priors.sources import InMemorySource

obs = Observation(
    data=np.ones((1, 2, 2), dtype="float32") * 0.25,
    quality=np.zeros((2, 2), dtype="uint16"),
    uncertainty=np.ones((1, 2, 2), dtype="float32") * 12,
    sample_index=np.zeros((2, 2), dtype="int16"),
    band_names=("iso",),
)

source = InMemorySource((obs,), name="example")
provider = Provider(ProviderConfig(cache_dir=".surface-cache", source=source))

product = provider.build_prior(
    product_id="example-prior",
    wgs84_bounds=(0, 0, 2, 2),
    native_crs="EPSG:4326",
    resolution=1,
    band_names=("iso",),
)
```

The product is written to:

```text
.surface-cache/<request-hash>/stac-item.json
.surface-cache/<request-hash>/assets/prior/01-iso.tif
.surface-cache/<request-hash>/assets/uncertainty/01-iso.tif
```

## Retrieve A Prepared Store

Use the same source namespace that built the cache:

```python
provider = Provider(ProviderConfig(cache_dir=".surface-cache", source_name="example"))
product = provider.build_prior(
    product_id="example-prior",
    wgs84_bounds=(0, 0, 2, 2),
    native_crs="EPSG:4326",
    resolution=1,
    band_names=("iso",),
)
```

If the cache key is absent and no source or explicit observations are configured, the provider raises a cache-miss error.
