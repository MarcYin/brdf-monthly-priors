from brdf_monthly_priors.types import DEFAULT_BRDF_CRS, GridSpec


def test_grid_spec_converts_wgs84_bounds_to_brdf_crs():
    grid = GridSpec.from_wgs84_bounds(
        wgs84_bounds=(-1.0, 51.0, -0.99, 51.01),
        brdf_crs=DEFAULT_BRDF_CRS,
        resolution=500,
    )

    assert grid.wgs84_bounds == (-1.0, 51.0, -0.99, 51.01)
    assert grid.crs == DEFAULT_BRDF_CRS
    assert grid.bounds != grid.wgs84_bounds
    assert grid.width > 0
    assert grid.height > 0


def test_grid_spec_identity_transform_for_wgs84_crs():
    grid = GridSpec.from_wgs84_bounds(
        wgs84_bounds=(0, 0, 2, 2),
        brdf_crs="EPSG:4326",
        resolution=1,
    )

    assert grid.bounds == (0.0, 0.0, 2.0, 2.0)
    assert grid.shape == (2, 2)

