# STAC And GeoTIFF Schema

The store layout is:

```text
<cache-root>/
  <request-hash>/
    stac-item.json
    assets/
      prior/
        01-brdf_iso_red.tif
        02-brdf_vol_red.tif
      uncertainty/
        01-brdf_iso_red.tif
        02-brdf_vol_red.tif
```

## Prior Assets

Each `assets/prior/<index>-<band>.tif` file is a tiled, DEFLATE-compressed
single-band GeoTIFF with no overviews.

- Data type: `uint16`
- Scale factor: `10000`
- Stored value: `round(prior * 10000)`
- Nodata: `65535`
- Bands: exactly one band per GeoTIFF

## Uncertainty Assets

Each `assets/uncertainty/<index>-<band>.tif` file is a tiled,
DEFLATE-compressed single-band GeoTIFF with no overviews.

- Data type: `uint8`
- Unit: percent relative uncertainty
- Valid range: `0` to `200`
- Suspicious or missing value: `255`
- Bands: exactly one uncertainty band per GeoTIFF

## STAC Item

`stac-item.json` uses STAC `1.0.0` plus the projection and raster extensions.

Important fields:

- `properties.brdf:schema_version`: package output schema version
- `properties.brdf:asset_layout`: `single-band-geotiff-per-band`
- `properties.brdf:band_names`: ordered BRDF band list
- `assets.*.href`: relative path to a one-band GeoTIFF
- `assets.*.brdf:asset_kind`: `prior` or `uncertainty`
- `assets.*.brdf:band_name`: source BRDF band name
- `assets.*.brdf:band_index`: zero-based band order
- `proj:wkt2`: native CRS
- `proj:shape`: raster shape
- `proj:transform`: affine transform
- `proj:bbox`: native-projection bounds
- `bbox` and `geometry`: caller-supplied WGS84 bounds and geometry when available

Each STAC asset has exactly one `raster:bands` entry. Prior assets advertise
`uint16` with scale `0.0001`; uncertainty assets advertise `uint8`, percent
units, valid statistics from `0` to `200`, and nodata `255`.

The STAC Item is the package-neutral output contract.
