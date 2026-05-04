from __future__ import annotations

from datetime import date, timedelta
from typing import Optional, Sequence, Tuple

TemporalRange = Tuple[str, str]


def sample_temporal_ranges(
    temporal_ranges: Sequence[TemporalRange],
    *,
    sample_every_days: Optional[int] = None,
) -> tuple[TemporalRange, ...]:
    """Return source query windows after optional day-stride sampling.

    With no sampling, ranges are preserved exactly. With sampling enabled, each
    input range is expanded into inclusive one-day windows spaced by the
    requested number of days.
    """

    normalized = tuple((str(start), str(end)) for start, end in temporal_ranges)
    if sample_every_days is None:
        return normalized

    stride_days = int(sample_every_days)
    if stride_days <= 0:
        raise ValueError("sample_every_days must be a positive integer")

    sampled = []
    for start, end in normalized:
        start_date = _date_from_iso_prefix(start)
        end_date = _date_from_iso_prefix(end)
        if end_date < start_date:
            raise ValueError(f"temporal range end {end!r} is before start {start!r}")
        current = start_date
        while current <= end_date:
            day = current.isoformat()
            sampled.append((day, day))
            current += timedelta(days=stride_days)
    return tuple(sampled)


def temporal_ranges_name(
    temporal_ranges: Sequence[TemporalRange],
    *,
    sample_every_days: Optional[int] = None,
) -> str:
    temporal_key = ",".join(f"{start}..{end}" for start, end in temporal_ranges)
    if sample_every_days is None:
        return temporal_key
    return f"{temporal_key}:sample-every-{int(sample_every_days)}-days"


def _date_from_iso_prefix(value: str) -> date:
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError as exc:
        raise ValueError(
            "sampled temporal ranges require ISO date strings beginning with YYYY-MM-DD"
        ) from exc
