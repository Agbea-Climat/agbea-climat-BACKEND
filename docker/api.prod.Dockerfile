# syntax=docker/dockerfile:1.7
# API AGBÉA CLIMAT — image de PRODUCTION (Dokploy, mode Raw).
# Contrairement à docker/api.Dockerfile (dev, données montées depuis ./data), cette image
# EMBARQUE les données de l'API (livrable P2) : elle tourne sans aucun fichier sur le serveur.
#
#   docker build -f docker/api.prod.Dockerfile -t ghcr.io/agbea-climat/agbea-api:latest .
#   docker push ghcr.io/agbea-climat/agbea-api:latest
#
# Fichiers exclus du build : docker/api.prod.Dockerfile.dockerignore (prioritaire sur .dockerignore).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements/api.txt requirements/api.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --timeout 120 --retries 10 -r requirements/api.txt

COPY alembic.ini ./
COPY backend ./backend
COPY chatbot ./chatbot
COPY worker ./worker

# Données lues par l'API (régénérer avec le pipeline puis reconstruire l'image).
# Ajouter ici data/corpus/ quand le corpus RAG (P3) existera.
COPY data/regions.geojson ./data/regions.geojson
COPY data/processed ./data/processed

RUN useradd --create-home --uid 1000 agbea \
    && chown -R agbea:agbea /app
USER agbea
ENV DATA_DIR=data

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=2)"
# Applique les migrations puis lance l'API
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn backend.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
