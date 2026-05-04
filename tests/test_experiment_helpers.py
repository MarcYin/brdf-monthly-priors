import importlib.util
import sys
from datetime import date
from pathlib import Path


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
