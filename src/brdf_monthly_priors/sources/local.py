from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Sequence, Union

import numpy as np

from brdf_monthly_priors.periods import MonthlyPeriod
from brdf_monthly_priors.types import GridSpec, Observation, parse_date


def _same_year_month(left: date, right: date) -> bool:
    return left.year == right.year and left.month == right.month


def _in_period(acquired: date, period: MonthlyPeriod) -> bool:
    return any(_same_year_month(acquired, month) for month in period.history_months)


@dataclass(frozen=True)
class InMemorySource:
    """Observation source for tests, notebooks, and custom integrations."""

    observations: Sequence[Observation]
    name: str = "in-memory"

    def load_observations(
        self,
        *,
        period: MonthlyPeriod,
        grid: GridSpec,
        band_names: Sequence[str],
    ) -> Sequence[Observation]:
        del grid
        requested_bands = tuple(str(band) for band in band_names)
        return tuple(
            observation
            for observation in self.observations
            if tuple(observation.band_names) == requested_bands and _in_period(observation.acquired, period)
        )


class LocalNpzSource:
    """Read observations from a JSON manifest pointing at local NPZ files.

    Manifest example:

    ```json
    {
      "name": "fixture",
      "band_names": ["iso", "vol", "geo"],
      "items": [
        {
          "date": "2024-07-15",
          "path": "obs-2024-07.npz",
          "data_key": "data",
          "quality_key": "quality",
          "sample_index_key": "sample_index"
        }
      ]
    }
    ```
    """

    def __init__(self, manifest_path: Union[str, Path]):
        self.manifest_path = Path(manifest_path).expanduser().resolve()
        with self.manifest_path.open("r", encoding="utf-8") as handle:
            self._manifest = json.load(handle)
        self._name = str(self._manifest.get("name") or f"local-npz:{self.manifest_path.name}")
        self._base_dir = self.manifest_path.parent

    @property
    def name(self) -> str:
        return self._name

    def load_observations(
        self,
        *,
        period: MonthlyPeriod,
        grid: GridSpec,
        band_names: Sequence[str],
    ) -> Sequence[Observation]:
        observations = []
        requested_bands = tuple(str(band) for band in band_names)
        manifest_bands = tuple(self._manifest.get("band_names", requested_bands))
        if manifest_bands != requested_bands:
            raise ValueError(
                f"local observation manifest bands {manifest_bands!r} do not match requested bands {requested_bands!r}"
            )
        for item in self._manifest.get("items", []):
            acquired = parse_date(item["date"])
            if not _in_period(acquired, period):
                continue
            observation = self._read_item(item, acquired=acquired, band_names=requested_bands)
            if observation.data.shape[1:] != grid.shape:
                raise ValueError(
                    f"local observation {observation.source_id!r} has shape {observation.data.shape[1:]}, "
                    f"expected {grid.shape}"
                )
            observations.append(observation)
        return tuple(observations)

    def _read_item(
        self,
        item: Mapping[str, Any],
        *,
        acquired: date,
        band_names: Sequence[str],
    ) -> Observation:
        path = Path(item["path"])
        if not path.is_absolute():
            path = self._base_dir / path
        data_key = str(item.get("data_key", "data"))
        quality_key = str(item.get("quality_key", "quality"))
        sample_index_key = item.get("sample_index_key", "sample_index")
        with np.load(path) as arrays:
            sample_index = None
            if sample_index_key in arrays.files:
                sample_index = arrays[sample_index_key]
            return Observation(
                acquired=acquired,
                data=arrays[data_key],
                quality=arrays[quality_key],
                sample_index=sample_index,
                band_names=band_names,
                source_id=str(item.get("source_id", path.name)),
                metadata={"path": str(path), **dict(item.get("metadata", {}))},
            )
