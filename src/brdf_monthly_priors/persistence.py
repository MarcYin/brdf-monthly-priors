from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Optional, Union

import numpy as np

from brdf_monthly_priors._version import __version__
from brdf_monthly_priors.types import (
    SCHEMA_VERSION,
    GridSpec,
    MonthlyComposite,
    MonthlyCompositeCollection,
)

MANIFEST_NAME = "manifest.json"


def stable_json_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:24]


class CompositeStore:
    """File-system store for package-neutral monthly composite collections."""

    def __init__(self, root: Union[str, Path]):
        self.root = Path(root).expanduser().resolve()

    def collection_dir(self, request_hash: str) -> Path:
        return self.root / request_hash

    def has_collection(self, request_hash: str) -> bool:
        return (self.collection_dir(request_hash) / MANIFEST_NAME).exists()

    def save(self, request_hash: str, collection: MonthlyCompositeCollection) -> Path:
        destination = self.collection_dir(request_hash)
        composites_dir = destination / "composites"
        composites_dir.mkdir(parents=True, exist_ok=True)
        array_paths = {}
        for composite in collection.composites:
            filename = f"{composite.month_key}.npz"
            array_path = composites_dir / filename
            np.savez_compressed(
                array_path,
                data=composite.data,
                quality=composite.quality,
                sample_index=composite.sample_index,
                selected_observation=composite.selected_observation,
                observation_count=composite.observation_count,
            )
            array_paths[composite.month_key] = str(Path("composites") / filename)
        manifest = collection.manifest(array_paths)
        manifest["request_hash"] = request_hash
        manifest["schema_version"] = SCHEMA_VERSION
        manifest["package_version"] = __version__
        with (destination / MANIFEST_NAME).open("w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2, sort_keys=True)
            handle.write("\n")
        return destination

    def load(self, request_hash: str) -> MonthlyCompositeCollection:
        source = self.collection_dir(request_hash)
        manifest_path = source / MANIFEST_NAME
        if not manifest_path.exists():
            raise FileNotFoundError(f"no composite manifest at {manifest_path}")
        return load_collection(source)


def load_collection(path: Union[str, Path]) -> MonthlyCompositeCollection:
    source = Path(path)
    with (source / MANIFEST_NAME).open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"unsupported schema_version {manifest.get('schema_version')!r}; expected {SCHEMA_VERSION!r}"
        )
    grid = GridSpec.from_dict(manifest["grid"])
    composites = []
    for entry in manifest["composites"]:
        array_path = source / entry["array_path"]
        with np.load(array_path) as arrays:
            composites.append(
                MonthlyComposite(
                    month_start=entry["month_start"],
                    month_end=entry["month_end"],
                    history_months=entry["history_months"],
                    grid=grid,
                    band_names=entry["band_names"],
                    data=arrays["data"],
                    quality=arrays["quality"],
                    sample_index=arrays["sample_index"],
                    selected_observation=arrays["selected_observation"],
                    observation_count=arrays["observation_count"],
                    source_items=entry.get("source_items", ()),
                    attrs=entry.get("attrs", {}),
                )
            )
    return MonthlyCompositeCollection(
        request=manifest["request"],
        grid=grid,
        composites=tuple(composites),
        schema_version=manifest["schema_version"],
        created_at=manifest["created_at"],
        package_version=manifest.get("package_version", "unknown"),
    )


def manifest_path(path: Union[str, Path], request_hash: Optional[str] = None) -> Path:
    base = Path(path).expanduser().resolve()
    if request_hash is not None:
        base = base / request_hash
    return base / MANIFEST_NAME
