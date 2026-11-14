# AGBÉA CLIMAT — Backend

API FastAPI de la plateforme AGBÉA CLIMAT (NASA Space Apps Challenge 2026).
Contrat API v0.4 — les routes renvoient pour l'instant des données mock.

## Lancer

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

- `backend/` — API : `api/` (routes `/api/v1/...`), `services/` (logique métier),
  `repositories/` (accès données), `schemas/` (Pydantic), `core/` (config, erreurs, base PostgreSQL + migrations Alembic)
- `chatbot/` — assistant IA (LangGraph + RAG)
- `worker/` — ingestion du corpus RAG
- `contract/types.ts` — types TypeScript pour le front (miroir de `backend/schemas/`)
- `CLAUDE.md` — règles du projet pour les agents IA
- `MISSIONS.md` — fiche technique, mission par mission
- `docs/AGBEA_CLIMAT_missions_*.pdf` — tests humains API + front (FR / EN)
- `tests/` — tests automatiques ; une mission est finie quand `pytest -m mXX` passe

## Tests

```bash
pytest                    # tout
pytest -m m14             # une mission
pytest -m "not llm"       # sans appel au LLM
```

Les tests `real_data` sont ignorés tant que `data/processed/monthly.parquet` n'existe pas (P2),
les tests `llm` tant que `LLM_API_KEY` n'est pas défini.

## Format des réponses

Toute réponse JSON : `{"status": "success" | "error", "message": "...", "response": ...}`
(voir `backend/schemas/envelope.py`). En cas d'erreur, `response.code` donne le code (`region_not_found`, ...).
Exceptions : flux SSE `/chat/stream` et fichiers `/timeseries/export`.

## Règle

`contract/types.ts` et `backend/schemas/` changent toujours ensemble, dans le même commit.
