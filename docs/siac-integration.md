# SIAC Integration

The intended SIAC boundary is:

```text
SIAC target scene
  -> SIAC decides which prior observations are relevant
  -> Provider.build_prior(...)
  -> STAC Item + tiled GeoTIFF assets
  -> SIAC reads/scales prior and uncertainty assets
  -> SIAC spectral mapping into target sensor basis
  -> SurfacePrior construction and validation
```

The package does not know about observation dates, target months, adjacent months, or history years. Those are SIAC usage policy.

Recommended adapter responsibilities:

- Select the BRDF observations to composite.
- Keep observations on their native MODIS/VIIRS projection and grid.
- Pass WGS84 bounds, native BRDF CRS, resolution, product id, and band names to `Provider.build_prior`.
- Let this package convert WGS84 bounds to native BRDF grid bounds.
- Validate `brdf:schema_version` on the returned STAC Item.
- Read `prior.tif` as `uint16` and apply scale `0.0001`.
- Read `uncertainty.tif` as relative percent uncertainty; treat `255` as suspicious/missing.
- Keep target-sensor spectral response mapping in SIAC.

Start by moving only fetch/build/provide prior composites. Keep SWIR refine and target-scene-specific logic in SIAC.
