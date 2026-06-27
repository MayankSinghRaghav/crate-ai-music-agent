"""Catalog source abstraction.

`SeedCatalogSource` reads the local data/*.json so Crate demos with no Spotify
API. The `CatalogSource` seam is where the real Spotify Web API drops in later.
"""
from __future__ import annotations

import json
from typing import Protocol

from .config import settings


class CatalogSource(Protocol):
    def tracks(self) -> list[dict]: ...
    def personas(self) -> list[dict]: ...


class SeedCatalogSource:
    def __init__(self, data_dir=None):
        self.data_dir = data_dir or settings.data_dir

    def tracks(self) -> list[dict]:
        with open(self.data_dir / "catalog.json", encoding="utf-8") as f:
            return json.load(f)

    def personas(self) -> list[dict]:
        with open(self.data_dir / "personas.json", encoding="utf-8") as f:
            return json.load(f)


def get_catalog() -> CatalogSource:
    return SeedCatalogSource()
