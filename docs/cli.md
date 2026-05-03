# CLI

The installed command is:

```bash
brdf-monthly-priors --help
```

## Local NPZ Build

Create a local observation manifest:

```json
{
  "name": "local-fixture",
  "band_names": ["iso"],
  "items": [
    {
      "date": "2025-07-12",
      "path": "obs-2025-07.npz",
      "data_key": "data",
      "quality_key": "quality",
      "sample_index_key": "sample_index"
    }
  ]
}
```

Build:

```bash
brdf-monthly-priors build \
  --bounds 0 0 1000 1000 \
  --crs EPSG:32631 \
  --observation-date 2025-07-12 \
  --resolution 500 \
  --months-window 0 \
  --history-years 1 \
  --band iso \
  --local-observations observations.json \
  --cache-dir .brdf-cache
```

## Earthaccess Build

Earthaccess builds need the optional extras and a product reader mapping:

```bash
pip install "brdf-monthly-priors[earthdata,raster]"
```

```bash
brdf-monthly-priors build \
  --product mcd19 \
  --bounds -2.0 51.0 -1.0 52.0 \
  --crs EPSG:4326 \
  --observation-date 2025-07-12 \
  --resolution 0.005 \
  --band brdf_iso_red \
  --band-pattern brdf_iso_red=BRDF_Albedo_Parameters_Band1 \
  --quality-pattern Quality
```

MCD43/VNP43 deployments often split BRDF parameters and quality across collections. Use the `ProductReader` protocol to pair those files if a single raster container does not contain every required band.

