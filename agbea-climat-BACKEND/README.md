# AGBÉA CLIMAT — Backend

API FastAPI de la plateforme AGBÉA CLIMAT (NASA Space Apps Challenge 2026).
Contrat API v0.4 — les routes renvoient pour l'instant des données mock.

## Lancer

```bash
python -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Documentation interactive : http://localhost:8000/docs

## Structure

- `app/main.py` — routes `/api/v1/...` (mock, à remplacer mission par mission)
- `app/schemas.py` — schémas Pydantic
- `contract/types.ts` — types TypeScript pour le front (miroir de `schemas.py`)
- `CLAUDE.md` — règles du projet pour les agents IA
- `docs/MISSIONS.md` — fiche technique, mission par mission
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

## Règle

`contract/types.ts` et `app/schemas.py` changent toujours ensemble, dans le même commit.
