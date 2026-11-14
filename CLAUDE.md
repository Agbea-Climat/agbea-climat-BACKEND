# AGBÉA CLIMAT — Backend : règles pour les agents

Plateforme qui transforme des données satellites NASA (pluie, végétation, température du sol, altitude)
en informations compréhensibles pour les 5 régions du Togo. Deux modes (public / scientifique),
4 profils d'utilisateurs, un assistant IA (RAG) qui cite toujours ses sources.

## Stack

- Python 3.11+, FastAPI, Pydantic v2, pydantic-settings
- Données : pandas + pyarrow (Parquet), shapely (point dans polygone)
- Sessions : SQLite (`sqlite3` standard ou SQLModel)
- IA : LangGraph, Chroma (vector store local), LLM configurable par variables d'environnement
- Tests : pytest + `fastapi.testclient`

## Commandes

```bash
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000 # API + /docs
pytest                                        # tous les tests
pytest -m m14                                 # tests d'une mission
pytest -m "not llm"                           # sans les tests qui appellent le LLM
```

## Architecture (mission P1 faite)

```text
backend/
  main.py                 # crée l'app, CORS, handlers d'erreur, inclut les routers
  core/
    config.py             # Settings (pydantic-settings, lit .env)
    constants.py          # API_PREFIX, APP_VERSION, DISCLAIMER
    exceptions/           # ApiError / NotFound / BadRequest + handlers → {"error": {code, message, details?}}
    database/             # connexion SQLite (sqlite3)
  schemas/                # TOUS les modèles Pydantic (miroir de contract/types.ts), un fichier par domaine
    common.py  geo.py  catalog.py  observations.py  views.py  ai.py  sessions.py  meta.py
  api/                    # une route = une fonction, aucune logique métier ici
    router.py             # assemble les routers sous /api/v1
    meta.py  profiles.py  sessions.py  regions.py  catalog.py
    observations.py  views.py  ai.py  admin.py  voice.py
  services/               # logique métier, testable sans HTTP (lève backend.core.exceptions)
    regions.py            # GeoJSON, point dans polygone
    indicators.py         # séries, normales, anomalies, comparaisons, dashboard, agriculture
    sessions.py           # sessions anonymes, préférences
    catalog.py            # datasets, indicateurs, couches, profils, méta (données statiques)
  repositories/           # accès aux données, aucune logique métier
    store.py              # charge data/processed/*.parquet en mémoire au démarrage
    sessions.py           # tables SQLite sessions / threads
chatbot/                  # assistant IA (LangGraph + RAG)
  graph.py                # graphe (route → fetch_data → retrieve → generate)
  nodes/                  # nœuds du graphe
  prompts/                # prompts par profil / mode / langue
  llm/                    # client LLM selon LLM_PROVIDER
  memory/                 # checkpointer SQLite par thread_id
  tools/                  # accès données (backend.services) et recherche Chroma
  channels/               # sortie : SSE (sse.py), voix plus tard
worker/
  rag_ingest.py           # ingestion du corpus, découpage, Chroma
evals/                    # évaluations de l'assistant
prisma/                   # réservé
contract/types.ts         # types du front
data/
  regions.geojson         # contours ADM1 (geoBoundaries TGO)
  processed/monthly.parquet   # region_id, indicator, date (YYYY-MM), value
  processed/static.json       # altitude par région
  corpus/                 # documents du RAG (md, pdf)
scripts/export_gee.py     # export Google Earth Engine → monthly.parquet
tests/                    # un fichier par bloc, un marker par mission
```

## Règles non négociables

1. **Le contrat est la loi.** Une réponse doit correspondre exactement à `backend/schemas/`.
   Si tu modifies un schéma, modifie `contract/types.ts` dans le même commit.
2. **Base des routes : `/api/v1`.** Ne change jamais un chemin existant.
3. **Erreurs** : toujours `{"error": {"code": "...", "message": "..."}}`. Codes en snake_case
   (`region_not_found`, `dataset_not_found`, `session_not_found`, `layer_not_found`,
   `outside_togo`, `no_timeseries`, `invalid_period`, `validation_error`, `in_development`).
4. **Coordonnées en `[lon, lat]`** partout (GeoJSON). Dates des séries : `YYYY-MM`.
   Dates des couches de carte : `YYYY-MM-DD`.
5. **Aucun chiffre inventé.** Chaque valeur renvoyée vient de `data/processed/` et porte son
   `dataset_id`. L'IA ne cite que des chiffres renvoyés par les services (nœud `fetch_data`).
6. **Observé / interprété / prédit** : chaque `Statement` a une `nature`. Une phrase `predicted`
   sans source est interdite.
7. **Avertissement** : `/explain`, `/agriculture` et le chat renvoient toujours le texte
   « AGBÉA CLIMAT aide à comprendre l'environnement. Il ne remplace pas les prévisions
   officielles ni les systèmes d'alerte. » (constante `DISCLAIMER`).
8. **Pas de secret dans le code.** Clés API dans `.env` (voir `.env.example`).

## Comment traiter une mission

1. Lis la section de la mission dans `MISSIONS.md` (fichiers, implémentation, données).
2. Lance `pytest -m mXX` pour voir ce qui échoue.
3. Implémente dans `backend/services/` (données via `backend/repositories/`) puis branche
   dans `backend/api/`. Les erreurs métier se lèvent avec `backend.core.exceptions`.
4. Relance `pytest -m mXX` jusqu'à ce que tout passe, puis `pytest -m "not llm"` pour vérifier
   que tu n'as rien cassé ailleurs.
5. Ne modifie pas les tests pour les faire passer. Si un test te semble faux, arrête-toi et
   explique pourquoi dans ta réponse.
6. Commit : `feat(M14): résumé régional sur données réelles`.
7. Dans ta réponse finale, donne : les fichiers modifiés, la sortie de `pytest -m mXX`,
   et un exemple `curl` pour le testeur humain.

## Ce qu'il ne faut pas faire

- Ajouter une route qui n'est pas dans `MISSIONS.md`.
- Mettre de la logique dans `backend/api/`.
- Appeler une API externe (NASA, GEE) pendant une requête : tout est pré-calculé dans `data/`.
- Renvoyer des données aléatoires une fois la mission sur données réelles faite.
