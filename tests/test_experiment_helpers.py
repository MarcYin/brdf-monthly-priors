import importlib.util
import sys
from datetime import date
from pathlib import Path

import numpy as np


def load_experiment_module():
    path = Path(__file__).parents[1] / "examples" / "gee_vs_official_mcd43a1.py"
    spec = importlib.util.spec_from_file_location("gee_vs_official_mcd43a1", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


experiment = load_experiment_module()


def test_native_mcd43_date_reads_earthdata_native_id():
    result = {"meta": {"native-id": "MCD43A1.A2024183.h17v03.061.2024193205134.hdf"}}

    assert experiment.native_mcd43_date(result) == date(2024, 7, 1)


def test_filter_results_by_native_date_excludes_overlapping_windows():
    results = [
        {"meta": {"native-id": "MCD43A1.A2024176.h17v03.061.2024185041201.hdf"}},
        {"umm": {"GranuleUR": "MCD43A1.A2024183.h17v03.061.2024193205134.hdf"}},
        {"meta": {"native-id": "MCD43A1.A2024184.h17v03.061.2024193205135.hdf"}},
    ]

    filtered = experiment.filter_results_by_native_date(
        results,
        start_date="2024-07-01",
        end_date="2024-07-01",
    )

    assert filtered == [results[1]]


def test_composite_period_label_uses_month_for_single_month_ranges():
    assert experiment.composite_period_label("2024-07-01", "2024-07-31") == "2024-07"
    assert experiment.composite_period_label("2024-07-20", "2024-08-05") == "2024-07-20..2024-08-05"


def test_band_comparison_metrics_reports_scatter_statistics():
    gee = np.array([[1.0, 2.0], [np.nan, 4.0]], dtype="float32")
    official = np.array([[1.0, 2.1], [3.0, np.nan]], dtype="float32")
    gee_encoded = np.array([[10, 20], [65535, 40]], dtype="uint16")
    official_encoded = np.array([[10, 21], [30, 65535]], dtype="uint16")

    metrics = experiment.band_comparison_metrics(
        gee=gee,
        official=official,
        gee_encoded=gee_encoded,
        official_encoded=official_encoded,
    )

    assert metrics["joint_valid_pixels"] == 2
    assert metrics["gee_only_valid_pixels"] == 1
    assert metrics["official_only_valid_pixels"] == 1
    assert metrics["encoded_prior_equal_pixels"] == 1
    assert metrics["encoded_prior_equal_fraction"] == 0.25
    assert metrics["rmse_float_difference"] > 0
    assert metrics["r2"] is not None
