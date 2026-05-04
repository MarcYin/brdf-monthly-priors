# STAC And GeoTIFF Schema

The store layout is:

```text
<cache-root>/
  <request-hash>/
    stac-item.json
    assets/
      prior.tif
      uncertainty.tif
```

## Prior Asset

`assets/prior.tif` is a tiled, DEFLATE-compressed GeoTIFF with no overviews.

- Data type: `uint16`
- Scale factor: `10000`
- Stored value: `round(prior * 10000)`
- Nodata: `65535`
- Bands: one band per BRDF prior band

## Uncertainty Asset

`assets/uncertainty.tif` is a tiled, DEFLATE-compressed GeoTIFF with no overviews.

- Data type: `uint8`
- Unit: percent relative uncertainty
- Valid range: `0` to `200`
- Suspicious or missing value: `255`
- Bands: one uncertainty band per prior band

## STAC Item

`stac-item.json` uses STAC `1.0.0` plus the projection and raster extensions.

Important fields:

- `assets.prior.href`: relative path to `assets/prior.tif`
- `assets.uncertainty.href`: relative path to `assets/uncertainty.tif`
- `proj:wkt2`: native CRS
- `proj:shape`: raster shape
- `proj:transform`: affine transform
- `proj:bbox`: native-projection bounds
- `bbox` and `geometry`: caller-supplied WGS84 bounds and geometry when available

The STAC Item is the package-neutral output contract.
