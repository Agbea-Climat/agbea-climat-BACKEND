import json
import os
import re
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

API = "/api/v1"
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / os.getenv("DATA_DIR", "data")
REGION_IDS = {"maritime", "plateaux", "centrale", "kara", "savanes"}
NATURES = {"observed", "interpreted", "predicted"}
# Emprise large du Togo [lon, lat]
TOGO_LON = (-0.3, 1.95)
TOGO_LAT = (6.0, 11.2)


def pytest_collection_modifyitems(config, items):
    has_key = bool(os.getenv("LLM_API_KEY"))
    has_data = (DATA / "processed" / "monthly.parquet").exists()
    for item in items:
        if "llm" in item.keywords and not has_key:
            item.add_marker(pytest.mark.skip(reason="LLM_API_KEY absent"))
        if "real_data" in item.keywords and not has_data:
            item.add_marker(pytest.mark.skip(reason="data/processed/monthly.parquet absent (P2)"))


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def session_id(client):
    r = client.post(f"{API}/sessions")
    assert r.status_code == 201
    return r.json()["session_id"]


def err_code(r):
    body = r.json()
    assert "error" in body, f"format d'erreur attendu {{'error': ...}}, reçu {body}"
    return body["error"]["code"]


def is_uuid(s):
    try:
        uuid.UUID(s)
        return True
    except (ValueError, TypeError):
        return False


def months(start, end):
    y, m = map(int, start.split("-"))
    ye, me = map(int, end.split("-"))
    out = []
    while (y, m) <= (ye, me):
        out.append(f"{y}-{m:02d}")
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return out


def sse_events(text):
    return [json.loads(line[5:].strip()) for line in text.splitlines() if line.startswith("data:")]


ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
