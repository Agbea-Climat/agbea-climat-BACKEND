# AGBÉA CLIMAT — Backend

API FastAPI de la plateforme AGBÉA CLIMAT (NASA Space Apps Challenge 2026).
Contrat API v0.4 — les routes renvoient pour l'instant des données mock.

## Lancer avec Docker (recommandé)

```bash
cp .env.example .env              # LLM_API_KEY, EARTHDATA_TOKEN…
docker compose build
docker compose up -d              # API → http://localhost:8000/docs
docker compose run --rm pipeline export-backend   # (re)génère les données lues par l'API
```

Tous les services (pipeline, tests, explorateur de données) : [docs/docker.md](docs/docker.md).

## Lancer sans Docker

```bash
python -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
docker compose up -d db          # PostgreSQL 17 + pgvector sur le port 5433
alembic upgrade head
uvicorn backend.main:app --reload --port 8000
```

Documentation interactive : http://localhost:8000/docs

## Structure

- `pipeline/` — **pipeline de données NASA** (prérequis P2) → `data/` ; voir [pipeline/README.md](pipeline/README.md)
- `data/` — `reference/` (limites), `regions.geojson` + `processed/` (lus par l'API), `api/` (livrable complet, non versionné)
- `docker/`, `docker-compose.yml` — images `agbea-api` et `agbea-pipeline`, services de test
- `requirements/` — `api.txt`, `pipeline.txt`, `pipeline.lock` (`requirements.txt` = les deux)
- `backend/` — API : `api/` (routes `/api/v1/...`), `services/` (logique métier),
  `repositories/` (accès données), `schemas/` (Pydantic), `core/` (config, erreurs, base PostgreSQL + migrations Alembic)
- `chatbot/` — assistant IA (LangGraph + RAG)
- `worker/` — ingestion du corpus RAG
- `contract/types.ts` — types TypeScript pour le front (miroir de `backend/schemas/`)
- `CLAUDE.md` — règles locales pour les agents IA (non versionné, voir `.gitignore`) ; `pipeline/CLAUDE.md` pour le pipeline
- `MISSIONS.md` — fiche technique, mission par mission
- `docs/AGBEA_CLIMAT_missions_*.pdf` — tests humains API + front (FR / EN)
- `tests/` — tests automatiques ; une mission est finie quand `pytest -m mXX` passe
- `tests/front/` — explorateur web des données (front de test, pas le front de l'application)
- `docs/data/` — contrat de données, méthodologie, accès aux sources NASA
- `notes/`, `changelogs/` — analyses, décisions, historique

## Tests

```bash
pytest                    # tout
pytest -m m14             # une mission
pytest -m "not llm"       # sans appel au LLM
pytest pipeline/tests     # tests du pipeline de données
```

Avec Docker : `docker compose --profile test run --rm api-tests` et `... run --rm pipeline-tests`.

Le fichier `data/processed/monthly.parquet` (P2) est fourni par le pipeline : les tests `real_data`
sont donc actifs et passent au vert au fur et à mesure des missions M07, M09, M14–M16 ;
les tests `llm` tant que `LLM_API_KEY` n'est pas défini.

## Format des réponses

Toute réponse JSON : `{"status": "success" | "error", "message": "...", "response": ...}`
(voir `backend/schemas/envelope.py`). En cas d'erreur, `response.code` donne le code (`region_not_found`, ...).
Exceptions : flux SSE `/chat/stream` et fichiers `/timeseries/export`.

## Règle

`contract/types.ts` et `backend/schemas/` changent toujours ensemble, dans le même commit.
