# syntax=docker/dockerfile:1.7
# Notebooks d'exploration des données traitées (tests/notebooks/), servis par JupyterLab.
# Lecture seule : data/ est monté depuis l'hôte, rien n'est recalculé ici.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# libexpat : requise par le GDAL embarqué dans la wheel rasterio, absente de l'image slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends libexpat1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/notebooks.txt requirements/notebooks.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --timeout 120 --retries 10 -r requirements/notebooks.txt

RUN useradd --create-home --uid 1000 agbea && mkdir -p /app/tests/notebooks && chown -R agbea:agbea /app
USER agbea
WORKDIR /app/tests/notebooks

LABEL org.opencontainers.image.title="agbea-notebooks" \
      org.opencontainers.image.description="AGBÉA CLIMAT — notebooks d'exploration des données traitées"

EXPOSE 8888
# Jeton vide : le port n'est publié que sur 127.0.0.1 (voir docker-compose.yml)
CMD ["jupyter", "lab", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--ServerApp.token=", "--ServerApp.password="]
