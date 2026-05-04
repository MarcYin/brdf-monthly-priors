# Quickstart

## Install

```bash
pip install brdf-monthly-priors
```

Optional NASA Earthdata search support:

```bash
pip install "brdf-monthly-priors[earthdata]"
```

## Build From A Custom Source

Any source that implements `ObservationSource` can feed the provider. Observations must already match the requested grid; the builder does not reproject.

```python
import numpy as np

from brdf_monthly_priors import Observation, Provider, ProviderConfig
from brdf_monthly_priors.sources import InMemorySource

obs = Observation(
    data=np.ones((1, 2, 2), dtype="float32") * 0.25,
    quality=np.zeros((2, 2), dtype="uint16"),
    uncertainty=np.ones((1, 2, 2), dtype="float32") * 12,
    sample_index=np.zeros((2, 2), dtype="int16"),
    band_names=("iso",),
)

source = InMemorySource((obs,), name="example")
provider = Provider(ProviderConfig(cache_dir=".brdf-cache", source=source))

product = provider.build_prior(
    product_id="example-prior",
    wgs84_bounds=(0, 0, 2, 2),
    brdf_crs="EPSG:4326",
    resolution=1,
    band_names=("iso",),
)
```

The product is written to:

```text
.brdf-cache/<request-hash>/stac-item.json
.brdf-cache/<request-hash>/assets/prior.tif
.brdf-cache/<request-hash>/assets/uncertainty.tif
```

## Retrieve A Prepared Store

Use the same source namespace that built the cache:

```python
provider = Provider(ProviderConfig(cache_dir=".brdf-cache", source_name="example"))
product = provider.build_prior(
    product_id="example-prior",
    wgs84_bounds=(0, 0, 2, 2),
    brdf_crs="EPSG:4326",
    resolution=1,
    band_names=("iso",),
)
```

If the cache key is absent and no source or explicit observations are configured, the provider raises a cache-miss error.
