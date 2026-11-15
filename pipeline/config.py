"""Chemins du projet et chargement de la configuration YAML (pipeline/settings/*.yaml).

Arborescence des données (partagée avec le backend, voir docs/data/contrat-donnees.md) :
  data/reference/            limites administratives versionnées (MAP TOGO, HDX)
  data/raw/                  téléchargements bruts                     (non versionné)
  data/interim/cubes/        un GeoTIFF par indicateur et par mois     (non versionné)
  data/interim/work/         unités, poids zonaux, tables de travail   (non versionné)
  data/api/                  livrable complet : fiches, tables, couches (non versionné, régénérable)
  data/regions.geojson             ┐
  data/processed/monthly.parquet   ├ livrable P2 lu par le backend (versionné)
  data/processed/static.json       ┘
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parent                      # racine du dépôt (backend/, pipeline/, data/…)
CONFIG_DIR = PACKAGE / "settings"
DATA = Path(os.environ.get("AGBEA_DATA_DIR", ROOT / "data"))
RAW = DATA / "raw"
INTERIM = DATA / "interim"
PROCESSED = INTERIM / "work"               # fichiers de travail du pipeline
API = DATA / "api"                         # livrable complet (fiches, tables, couches)
BACKEND_REGIONS = DATA / "regions.geojson"           # livrable P2
BACKEND_PROCESSED = DATA / "processed"               # livrable P2 : monthly.parquet, static.json

PIPELINE_VERSION = "0.2.0"


def _load(name: str) -> dict:
    with open(CONFIG_DIR / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache
def settings() -> dict:
    s = _load("settings.yaml")
    # surcharge ponctuelle du parallélisme sans toucher au YAML : AGBEA_MAX_WORKERS=16
    if os.environ.get("AGBEA_MAX_WORKERS"):
        s["network"]["max_workers"] = int(os.environ["AGBEA_MAX_WORKERS"])
    return s


@lru_cache
def sites() -> dict:
    return _load("sites.yaml")


@lru_cache
def datasets() -> dict:
    return _load("datasets.yaml")


@dataclass(frozen=True)
class BBox:
    west: float
    south: float
    east: float
    north: float

    def as_tuple(self) -> tuple[float, float, float, float]:
        return (self.west, self.south, self.east, self.north)


def bbox() -> BBox:
    return BBox(**settings()["bbox"])


def ensure_dirs() -> None:
    for p in (RAW, INTERIM, PROCESSED, API, BACKEND_PROCESSED):
        p.mkdir(parents=True, exist_ok=True)
