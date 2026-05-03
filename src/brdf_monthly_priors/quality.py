from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

import numpy as np


@dataclass(frozen=True)
class QualityRules:
    """Scoring rules for best-pixel selection.

    Scores are ordered lexicographically by large numeric weights:
    quality first, temporal distance second, sample index third.
    Lower scores are better.
    """

    max_usable_quality: int = 32767
    nodata_quality: int = 65535
    quality_weight: float = 1_000_000.0
    day_weight: float = 1_000.0
    sample_index_weight: float = 1.0


def valid_pixel_mask(data: np.ndarray, quality: np.ndarray, rules: QualityRules) -> np.ndarray:
    finite_data = np.all(np.isfinite(data), axis=0)
    finite_quality = np.isfinite(quality)
    usable_quality = quality <= rules.max_usable_quality
    return finite_data & finite_quality & usable_quality


def score_pixels(
    *,
    quality: np.ndarray,
    acquired: date,
    preferred_date: date,
    sample_index: Optional[np.ndarray],
    valid_mask: np.ndarray,
    rules: QualityRules,
) -> np.ndarray:
    quality_score = quality.astype("float64", copy=False) * rules.quality_weight
    day_delta = abs((acquired - preferred_date).days)
    date_score = float(day_delta) * rules.day_weight
    if sample_index is None:
        sample_score = 0.0
    else:
        sample_score = np.where(np.isfinite(sample_index), sample_index, rules.nodata_quality)
        sample_score = sample_score.astype("float64", copy=False) * rules.sample_index_weight
    score = quality_score + date_score + sample_score
    return np.where(valid_mask, score, np.inf)

