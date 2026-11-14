"""Ingestion du corpus RAG.

TODO M22/M23 : lire data/corpus/ + sources.json, découper (~600 tokens, chevauchement 80),
vectoriser, upsert dans la table `rag_chunks` (pgvector ; id = sha1(file + index)).
"""


def ingest() -> dict:
    return {"ingested": 0}


def list_documents() -> dict:
    return {"documents": []}
