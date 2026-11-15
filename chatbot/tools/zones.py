"""Préfectures, sites pilotes et régions cités dans une question → fiche du corpus (data/corpus/fiches/, D31).

L'API ne connaît que les 5 régions ; les fiches de zone (générées par `python -m pipeline corpus`) décrivent
aussi les 39 préfectures et les 7 sites pilotes. La liste des zones est lue dans data/corpus/sources.json
(entrées `fiches/…`), donc elle suit le corpus sans liste écrite à la main ici.

Règles de reconnaissance :
- site pilote : sa ville principale (« Lomé », « Kpalimé », « Aného »…) ou un mot propre au site (« Fazao »,
  « Défalé », « Kpémé ») ; un site passe avant la préfecture qui le contient ;
- préfecture : son nom, en entier (« Agoè-Nyivé », « Bas-Mono », « Kpendjal-Ouest ») ;
- noms courts ou ambigus (« Lacs », « Vo », « Mô », « Golfe », « Agou », « Mango »…) : seulement avec un
  contexte (« préfecture des Lacs ») ou une majuscule hors début de phrase, comme pour les régions ;
- l'ordre de la phrase décide entre plusieurs zones ; une zone niée (« pas à Lomé ») est ignorée.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

from backend.core.config import settings
from chatbot.tools import question

FICHES = "fiches/"
# Mots des noms de site qui désignent autre chose (région, mot courant) : jamais des clés de site
_SITE_SKIP = {"grand", "lagune", "littoral", "de", "du", "des", "mont", "corridor", "massif", "confins", "saheliens",
              "bassin", "fluvial", "l", "oti", "kara"}
# Clés qui exigent un contexte ou une majuscule (mots courts, mots courants, noms partagés)
_NEEDS_CONTEXT = set(question.AMBIGUOUS) | {"mo", "agou", "amou", "ogou", "haho", "wawa", "golfe", "lacs", "ave",
                                            "vo", "zio", "yoto", "oti", "mango", "danyi", "assoli", "est"}


@dataclass(frozen=True)
class Zone:
    file: str           # fiches/<niveau>_<nom>.md
    title: str
    name: str           # nom affiché (« Kpalimé & Mont Agou », « Agoè-Nyivé »)
    level: str          # region | prefecture | site | country
    region_id: Optional[str]

    def as_dict(self) -> dict:
        return {"file": self.file, "title": self.title, "name": self.name, "level": self.level,
                "region_id": self.region_id}


def _level(file: str) -> str:
    stem = file[len(FICHES):]
    return {"pays": "country", "region": "region", "prefecture": "prefecture", "site": "site"}.get(stem.split("_")[0], "")


def _name(title: str) -> str:
    # « Fiche climatique AGBÉA : préfecture Agoè-Nyivé » → « Agoè-Nyivé »
    tail = title.split(":", 1)[-1].strip()
    return re.sub(r"^(préfecture|site pilote|région)\s+", "", tail, flags=re.I)


@lru_cache(maxsize=1)
def _load() -> tuple[list[Zone], dict[tuple[str, ...], Zone]]:
    path = Path(settings.data_dir, "corpus", "sources.json")
    try:
        entries = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [], {}
    zones, keys = [], {}
    for e in entries:
        if not e["file"].startswith(FICHES):
            continue
        lvl = _level(e["file"])
        regions = e.get("region_ids") or []
        z = Zone(e["file"], e["title"], _name(e["title"]), lvl, regions[0] if len(regions) == 1 else None)
        zones.append(z)
        words = tuple(question.normalize(z.name).replace("-", " ").replace("&", " ").split())
        if lvl == "prefecture":
            keys[words] = z
        elif lvl == "site":
            for w in words:
                if w not in _SITE_SKIP and len(w) > 2:
                    keys.setdefault((w,), z)
    return zones, keys


def by_file(file: str) -> Optional[Zone]:
    return next((z for z in _load()[0] if z.file == file), None)


def region_fiche(region_id: str) -> Optional[Zone]:
    return by_file(f"{FICHES}region_{region_id}.md")


def find(text: str) -> Optional[Zone]:
    """Première zone (site ou préfecture) citée dans la phrase, ou None."""
    _, keys = _load()
    if not keys:
        return None
    toks = question._tokens(text)       # (mot normalisé, mot original, début de phrase)
    norm = [t[0] for t in toks]
    found: list[tuple[int, int, int, Zone]] = []   # (position, priorité, -longueur, zone) ; priorité 0 = site
    for key, z in keys.items():
        n = len(key)
        for i in range(len(norm) - n + 1):
            if tuple(norm[i:i + n]) != key:
                continue
            if n == 1 and key[0] in _NEEDS_CONTEXT:
                before = set(norm[max(0, i - 3):i])
                orig, start = toks[i][1], toks[i][2]
                if not (before & question.PLACE_CONTEXT or (orig[:1].isupper() and not start)):
                    continue
            if set(norm[max(0, i - 3):i]) & question.NEGATIONS:
                continue
            found.append((i, 0 if z.level == "site" else 1, -n, z))
    if not found:
        return None
    return sorted(found, key=lambda x: (x[0], x[1], x[2]))[0][3]
