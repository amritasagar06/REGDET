"""Loading prompts and the golden dataset from disk."""
import json

import yaml

from .models import GoldenCase, PromptConfig


def load_prompt(path: str) -> PromptConfig:
    with open(path, encoding="utf-8") as f:
        return PromptConfig(**yaml.safe_load(f))


def load_dataset(path: str) -> tuple[str, list[GoldenCase]]:
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    cases = [GoldenCase(**c) for c in raw["cases"]]
    ids = [c.id for c in cases]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"Duplicate case ids in dataset: {sorted(dupes)}")
    return raw["dataset_version"], cases
