from datetime import date

from examples.gee_vs_official_mcd43a1 import filter_results_by_native_date, native_mcd43_date


def test_native_mcd43_date_reads_earthdata_native_id():
    result = {"meta": {"native-id": "MCD43A1.A2024183.h17v03.061.2024193205134.hdf"}}

    assert native_mcd43_date(result) == date(2024, 7, 1)


def test_filter_results_by_native_date_excludes_overlapping_windows():
    results = [
        {"meta": {"native-id": "MCD43A1.A2024176.h17v03.061.2024185041201.hdf"}},
        {"umm": {"GranuleUR": "MCD43A1.A2024183.h17v03.061.2024193205134.hdf"}},
        {"meta": {"native-id": "MCD43A1.A2024184.h17v03.061.2024193205135.hdf"}},
    ]

    filtered = filter_results_by_native_date(
        results,
        start_date="2024-07-01",
        end_date="2024-07-01",
    )

    assert filtered == [results[1]]
