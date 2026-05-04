# CLI

The installed command is:

```bash
brdf-monthly-priors --help
```

## Local NPZ Input

Local NPZ files are an input convenience for offline builds. The output is always STAC plus GeoTIFF assets.

Create a local observation manifest:

```json
{
  "name": "local-fixture",
  "band_names": ["iso"],
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

Build:

```bash
brdf-monthly-priors build \
  --product-id local-prior \
  --bounds 0 0 1000 1000 \
  --crs EPSG:4326 \
  --resolution 500 \
  --band iso \
  --local-observations observations.json \
  --cache-dir .brdf-cache
```

## Earthaccess Input

Earthaccess builds need explicit temporal ranges. The package does not plan months or years.

```bash
pip install "brdf-monthly-priors[earthdata]"
```

```bash
brdf-monthly-priors build \
  --product-id mcd19-prior \
  --product mcd19 \
  --temporal-range 2024-07-01 2024-07-31 \
  --bounds -2.0 51.0 -1.0 52.0 \
  --crs EPSG:4326 \
  --resolution 0.005 \
  --band brdf_iso_red \
  --band-pattern brdf_iso_red=BRDF_Albedo_Parameters_Band1 \
  --quality-pattern Quality
```

MCD43/VNP43 deployments often split BRDF parameters and quality across collections. Use the `ProductReader` protocol to pair those files if a single raster container does not contain every required band.

