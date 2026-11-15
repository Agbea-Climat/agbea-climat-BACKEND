"""Faits chiffrés pour l'assistant (nœud fetch_data) : uniquement via backend.services.

Chaque fait porte une source `computed:<region>:<indicator>:<date>` : c'est la seule origine
autorisée pour un chiffre dans une réponse de l'IA (règle 5 de CLAUDE.md).
"""
from typing import Optional

from backend.schemas import IndicatorSnapshot, Source
from backend.services import catalog, indicators, regions


def computed_id(s: IndicatorSnapshot, region_id: str) -> str:
    return f"computed:{region_id}:{s.indicator}:{s.date}"


def snapshots(region_id: str, inds: list[str], date: Optional[str] = None) -> list[IndicatorSnapshot]:
    summary = indicators.summary(region_id, date, mode="scientific")
    return [s for s in summary.indicators if s.indicator in inds]


def facts_and_sources(region_id: str, snaps: list[IndicatorSnapshot]) -> tuple[list[dict], list[Source]]:
    region = regions.get_region(region_id)
    facts, sources, seen_ds = [], [], set()
    for s in snaps:
        sid = computed_id(s, region_id)
        facts.append({"source_id": sid, "text": f"{region.name} — {s.plain_summary}", "indicator": s.indicator})
        ds = catalog.get_dataset(s.dataset_id)
        sources.append(Source(id=sid, kind="computed", title=f"{s.label} — {region.name} ({s.date})",
                              dataset_id=ds.id, url=ds.source_url))
        if ds.id not in seen_ds:
            seen_ds.add(ds.id)
            sources.append(Source(id=f"ds:{ds.id}", kind="dataset", title=ds.name, dataset_id=ds.id, url=ds.source_url))
    return facts, sources


def elevation_fact(region_id: str) -> Optional[tuple[dict, Source]]:
    from backend.repositories import store
    try:
        e = store.static()["regions"][region_id]["elevation"]
    except (KeyError, store.DataUnavailable):
        return None
    region = regions.get_region(region_id)
    ds = catalog.get_dataset("srtm")
    sid = f"computed:{region_id}:elevation:static"
    text = (f"{region.name} — Altitude (NASADEM) : moyenne {e['mean']} m, médiane {e['median']} m, "
            f"10 % des points sous {e['p10']} m, maximum {e['max']} m.")
    return ({"source_id": sid, "text": text, "indicator": "elevation"},
            Source(id=sid, kind="computed", title=f"Altitude — {region.name}", dataset_id=ds.id, url=ds.source_url))
