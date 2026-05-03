# BRDF Monthly Priors

`brdf-monthly-priors` builds monthly best-pixel BRDF prior composites for a target AOI, CRS, resolution, and observation date.

The package boundary is intentionally narrow:

- Fetch or read MCD43/VNP43/MCD19-style BRDF observations.
- Plan target, adjacent, and historical months.
- Composite the best pixel per BRDF band using quality, temporal distance, and sample-index tie-breaks.
- Persist a schema-versioned collection with a JSON manifest and NumPy arrays.
- Return a package-neutral object that downstream systems can adapt.

SIAC should keep atmospheric correction, SWIR refinement, spectral mapping into the target sensor basis, and `SurfacePrior` construction.

## Contract

```python
from datetime import date

from brdf_monthly_priors import Provider, ProviderConfig

provider = Provider(ProviderConfig(cache_dir=".brdf-cache"))

collection = provider.get_monthly_composites(
    bounds=(500000.0, 5700000.0, 501000.0, 5701000.0),
    crs="EPSG:32631",
    observation_date=date(2025, 7, 12),
    resolution=500.0,
    months_window=(-1, 0, 1),
    history_years=5,
)
```

The collection contains one `MonthlyComposite` per requested month and a stable manifest that does not expose SIAC internals.

