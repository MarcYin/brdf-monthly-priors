from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

from brdf_monthly_priors.quality import QualityRules, score_pixels, valid_pixel_mask
from brdf_monthly_priors.types import GridSpec, Observation, PriorComposite


@dataclass(frozen=True)
class PriorCompositor:
    """Build a best-pixel BRDF prior from native-grid observations."""

    quality_rules: QualityRules = field(default_factory=QualityRules)
    output_dtype: str = "float32"

    def compose(
        self,
        *,
        product_id: str,
        grid: GridSpec,
        band_names: Sequence[str],
        observations: Sequence[Observation],
    ) -> PriorComposite:
        band_names = tuple(str(band) for band in band_names)
        if not observations:
            return self._empty(product_id=product_id, grid=grid, band_names=band_names)

        self._validate_observations(observations, grid, band_names)
        band_count = len(band_names)
        height, width = grid.shape
        best_score = np.full((height, width), np.inf, dtype="float64")
        best_data = np.full((band_count, height, width), np.nan, dtype=self.output_dtype)
        best_uncertainty = np.full((band_count, height, width), np.nan, dtype="float32")
        best_quality = np.full((height, width), self.quality_rules.nodata_quality, dtype="uint16")
        best_sample_index = np.full((height, width), -1, dtype="int16")
        selected_observation = np.full((height, width), -1, dtype="int16")
        observation_count = np.zeros((height, width), dtype="uint16")
        valid_stack = []
        data_stack = []
        source_items = []

        for obs_index, observation in enumerate(observations):
            quality = observation.quality
            valid_mask = valid_pixel_mask(observation.data, quality, self.quality_rules)
            observation_count += valid_mask.astype("uint16")
            valid_stack.append(valid_mask)
            data_stack.append(observation.data.astype("float32", copy=False))
            score = score_pixels(
                quality=quality,
                sample_index=observation.sample_index,
                valid_mask=valid_mask,
                source_order=obs_index,
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
                if observation.uncertainty is not None:
                    uncertainty = _expand_uncertainty(observation.uncertainty, band_count)
                    best_uncertainty[:, replace] = uncertainty.astype("float32", copy=False)[:, replace]
            source_items.append(
                {
                    "source_id": observation.source_id,
                    "metadata": dict(observation.metadata),
                }
            )

        missing_uncertainty = ~np.isfinite(best_uncertainty)
        if np.any(missing_uncertainty):
            fallback_uncertainty = relative_uncertainty_from_stack(
                data_stack=tuple(data_stack),
                valid_stack=tuple(valid_stack),
                reference=best_data,
            )
            best_uncertainty = np.where(missing_uncertainty, fallback_uncertainty, best_uncertainty)

        return PriorComposite(
            product_id=product_id,
            grid=grid,
            band_names=band_names,
            data=best_data,
            uncertainty=best_uncertainty,
            quality=best_quality,
            sample_index=best_sample_index,
            selected_observation=selected_observation,
            observation_count=observation_count,
            source_items=source_items,
            attrs={"compositor": "best_pixel_v2"},
        )

    def _empty(
        self,
        *,
        product_id: str,
        grid: GridSpec,
        band_names: Sequence[str],
    ) -> PriorComposite:
        band_count = len(band_names)
        height, width = grid.shape
        return PriorComposite(
            product_id=product_id,
            grid=grid,
            band_names=band_names,
            data=np.full((band_count, height, width), np.nan, dtype=self.output_dtype),
            uncertainty=np.full((band_count, height, width), np.nan, dtype="float32"),
            quality=np.full((height, width), self.quality_rules.nodata_quality, dtype="uint16"),
            sample_index=np.full((height, width), -1, dtype="int16"),
            selected_observation=np.full((height, width), -1, dtype="int16"),
            observation_count=np.zeros((height, width), dtype="uint16"),
            source_items=(),
            attrs={"compositor": "best_pixel_v2", "empty": True},
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
                raise ValueError("all observations must be aligned to the native grid")


MonthlyCompositor = PriorCompositor


def _expand_uncertainty(uncertainty: np.ndarray, band_count: int) -> np.ndarray:
    uncertainty = np.asarray(uncertainty)
    if uncertainty.ndim == 2:
        return np.broadcast_to(uncertainty, (band_count, *uncertainty.shape))
    return uncertainty


def relative_uncertainty_from_stack(
    *,
    data_stack: Sequence[np.ndarray],
    valid_stack: Sequence[np.ndarray],
    reference: np.ndarray,
) -> np.ndarray:
    if not data_stack:
        return np.full_like(reference, np.nan, dtype="float32")
    stacked = np.stack(data_stack, axis=0).astype("float32", copy=False)
    valid = np.stack(valid_stack, axis=0)
    stacked = np.where(valid[:, None, :, :], stacked, np.nan)
    std = np.nanstd(stacked, axis=0)
    denominator = np.abs(reference)
    with np.errstate(divide="ignore", invalid="ignore"):
        uncertainty = (std / denominator) * 100.0
    return np.where(np.isfinite(reference) & (denominator > 0), uncertainty, np.nan).astype("float32")

