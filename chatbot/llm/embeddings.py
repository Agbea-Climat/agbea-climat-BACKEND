"""Vectorisation des textes pour pgvector (M22–M25).

EMBEDDING_MODEL :
- vide ou `hash-v1` (défaut) : embedder local et déterministe (hachage des mots et bigrammes,
  normalisé L2). Aucun appel réseau, aucune clé : l'ingestion et la recherche marchent partout.
  C'est une recherche lexicale (mots communs), pas sémantique.
- autre valeur : non encore branché (Anthropic n'a pas d'API d'embeddings ; un fournisseur dédié
  pourra être ajouté ici). Changer de modèle ou de EMBEDDING_DIM impose une migration + réingestion.
"""
import hashlib
import math
import re
import unicodedata

from backend.core.config import settings

HASH_MODEL = "hash-v1"
_WORD = re.compile(r"[a-z0-9]+")
# Mots trop fréquents en français pour aider la recherche
_STOP = set("""a au aux avec ce ces dans de des du elle en est et il ils la le les leur mais
ne ni on ou par pas pour qu que qui sa se ses son sont sur un une vos votre nous vous d l s c n
y the of and to in is""".split())


def model_name() -> str:
    return settings.embedding_model or HASH_MODEL


def _tokens(text: str) -> list[str]:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    words = [w for w in _WORD.findall(text) if w not in _STOP and len(w) > 1]
    return words + [f"{a}_{b}" for a, b in zip(words, words[1:])]


def _hash_embed(text: str, dim: int) -> list[float]:
    vec = [0.0] * dim
    for tok in _tokens(text):
        h = hashlib.blake2b(tok.encode(), digest_size=8).digest()
        idx = int.from_bytes(h[:4], "little") % dim
        vec[idx] += 1.0 if h[4] & 1 else -1.0
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0:
        vec[0] = 1.0  # texte vide : vecteur unitaire arbitraire (pgvector refuse la norme nulle en cosinus)
        return vec
    return [v / norm for v in vec]


def embed(texts: list[str]) -> list[list[float]]:
    name = model_name()
    if name != HASH_MODEL:
        raise NotImplementedError(f"EMBEDDING_MODEL={name} non pris en charge (valeurs possibles : vide, {HASH_MODEL})")
    return [_hash_embed(t, settings.embedding_dim) for t in texts]


def embed_one(text: str) -> list[float]:
    return embed([text])[0]
