"""SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".

Loader for the dataset capability registry (`datasets.yaml`).

The location -> terrain-stack resolver is in lss/registry/terrain.py.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from lss.contract import DatasetCapability

REGISTRY_PATH = Path(__file__).with_name("datasets.yaml")


@lru_cache(maxsize=1)
def load_datasets(path: Path = REGISTRY_PATH) -> tuple[DatasetCapability, ...]:
    """Parse and validate every registry entry; raises on a bad entry or duplicate id."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    datasets = tuple(DatasetCapability.model_validate(d) for d in raw["datasets"])
    ids = [d.id for d in datasets]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"duplicate dataset ids in registry: {sorted(dupes)}")
    return datasets


def get_dataset(dataset_id: str) -> DatasetCapability:
    for d in load_datasets():
        if d.id == dataset_id:
            return d
    raise KeyError(dataset_id)
