from __future__ import annotations

from typing import Protocol, Sequence

from surface_priors.types import GridSpec, Observation


class ObservationSource(Protocol):
    """Protocol for sources that return native-grid prior observations."""

    @property
    def name(self) -> str:
        """Stable source name included in request hashes."""

    def load_observations(
        self,
        *,
        grid: GridSpec,
        band_names: Sequence[str],
    ) -> Sequence[Observation]:
        """Return observations already aligned to `grid`."""
