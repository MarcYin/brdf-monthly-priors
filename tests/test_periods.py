from datetime import date

from brdf_monthly_priors.periods import add_months, plan_monthly_periods


def test_add_months_handles_year_boundaries():
    assert add_months(date(2025, 1, 15), -1) == date(2024, 12, 1)
    assert add_months(date(2025, 12, 15), 1) == date(2026, 1, 1)


def test_plan_monthly_periods_avoids_future_lookahead():
    periods = plan_monthly_periods(date(2025, 1, 15), months_window=(-1, 0, 1), history_years=3)

    assert [period.month_key for period in periods] == ["2024-12", "2025-01", "2025-02"]
    assert periods[0].history_months == (
        date(2022, 12, 1),
        date(2023, 12, 1),
        date(2024, 12, 1),
    )
    assert periods[1].history_months == (
        date(2023, 1, 1),
        date(2024, 1, 1),
        date(2025, 1, 1),
    )
    assert periods[2].history_months == (
        date(2022, 2, 1),
        date(2023, 2, 1),
        date(2024, 2, 1),
    )

