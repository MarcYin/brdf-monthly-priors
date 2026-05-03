# Persistence Schema

The store layout is:

```text
<cache-root>/
  <request-hash>/
    manifest.json
    composites/
      2025-06.npz
      2025-07.npz
      2025-08.npz
```

`manifest.json` is the package-neutral contract. It contains:

- `schema_version`: currently `brdf-monthly-priors/v1`.
- `package_version`: package version that wrote the store.
- `request`: AOI, CRS, resolution, observation date, month window, history years, band names, and source namespace.
- `grid`: bounds, CRS, resolution, shape, and affine transform tuple.
- `composites`: per-month metadata and relative array path.

Each `.npz` file contains:

- `data`: float array with shape `(bands, height, width)`.
- `quality`: selected source quality value per pixel.
- `sample_index`: selected source sample index per pixel, or `-1`.
- `selected_observation`: zero-based source observation index, or `-1`.
- `observation_count`: number of usable observations seen per pixel.

Consumers should treat the JSON manifest as the stable schema and the NPZ files as array payloads referenced by that manifest.
