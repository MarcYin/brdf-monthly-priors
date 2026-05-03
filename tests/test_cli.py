import json
from pathlib import Path

import numpy as np

from brdf_monthly_priors.cli import main


def test_cli_builds_from_local_manifest(tmp_path, capsys):
    np.savez_compressed(
        tmp_path / "obs.npz",
        data=np.ones((1, 2, 2), dtype="float32"),
        quality=np.zeros((2, 2), dtype="uint16"),
        sample_index=np.zeros((2, 2), dtype="int16"),
    )
    manifest = {
        "name": "cli-fixture",
        "band_names": ["iso"],
        "items": [{"date": "2025-07-12", "path": "obs.npz"}],
    }
    manifest_path = tmp_path / "observations.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    cache_dir = tmp_path / "cache"

    exit_code = main(
        [
            "build",
            "--bounds",
            "0",
            "0",
            "2",
            "2",
            "--crs",
            "EPSG:32631",
            "--observation-date",
            "2025-07-12",
            "--resolution",
            "1",
            "--months-window",
            "0",
            "--history-years",
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
    manifest_line = next(line for line in output.splitlines() if line.startswith("manifest="))
    assert Path(manifest_line.split("=", 1)[1]).exists()

