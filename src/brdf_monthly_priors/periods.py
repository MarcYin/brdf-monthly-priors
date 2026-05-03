from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, Sequence, Tuple, Union

from brdf_monthly_priors.types import parse_date


@dataclass(frozen=True)
class MonthlyPeriod:
    """A requested monthly composite and the source months used to build it."""

    offset: int
    month_start: date
    month_end: date
    history_months: Tuple[date, ...]

    @property
    def month_key(self) -> str:
        return self.month_start.strftime("%Y-%m")

    @property
    def temporal_ranges(self) -> Tuple[Tuple[date, date], ...]:
        return tuple((month, month_end(month)) for month in self.history_months)


def month_start(value: Union[date, str]) -> date:
    parsed = parse_date(value)
    return date(parsed.year, parsed.month, 1)


def month_end(value: Union[date, str]) -> date:
    start = month_start(value)
    return add_months(start, 1) - timedelta(days=1)


def add_months(value: Union[date, str], months: int) -> date:
    parsed = month_start(value)
    month_zero = parsed.month - 1 + months
    year = parsed.year + month_zero // 12
    month = month_zero % 12 + 1
    return date(year, month, 1)


def _history_months(anchor: date, observation_month: date, history_years: int) -> Tuple[date, ...]:
    if history_years <= 0:
        raise ValueError("history_years must be positive")
    latest_year = anchor.year
    if anchor > observation_month:
        latest_year = observation_month.year - 1
    start_year = latest_year - history_years + 1
    return tuple(date(year, anchor.month, 1) for year in range(start_year, latest_year + 1))


def plan_monthly_periods(
    observation_date: Union[date, str],
    months_window: Sequence[int] = (-1, 0, 1),
    history_years: int = 5,
) -> Tuple[MonthlyPeriod, ...]:
    """Plan requested monthly composites and their historical source months.

    The planner avoids lookahead. If a positive offset points to a calendar
    month later than the observation month, the latest history year is shifted
    back by one year.
    """

    observation_month = month_start(observation_date)
    periods = []
    for offset in months_window:
        offset_int = int(offset)
        anchor = add_months(observation_month, offset_int)
        periods.append(
            MonthlyPeriod(
                offset=offset_int,
                month_start=anchor,
                month_end=month_end(anchor),
                history_months=_history_months(anchor, observation_month, int(history_years)),
            )
        )
    return tuple(periods)


def period_month_keys(periods: Iterable[MonthlyPeriod]) -> Tuple[str, ...]:
    return tuple(period.month_key for period in periods)
