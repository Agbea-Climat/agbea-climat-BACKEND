# syntax=docker/dockerfile:1.7
# Pipeline de données AGBÉA CLIMAT (pipeline/) : NASA IMERG, MODIS, NASADEM, POWER → data/
# Les wheels rasterio / geopandas / h5py / pyhdf embarquent GDAL, PROJ, HDF5 et HDF4.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# libexpat : requise par le GDAL embarqué dans les wheels rasterio, absente de l'image slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends libexpat1 \
    && rm -rf /var/lib/apt/lists/*

# versions exactes testées (pip freeze du venv de dev)
COPY requirements/pipeline.lock requirements/pipeline.lock
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --timeout 120 --retries 10 -r requirements/pipeline.lock

COPY pytest.ini ./
COPY pipeline ./pipeline
# limites administratives versionnées : seule donnée d'entrée embarquée (le reste est monté depuis ./data)
COPY data/reference ./data/reference

RUN useradd --create-home --uid 1000 agbea \
    && mkdir -p /app/data/raw /app/data/interim /app/data/api /app/data/processed \
    && chown -R agbea:agbea /app/data
USER agbea

LABEL org.opencontainers.image.title="agbea-pipeline" \
      org.opencontainers.image.description="AGBÉA CLIMAT — pipeline de données NASA pour le Togo (prérequis P2 du backend)"

ENTRYPOINT ["python", "-m", "pipeline"]
CMD ["--help"]
