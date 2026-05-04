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
  --wgs84-bounds 0 0 1 1 \
  --brdf-crs EPSG:4326 \
  --resolution 500 \
  --band iso \
  --local-observations observations.json \
  --cache-dir .brdf-cache
```

## Earthaccess Input

Earthaccess builds need explicit temporal ranges. The package does not plan months or years.
Use `--sample-every-days` to query one-day windows at a fixed stride inside
each range when a full range would download more observations than needed.

```bash
pip install "brdf-monthly-priors[earthdata]"
```

```bash
brdf-monthly-priors build \
  --product-id mcd19-prior \
  --product mcd19 \
  --temporal-range 2024-07-01 2024-07-31 \
  --sample-every-days 7 \
  --wgs84-bounds -2.0 51.0 -1.0 52.0 \
  --resolution 0.005 \
  --band brdf_iso_red \
  --band-pattern brdf_iso_red=BRDF_Albedo_Parameters_Band1 \
  --quality-pattern Quality
```

MCD43/VNP43 deployments often split BRDF parameters and quality across collections. Use the `ProductReader` protocol to pair those files if a single raster container does not contain every required band.

## Google Earth Engine Input

Install the `gee` extra and authenticate Earth Engine as required by `edown`.

```bash
pip install "brdf-monthly-priors[gee]"
```

The built-in GEE preset downloads `MODIS/061/MCD43A1` through `edown`:

```bash
brdf-monthly-priors build \
  --product-id mcd43a1-prior \
  --gee-product mcd43a1 \
  --temporal-range 2024-07-01 2024-07-31 \
  --sample-every-days 7 \
  --wgs84-bounds -2.0 51.0 -1.0 52.0 \
  --resolution 500 \
  --cache-dir .brdf-cache \
  --edown-output-root .brdf-gee-cache
```

For the July range above, `--sample-every-days 7` queries `2024-07-01`,
`2024-07-08`, `2024-07-15`, `2024-07-22`, and `2024-07-29`.

For a generic Earth Engine ImageCollection, pass the collection ID and explicit data/quality band mappings:

```bash
brdf-monthly-priors build \
  --product-id custom-gee-prior \
  --gee-collection-id MODIS/061/MCD43A1 \
  --temporal-range 2024-07-01 2024-07-31 \
  --sample-every-days 7 \
  --wgs84-bounds -2.0 51.0 -1.0 52.0 \
  --resolution 500 \
  --band brdf_iso_red \
  --gee-band brdf_iso_red=BRDF_Albedo_Parameters_Band1_iso \
  --gee-quality-band brdf_iso_red=BRDF_Albedo_Band_Mandatory_Quality_Band1
```
