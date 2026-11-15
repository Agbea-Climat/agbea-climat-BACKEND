"""Recherche dans le corpus RAG (table rag_chunks, pgvector, distance cosinus) et extraction de passages.

- `search` : k morceaux les plus proches (filtres indicateur / région / fichiers) ;
- `dedupe` : un seul morceau (donc une seule source) par document ;
- `passages` : lignes, puces ou rangées de tableau d'un morceau qui répondent à la question
  (citées telles quelles, avec l'en-tête du tableau), pour répondre sans LLM à partir du document.
"""
import re
import unicodedata
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import literal, or_, select

from backend.core.database import SessionLocal
from backend.core.database.models import RagChunk
from chatbot.llm import embeddings

CALENDAR_FILE = "calendrier_agricole_togo.md"
LIMITS_FILE = "limites_donnees_agbea.md"
# Fiche ou explication de référence par indicateur (cité par /explain)
INDICATOR_DOCS = {
    "precipitation": ("comprendre_pluie_imerg.md", "fiche_gpm_imerg.md"),
    "ndvi": ("comprendre_ndvi.md", "fiche_modis_ndvi.md"),
    "lst_day": ("comprendre_temperature_sol.md", "fiche_modis_lst.md"),
    "elevation": ("fiche_nasadem.md",),
}


@dataclass
class Chunk:
    id: str
    file: str
    title: str
    source_url: str
    content: str
    distance: float

    @property
    def source_id(self) -> str:
        return f"doc:{self.id[:12]}"

    def snippet(self, n: int = 300) -> str:
        text = " ".join(self.content.split())
        return text if len(text) <= n else text[:n].rsplit(" ", 1)[0] + "…"


def search(query: str, k: int = 4, indicator: Optional[str] = None,
           region_id: Optional[str] = None, files: Optional[list[str]] = None) -> list[Chunk]:
    """k morceaux les plus proches. Filtres : documents de l'indicateur / la région (ou généraux), fichiers."""
    vec = embeddings.embed_one(query)
    dist = RagChunk.embedding.cosine_distance(vec).label("distance")
    q = select(RagChunk.id, RagChunk.file, RagChunk.title, RagChunk.source_url, RagChunk.content, dist)
    if indicator:
        q = q.where(or_(RagChunk.indicators.overlap([indicator]), RagChunk.indicators == literal([], RagChunk.indicators.type)))
    if region_id:
        q = q.where(or_(RagChunk.region_ids.overlap([region_id]), RagChunk.region_ids == literal([], RagChunk.region_ids.type)))
    if files:
        q = q.where(RagChunk.file.in_(files))
    try:
        with SessionLocal() as db:
            rows = db.execute(q.order_by(dist).limit(k)).all()
    except Exception:  # base indisponible : l'assistant répond sans documents
        return []
    return [Chunk(*r) for r in rows]


def dedupe(chunks: list[Chunk]) -> list[Chunk]:
    """Un morceau par document (le plus proche) : une seule source par document."""
    seen, out = set(), []
    for c in chunks:
        if c.file not in seen:
            seen.add(c.file)
            out.append(c)
    return out


# ─────────── Passages ───────────
_STOP = embeddings._STOP | set("""quand comment quel quelle quels quelles est faut il ils elle on je tu peut peux
dois doit bien plus moins tres when how what which should could would can do does did i we my our is are was
were be it this that for from with at on region regions togo""".split())
SYNONYMS = {"semer": "semis", "seme": "semis", "semez": "semis", "planter": "semis", "plante": "semis",
            "sow": "semis", "sowing": "semis", "plant": "semis", "planting": "semis", "recolter": "recolte",
            "recoltes": "recolte", "harvest": "recolte", "harvesting": "recolte", "maize": "mais", "corn": "mais",
            "millet": "mil", "sorghum": "sorgho", "rice": "riz", "yam": "igname", "yams": "igname",
            "cassava": "manioc", "rain": "pluie", "rains": "pluie", "rainy": "pluies", "season": "saison",
            "seasons": "saisons"}
STRONG = {"mais", "mil", "sorgho", "riz", "igname", "manioc", "maritime", "plateaux", "centrale", "kara", "savanes"}
# Zone climatique de chaque région (pour retrouver « sud », « nord » dans les documents)
REGION_ZONE = {"maritime": "sud", "plateaux": "sud", "centrale": "centre", "kara": "nord", "savanes": "nord"}


def _norm_words(text: str) -> list[str]:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.findall(r"[a-z0-9]+", text)


def keywords(question: str, region_id: Optional[str] = None) -> dict[str, int]:
    """Mots-clés pondérés de la question : culture et région comptent triple."""
    kws: dict[str, int] = {}
    for w in _norm_words(question):
        w = SYNONYMS.get(w, w)
        if w not in STRONG and (w in _STOP or len(w) < 3 or w.isdigit()):
            continue
        kws[w] = 3 if w in STRONG else 1
    if region_id:
        kws[region_id] = 3
        kws.setdefault(REGION_ZONE[region_id], 1)
    return kws


def _clean(text: str) -> str:
    return " ".join(text.replace("**", "").split())


def _units(content: str) -> list[str]:
    """Découpe un morceau en unités citables : paragraphe, puce, ou rangée de tableau avec son en-tête."""
    out: list[str] = []
    header: Optional[list[str]] = None
    current: list[str] = []
    in_table = False

    def flush():
        if current:
            out.append(_clean(" ".join(current)))
            current.clear()

    lines = [ln.strip() for ln in content.split("\n")]
    # Morceau commencé au milieu d'une phrase ou d'une rangée (fenêtre de mots) : on ignore ce début
    if lines and lines[0] and not re.match(r"^([#|*-]|\d+\.|[A-ZÀ-Ý«])", lines[0]):
        lines = lines[1:]
    sep = re.compile(r"^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?$")
    for i, line in enumerate(lines):
        if not line or line.startswith("#"):
            flush()
            in_table, header = False, None
            continue
        if line.startswith("|"):
            flush()
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                continue  # ligne de séparation |---|
            if not in_table:
                in_table = True
                nxt = lines[i + 1] if i + 1 < len(lines) else ""
                if sep.match(nxt):   # vrai en-tête : suivi de |---|
                    header = cells
                    continue
                header = None
            if header and len(header) == len(cells):
                out.append(_clean(" ; ".join(f"{h} : {c}" for h, c in zip(header, cells))))
            # rangée sans son en-tête (morceau coupé dans le tableau) : sens perdu, non citée
            continue
        in_table, header = False, None
        if re.match(r"^([-*]|\d+\.)\s", line):
            flush()
            line = re.sub(r"^([-*]|\d+\.)\s+", "", line)
        current.append(line)
    flush()
    return [u for u in out if len(u) > 20]


def _score(unit: str, kws: dict[str, int]) -> int:
    ws = set(_norm_words(unit))
    return sum(weight for k, weight in kws.items() if any(w == k or (len(k) >= 4 and w.startswith(k)) for w in ws))


def passages(chunks: list[Chunk], question: str, region_id: Optional[str] = None,
             max_n: int = 5) -> list[tuple[Chunk, str]]:
    """Passages les plus pertinents (score > 0), dans l'ordre du document, sans doublon."""
    kws = keywords(question, region_id)
    scored, seen = [], set()
    for ci, c in enumerate(chunks):
        for ui, u in enumerate(_units(c.content)):
            if u in seen:
                continue
            seen.add(u)
            s = _score(u, kws)
            if s > 0:
                scored.append((s, ci, ui, c, u))
    best = sorted(scored, key=lambda x: (-x[0], x[1], x[2]))[:max_n]
    return [(c, u) for _, _, _, c, u in sorted(best, key=lambda x: (x[1], x[2]))]
