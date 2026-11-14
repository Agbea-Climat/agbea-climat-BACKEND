# syntax=docker/dockerfile:1.7
# API AGBÉA CLIMAT (FastAPI) : backend/ + chatbot/ + worker/
# Les données sont montées depuis ./data (livrable P2 du pipeline), pas copiées dans l'image.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements/api.txt requirements/api.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --timeout 120 --retries 10 -r requirements/api.txt

COPY pytest.ini ./
COPY backend ./backend
COPY chatbot ./chatbot
COPY worker ./worker
COPY contract ./contract
COPY tests ./tests

# /app/var : SQLite (sessions) et Chroma (RAG), persistés dans un volume nommé
RUN useradd --create-home --uid 1000 agbea \
    && mkdir -p /app/var /app/data \
    && chown -R agbea:agbea /app/var /app/data
USER agbea
ENV DB_PATH=/app/var/agbea.sqlite \
    CHROMA_DIR=/app/var/.chroma \
    DATA_DIR=data

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
