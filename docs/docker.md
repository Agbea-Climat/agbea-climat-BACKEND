# Docker

Trois images et un seul `docker-compose.yml` à la racine. Les données vivent sur l'hôte, dans `./data`, montées dans les conteneurs : **le pipeline écrit, l'API lit**.

| Service | Image | Rôle | Lancement |
|---|---|---|---|
| `db` | `pgvector/pgvector:pg17` | PostgreSQL + pgvector : sessions, threads, corpus RAG (volume `pgdata`) | `docker compose up -d db` → port 5433 sur l'hôte |
| `api` | `agbea-api` (`docker/api.Dockerfile`) | FastAPI : `backend/`, `chatbot/`, `worker/`. Applique les migrations Alembic au démarrage, joint la base sur `db:5432` | `docker compose up -d` → <http://localhost:8000/docs> |
| `pipeline` (profil `pipeline`) | `agbea-pipeline` (`docker/pipeline.Dockerfile`) | `python -m pipeline <étape>` | `docker compose run --rm pipeline <étape>` |
| `api-tests` (profil `test`) | `agbea-api` | `pytest` de l'API (`tests/` monté en lecture seule) | `docker compose --profile test run --rm api-tests` |
| `pipeline-tests` (profil `test`) | `agbea-pipeline` | `pytest pipeline/tests` | `docker compose --profile test run --rm pipeline-tests` |
| `notebooks` (profil `notebooks`) | `agbea-notebooks` (`docker/notebooks.Dockerfile`) | JupyterLab : notebooks d'exploration de toutes les données (`tests/notebooks`), `data/` en lecture seule, port publié sur 127.0.0.1 seulement | `docker compose --profile notebooks up -d notebooks` → <http://localhost:8888> |
| `data-server` (profil `serve`) | nginx | `data/api/` en HTTP statique, CORS ouvert | `docker compose --profile serve up -d data-server` → <http://localhost:8088> |

`docker compose up -d` ne démarre que l'API et sa base (`db`). Les autres services ne partent qu'à la demande : on cible un service explicitement, ou on passe son profil.

## Commandes courantes

```powershell
docker compose build                                   # images api et pipeline
docker compose --profile notebooks build notebooks     # image des notebooks
docker compose up -d                                   # API
docker compose run --rm pipeline all                   # tout le pipeline (≈ 1 h la première fois)
docker compose run --rm pipeline imerg                 # pluie mensuelle (jeton Earthdata requis)
docker compose run --rm pipeline ndvi --start 2026     # mise à jour de l'année en cours
docker compose run --rm pipeline analyse
docker compose run --rm pipeline export
docker compose run --rm pipeline export-backend        # régénère le livrable P2 lu par l'API
docker compose restart api                             # l'API recharge data/ au démarrage
```

Secrets et paramètres : `.env`, lu par tous les services (`env_file`). Il n'est **jamais copié dans une image**, car `.env` est exclu par `.dockerignore`. Ports : `AGBEA_API_PORT`, `AGBEA_NOTEBOOKS_PORT`, `AGBEA_DATA_PORT`.

## Dépendances

| Fichier | Utilisé par |
|---|---|
| `requirements/api.txt` | image `agbea-api` |
| `requirements/pipeline.lock` | image `agbea-pipeline` (versions exactes testées) |
| `requirements/pipeline.txt` | dépendances directes du pipeline (bornes) |
| `requirements.txt` | environnement de dev complet (`-r` des deux) |

## Problème réseau connu : DNS local et PyPI

Sur le réseau du 14/11/2026, le DNS local (10.15.108.134) ne résolvait pas `files.pythonhosted.org`, d'où l'échec de `pip install` pendant le build. `pypi.org` passait, et un DNS public (1.1.1.1) résolvait correctement. Solutions, de la plus propre à la plus ponctuelle :

1. Corriger le DNS de la machine ou du réseau.
2. Docker Desktop → *Settings → Docker Engine* : ajouter `"dns": ["1.1.1.1", "8.8.8.8"]` (réglage global de Docker).
3. Contournement ponctuel, non versionné :
   ```powershell
   docker build --add-host files.pythonhosted.org:151.101.0.223 -f docker/api.Dockerfile -t agbea-api:0.1.0 .
   docker build --add-host files.pythonhosted.org:151.101.0.223 -f docker/pipeline.Dockerfile -t agbea-pipeline:0.2.0 .
   ```

Les builds utilisent un cache pip BuildKit : un build interrompu reprend sans retélécharger ce qui a déjà été reçu.

## Production : Dokploy (mode « Raw »)

`docker/dokploy.compose.yml` se colle tel quel dans un service *Compose* Dokploy (fournisseur *Raw*). Il ne contient
**aucune variable** : `db` et `api` lisent le fichier `.env` que Dokploy écrit à partir de l'onglet *Environment*.

1. Image : publiée automatiquement par la CI (voir « CI/CD » ci-dessous). À la main, si besoin :
   ```bash
   docker build -f docker/api.prod.Dockerfile -t ghcr.io/agbea-climat/agbea-api:latest .
   docker push ghcr.io/agbea-climat/agbea-api:latest
   ```
   Package GHCR privé : ajouter le registre dans Dokploy (*Settings → Registry*).
2. Onglet *Environment* (toutes obligatoires sauf mention) :
   ```
   POSTGRES_USER=agbea
   POSTGRES_PASSWORD=<mot de passe fort>
   POSTGRES_DB=agbea
   POSTGRES_HOST=db
   POSTGRES_PORT=5432
   DATA_DIR=data
   CORS_ORIGINS=https://agbea-climat.vercel.app
   LLM_PROVIDER=openrouter
   LLM_API_KEY=sk-or-...              # une seule clé OpenRouter : assistant et voix
   LLM_MODEL=                         # facultatif, vide = anthropic/claude-opus-5.5
   VOICE_MODEL=                       # facultatif, modèle OpenRouter acceptant l'audio
   VOICE_LANGUAGES=fr,en
   ```
   `POSTGRES_HOST=db` et `POSTGRES_PORT=5432` : l'API joint la base par le réseau interne du compose.
3. Onglet *Domains* : service `api`, port `8000`. Puis *Deploy*.
4. Après le premier déploiement (et après chaque nouvelle image avec un corpus modifié) :
   `curl -X POST https://<domaine>/api/v1/admin/rag/ingest`.

## CI/CD (`.github/workflows/ci-cd.yml`)

| Job | Quand | Ce qu'il fait |
|---|---|---|
| `test` | PR et push | PostgreSQL 17 + pgvector en service, `alembic upgrade head` + `alembic check`, `pytest -m "not llm"` |
| `image` | après `test` | construit `docker/api.prod.Dockerfile` ; sur `main` / tag `v*` : pousse `ghcr.io/agbea-climat/agbea-api` (`latest`, `sha-<commit>`, `X.Y.Z`) |
| `deploy` | push sur `main`, après `image` | `POST <DOKPLOY_URL>/api/compose.deploy`, attend `/api/v1/health`, relance l'ingestion RAG |

Réglages GitHub (*Settings → Secrets and variables → Actions*), dans l'environnement **`production`** :

- secrets : `DOKPLOY_URL` (URL du panneau Dokploy), `DOKPLOY_API_KEY` (Dokploy → *Settings → Profile → API/CLI*),
  `DOKPLOY_COMPOSE_ID` (identifiant du service compose, visible dans son URL Dokploy) ;
- variable : `API_URL` (domaine public de l'API, sans `/api/v1`).

Sans ces secrets, `deploy` est sauté avec un avertissement : l'image est quand même publiée. Le service `api` du
compose a `pull_policy: always`, donc chaque redéploiement récupère la dernière image `latest`.
