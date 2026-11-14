"""Ingestion du corpus RAG.

TODO M22/M23 : lire data/corpus/ + sources.json, découper (~600 tokens, chevauchement 80),
vectoriser, upsert dans la collection Chroma `agbea_corpus` (id = sha1(file + index)).
"""


def ingest() -> dict:
    return {"ingested": 0}


def list_documents() -> dict:
    return {"documents": []}
