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
- For Google Earth Engine sources, configure `EdownGeeSource` with SIAC-selected temporal ranges; `edown` downloads the source-native GeoTIFFs and the provider composites those arrays directly.
- Validate `brdf:schema_version` on the returned STAC Item.
- Iterate STAC assets in `properties.brdf:band_names` order using `brdf:asset_kind` and `brdf:band_index`.
- Read each `prior` GeoTIFF as one `uint16` band and apply scale `0.0001`.
- Read each `uncertainty` GeoTIFF as one relative percent uncertainty band; treat `255` as suspicious/missing.
- Keep target-sensor spectral response mapping in SIAC.

Start by moving only fetch/build/provide prior composites. Keep SWIR refine and target-scene-specific logic in SIAC.
