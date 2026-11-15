# AGBÉA CLIMAT — commandes du backend.  `make` ou `make help` pour la liste.

VENV ?= .venv
# Utilise le venv s'il existe, sinon le python3 du système
PY := $(if $(wildcard $(VENV)/bin/python),$(VENV)/bin/python,python3)
PORT ?= 8000
COMPOSE := docker compose

.DEFAULT_GOAL := help
.PHONY: help venv install env setup run db-up db-down db-logs db-psql db-reset \
        migrate migration downgrade db-check test test-fast test-m test-db clean

help: ## Affiche cette aide
	@grep -hE '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*## "} {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

# ── Installation ──
venv: ## Crée le venv .venv
	python3 -m venv $(VENV)

install: ## Installe les dépendances (requirements.txt)
	$(PY) -m pip install -r requirements.txt

env: ## Crée .env depuis .env.example (n'écrase pas un .env existant)
	@test -f .env && echo ".env existe déjà" || (cp .env.example .env && echo ".env créé")

setup: env install db-up migrate ## Tout installer : .env, dépendances, base, migrations

# ── API ──
run: ## Lance l'API en mode dev (PORT=8000)
	$(PY) -m uvicorn backend.main:app --reload --port $(PORT)

# ── Base PostgreSQL + pgvector ──
db-up: ## Démarre la base (docker compose)
	$(COMPOSE) up -d db --wait

db-down: ## Arrête la base (garde les données)
	$(COMPOSE) down

db-logs: ## Affiche les logs de la base
	$(COMPOSE) logs -f db

db-psql: ## Ouvre psql dans le conteneur
	$(COMPOSE) exec db sh -c 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"'

db-reset: ## SUPPRIME toutes les données puis recrée la base et les migrations
	@read -p "Supprimer toutes les données de la base locale ? [y/N] " ok && [ "$$ok" = "y" ]
	$(COMPOSE) down -v
	$(MAKE) db-up migrate

# ── Migrations Alembic ──
migrate: ## Applique les migrations (alembic upgrade head)
	$(PY) -m alembic upgrade head

migration: ## Crée une migration : make migration m="message"
	@test -n "$(m)" || (echo 'Usage : make migration m="message"' && exit 1)
	$(PY) -m alembic revision --autogenerate -m "$(m)"

downgrade: ## Annule la dernière migration
	$(PY) -m alembic downgrade -1

db-check: ## Vérifie que models.py et la base sont synchronisés
	$(PY) -m alembic check

# ── Tests ──
test: ## Lance tous les tests
	$(PY) -m pytest

test-fast: ## Tests sans appel au LLM
	$(PY) -m pytest -m "not llm"

test-m: ## Tests d'une mission : make test-m M=m14
	@test -n "$(M)" || (echo 'Usage : make test-m M=m14' && exit 1)
	$(PY) -m pytest -m $(M)

test-db: ## Tests de la base (exige db-up)
	$(PY) -m pytest -m db

# ── Nettoyage ──
clean: ## Supprime les caches Python et pytest
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
	rm -rf .pytest_cache
