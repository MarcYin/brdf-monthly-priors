from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Sequence

import numpy as np

from brdf_monthly_priors.periods import MonthlyPeriod
from brdf_monthly_priors.quality import QualityRules, score_pixels, valid_pixel_mask
from brdf_monthly_priors.types import GridSpec, MonthlyComposite, Observation


@dataclass(frozen=True)
class MonthlyCompositor:
    """Build best-pixel monthly composites from grid-aligned observations."""

    quality_rules: QualityRules = field(default_factory=QualityRules)
    output_dtype: str = "float32"

    def compose(
        self,
        *,
        period: MonthlyPeriod,
        grid: GridSpec,
        band_names: Sequence[str],
        observations: Sequence[Observation],
        preferred_date: date,
    ) -> MonthlyComposite:
        band_names = tuple(str(band) for band in band_names)
        if not observations:
            return self._empty(period=period, grid=grid, band_names=band_names)

        self._validate_observations(observations, grid, band_names)
        band_count = len(band_names)
        height, width = grid.shape
        best_score = np.full((height, width), np.inf, dtype="float64")
        best_data = np.full((band_count, height, width), np.nan, dtype=self.output_dtype)
        best_quality = np.full((height, width), self.quality_rules.nodata_quality, dtype="uint16")
        best_sample_index = np.full((height, width), -1, dtype="int16")
        selected_observation = np.full((height, width), -1, dtype="int16")
        observation_count = np.zeros((height, width), dtype="uint16")

        source_items = []
        for obs_index, observation in enumerate(observations):
            quality = observation.quality
            valid_mask = valid_pixel_mask(observation.data, quality, self.quality_rules)
            observation_count += valid_mask.astype("uint16")
            score = score_pixels(
                quality=quality,
                acquired=observation.acquired,
                preferred_date=preferred_date,
                sample_index=observation.sample_index,
                valid_mask=valid_mask,
                rules=self.quality_rules,
            )
            replace = score < best_score
            if np.any(replace):
                best_score[replace] = score[replace]
                best_quality[replace] = quality.astype("uint16", copy=False)[replace]
                if observation.sample_index is not None:
                    best_sample_index[replace] = observation.sample_index.astype("int16", copy=False)[replace]
                selected_observation[replace] = obs_index
                best_data[:, replace] = observation.data.astype(self.output_dtype, copy=False)[:, replace]
            source_items.append(
                {
                    "source_id": observation.source_id,
                    "acquired": observation.acquired.isoformat(),
                    "metadata": dict(observation.metadata),
                }
            )

        return MonthlyComposite(
            month_start=period.month_start,
            month_end=period.month_end,
            history_months=period.history_months,
            grid=grid,
            band_names=band_names,
            data=best_data,
            quality=best_quality,
            sample_index=best_sample_index,
            selected_observation=selected_observation,
            observation_count=observation_count,
            source_items=source_items,
            attrs={"compositor": "best_pixel_v1"},
        )

    def _empty(
        self,
        *,
        period: MonthlyPeriod,
        grid: GridSpec,
        band_names: Sequence[str],
    ) -> MonthlyComposite:
        band_count = len(band_names)
        height, width = grid.shape
        return MonthlyComposite(
            month_start=period.month_start,
            month_end=period.month_end,
            history_months=period.history_months,
            grid=grid,
            band_names=band_names,
            data=np.full((band_count, height, width), np.nan, dtype=self.output_dtype),
            quality=np.full((height, width), self.quality_rules.nodata_quality, dtype="uint16"),
            sample_index=np.full((height, width), -1, dtype="int16"),
            selected_observation=np.full((height, width), -1, dtype="int16"),
            observation_count=np.zeros((height, width), dtype="uint16"),
            source_items=(),
            attrs={"compositor": "best_pixel_v1", "empty": True},
        )

    @staticmethod
    def _validate_observations(
        observations: Sequence[Observation],
        grid: GridSpec,
        band_names: Sequence[str],
    ) -> None:
        for observation in observations:
            if tuple(observation.band_names) != tuple(band_names):
                raise ValueError("all observations must use the requested band_names")
            if observation.data.shape[1:] != grid.shape:
                raise ValueError("all observations must be aligned to the requested grid")

