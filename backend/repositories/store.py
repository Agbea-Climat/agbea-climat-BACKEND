"""Données d'observation : livrable P2 du pipeline (data/), chargé une seule fois en mémoire.

- data/processed/monthly.parquet : region_id, indicator, date (YYYY-MM), value, valid_frac,
  low_coverage, dataset_id (voir docs/data/contrat-donnees.md)
- data/processed/static.json     : altitude par région
- data/regions.geojson           : contours des 5 régions

Chargement paresseux (au premier appel) : /health ne dépend pas des fichiers. Si un fichier
manque, les routes qui en ont besoin répondent 503 `data_unavailable`.
"""
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

import pandas as pd

from backend.core.config import settings
from backend.core.exceptions import ApiError


@dataclass(frozen=True)
class Obs:
    value: Optional[float]
    valid_frac: Optional[float]
    low_coverage: bool


class DataUnavailable(ApiError):
    status_code = 503


def _path(*parts: str) -> Path:
    return Path(settings.data_dir, *parts)


def _require(p: Path) -> Path:
    if not p.exists():
        raise DataUnavailable("data_unavailable", f"Fichier de données absent : {p} (lancer le pipeline P2)")
    return p


@lru_cache
def monthly() -> pd.DataFrame:
    df = pd.read_parquet(_require(_path("processed", "monthly.parquet")))
    return df.sort_values(["region_id", "indicator", "date"]).reset_index(drop=True)


@lru_cache
def _index() -> dict[tuple[str, str], dict[str, Obs]]:
    """{(region_id, indicator): {date: Obs}}"""
    out: dict[tuple[str, str], dict[str, Obs]] = {}
    for r in monthly().itertuples(index=False):
        v = None if pd.isna(r.value) else float(r.value)
        vf = None if pd.isna(r.valid_frac) else float(r.valid_frac)
        out.setdefault((r.region_id, r.indicator), {})[r.date] = Obs(v, vf, bool(r.low_coverage))
    return out


def observation(region_id: str, indicator: str, date: str) -> Optional[Obs]:
    return _index().get((region_id, indicator), {}).get(date)


def series(region_id: str, indicator: str) -> dict[str, Obs]:
    return _index().get((region_id, indicator), {})


@lru_cache(maxsize=None)
def last_date(indicator: Optional[str] = None, region_id: Optional[str] = None) -> Optional[str]:
    """Dernier mois avec une valeur non nulle (pour un indicateur / une région si précisés)."""
    df = monthly()
    df = df[df.value.notna()]
    if indicator:
        df = df[df.indicator == indicator]
    if region_id:
        df = df[df.region_id == region_id]
    return None if df.empty else str(df.date.max())


@lru_cache(maxsize=None)
def first_date(indicator: Optional[str] = None) -> Optional[str]:
    df = monthly()
    df = df[df.value.notna()]
    if indicator:
        df = df[df.indicator == indicator]
    return None if df.empty else str(df.date.min())


def last_dates() -> dict[str, str]:
    """Dernier mois avec une valeur, par indicateur : {indicator: "YYYY-MM"} (les séries s'arrêtent
    à des mois différents : retard de publication d'IMERG Final, LST arrêtée en 2022-12)."""
    df = monthly()
    return {str(k): str(v) for k, v in df[df.value.notna()].groupby("indicator").date.max().items()}


@lru_cache
def static() -> dict:
    return json.loads(_require(_path("processed", "static.json")).read_text(encoding="utf-8"))


@lru_cache
def regions_geojson() -> dict:
    return json.loads(_require(_path("regions.geojson")).read_text(encoding="utf-8"))


def warm_up() -> None:
    """Précharge les fichiers (appelé au démarrage ; ignoré si les données manquent)."""
    try:
        _index()
        static()
        regions_geojson()
    except DataUnavailable:
        pass
