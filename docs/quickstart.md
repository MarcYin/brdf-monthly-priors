# Quickstart

## Install

```bash
pip install brdf-monthly-priors
```

Optional NASA Earthdata and raster support:

```bash
pip install "brdf-monthly-priors[earthdata,raster]"
```

## Build From A Custom Source

Any source that implements `ObservationSource` can feed the provider.

```python
from datetime import date

import numpy as np

from brdf_monthly_priors import Observation, Provider, ProviderConfig
from brdf_monthly_priors.sources import InMemorySource

obs = Observation(
    acquired=date(2025, 7, 12),
    data=np.ones((1, 2, 2), dtype="float32"),
    quality=np.zeros((2, 2), dtype="uint16"),
    sample_index=np.zeros((2, 2), dtype="int16"),
    band_names=("iso",),
)

source = InMemorySource((obs,), name="example")
provider = Provider(ProviderConfig(cache_dir=".brdf-cache", source=source))

collection = provider.get_monthly_composites(
    bounds=(0, 0, 2, 2),
    crs="EPSG:32631",
    observation_date="2025-07-12",
    resolution=1,
    months_window=(0,),
    history_years=1,
    band_names=("iso",),
)
```

## Retrieve A Prepared Store

Use the same source namespace that built the cache:

```python
provider = Provider(ProviderConfig(cache_dir=".brdf-cache", source_name="example"))
collection = provider.get_monthly_composites(
    bounds=(0, 0, 2, 2),
    crs="EPSG:32631",
    observation_date="2025-07-12",
    resolution=1,
    months_window=(0,),
    history_years=1,
    band_names=("iso",),
)
```

If the cache key is absent and no source is configured, the provider raises a cache-miss error.

