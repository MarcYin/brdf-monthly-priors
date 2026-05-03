# BRDF Monthly Priors

`brdf-monthly-priors` builds schema-versioned monthly BRDF prior composites for a target AOI, CRS, resolution, and observation date. It is designed so SIAC can keep atmospheric correction, SWIR refinement, sensor spectral mapping, and `SurfacePrior` validation while delegating monthly BRDF composite fetch/build/cache behavior to this package.

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

The returned `MonthlyCompositeCollection` is package-neutral. It exposes NumPy-backed monthly composites plus a JSON manifest schema that SIAC or any other consumer can adapt into its own internal classes.

## Scope

This package owns:

- BRDF product fetching hooks for MCD43/VNP43/MCD19-style Earthaccess sources.
- Monthly period planning for target, adjacent, and historical months.
- Monthly best-pixel compositing.
- BRDF quality and sample-index tie-breaking.
- Composite persistence and manifest generation.
- A Python API and CLI for build/retrieve workflows.

SIAC should keep:

- Atmospheric correction.
- SWIR refine query logic that uses the target scene.
- Spectral mapping into the target-sensor basis.
- `SurfacePrior` construction and validation.
- A narrow adapter from this package's neutral collection schema to SIAC internals.

## Installation

```bash
pip install brdf-monthly-priors
```

Optional Earthdata and raster IO support:

```bash
pip install "brdf-monthly-priors[earthdata,raster]"
```

Development install:

```bash
python -m pip install -e ".[dev,docs]"
pytest
```

## CLI

Retrieve from cache or build through a configured source:

```bash
brdf-monthly-priors build \
  --bounds 500000 5700000 501000 5701000 \
  --crs EPSG:32631 \
  --observation-date 2025-07-12 \
  --resolution 500 \
  --history-years 5 \
  --months-window -1 0 1 \
  --cache-dir .brdf-cache
```

For offline tests and local processing, pass a local observation manifest:

```bash
brdf-monthly-priors build \
  --bounds 0 0 1000 1000 \
  --crs EPSG:32631 \
  --observation-date 2025-07-12 \
  --resolution 500 \
  --local-observations examples/observations.json \
  --cache-dir .brdf-cache
```

## Publishing

The repository includes GitHub Actions workflows for tests, package build checks, PyPI trusted publishing on GitHub releases, and MkDocs Material deployment to GitHub Pages.

Actual PyPI publication and GitHub Pages deployment require a GitHub repository with Pages enabled and a PyPI trusted publisher configured for the release workflow.

