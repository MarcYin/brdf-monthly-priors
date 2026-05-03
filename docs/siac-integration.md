# SIAC Integration

The intended SIAC boundary is:

```text
SIAC target scene
  -> SWIR refine query remains in SIAC
  -> Provider.get_monthly_composites(...)
  -> SIAC MonthlyCompositeProvider adapter
  -> SIAC spectral mapping into target sensor basis
  -> SurfacePrior construction and validation
```

The adapter should convert the neutral `MonthlyCompositeCollection` into SIAC's internal `MonthlyCompositeCollection` equivalent. It should not require this package to import SIAC classes.

Recommended adapter responsibilities:

- Pass target AOI bounds, CRS, resolution, observation date, month window, and history years.
- Select or configure the source namespace used for cache keys.
- Validate `schema_version` before adapting.
- Map neutral band names to SIAC's internal BRDF band identifiers.
- Keep target-sensor spectral response mapping in SIAC.

Start by moving only fetch/build/provide monthly composites. Keep the SWIR refine route in SIAC until the new package contract is stable in production.

