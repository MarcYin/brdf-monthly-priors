from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence, Union

import numpy as np

from surface_priors.types import GridSpec, Observation


@dataclass(frozen=True)
class InMemorySource:
    """Observation source for tests, notebooks, and custom integrations."""

    observations: Sequence[Observation]
    name: str = "in-memory"

    def load_observations(
        self,
        *,
        grid: GridSpec,
        band_names: Sequence[str],
    ) -> Sequence[Observation]:
        requested_bands = tuple(str(band) for band in band_names)
        observations = []
        for observation in self.observations:
            if tuple(observation.band_names) != requested_bands:
                continue
            if observation.data.shape[1:] != grid.shape:
                raise ValueError(
                    f"observation {observation.source_id!r} has shape {observation.data.shape[1:]}, "
                    f"expected {grid.shape}"
                )
            observations.append(observation)
        return tuple(observations)


class LocalNpzSource:
    """Read native-grid observations from a JSON manifest pointing at local NPZ files.

    The source reads all manifest items. Temporal filtering belongs to the
    calling application, which can write a manifest for the exact observations
    that should enter one prior composite.
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
            observation = self._read_item(item, band_names=requested_bands)
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
        band_names: Sequence[str],
    ) -> Observation:
        path = Path(item["path"])
        if not path.is_absolute():
            path = self._base_dir / path
        data_key = str(item.get("data_key", "data"))
        quality_key = str(item.get("quality_key", "quality"))
        sample_index_key = item.get("sample_index_key", "sample_index")
        uncertainty_key = item.get("uncertainty_key", "uncertainty")
        with np.load(path) as arrays:
            sample_index = None
            if sample_index_key in arrays.files:
                sample_index = arrays[sample_index_key]
            uncertainty = None
            if uncertainty_key in arrays.files:
                uncertainty = arrays[uncertainty_key]
            return Observation(
                data=arrays[data_key],
                quality=arrays[quality_key],
                uncertainty=uncertainty,
                sample_index=sample_index,
                band_names=band_names,
                source_id=str(item.get("source_id", path.name)),
                metadata={"path": str(path), **dict(item.get("metadata", {}))},
            )

