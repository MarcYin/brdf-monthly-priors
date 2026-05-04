import json
from pathlib import Path

import numpy as np

from surface_priors.cli import main


def test_cli_builds_from_local_manifest(tmp_path, capsys):
    np.savez_compressed(
        tmp_path / "obs.npz",
        data=np.ones((1, 2, 2), dtype="float32") * 0.25,
        quality=np.zeros((2, 2), dtype="uint16"),
        sample_index=np.zeros((2, 2), dtype="int16"),
        uncertainty=np.ones((1, 2, 2), dtype="float32") * 12,
    )
    manifest = {
        "name": "cli-fixture",
        "band_names": ["iso"],
        "items": [{"path": "obs.npz"}],
    }
    manifest_path = tmp_path / "observations.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    cache_dir = tmp_path / "cache"

    exit_code = main(
        [
            "build",
            "--product-id",
            "cli-prior",
            "--wgs84-bounds",
            "0",
            "0",
            "2",
            "2",
            "--native-crs",
            "EPSG:4326",
            "--resolution",
            "1",
            "--band",
            "iso",
            "--cache-dir",
            str(cache_dir),
            "--local-observations",
            str(manifest_path),
        ]
    )

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "request_hash=" in output
    stac_line = next(line for line in output.splitlines() if line.startswith("stac_item="))
    assert Path(stac_line.split("=", 1)[1]).exists()
