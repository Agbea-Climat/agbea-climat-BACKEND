"""Client LLM (M24–M26), choisi par LLM_PROVIDER / LLM_MODEL / LLM_API_KEY.

Sans clé (ou fournisseur non pris en charge), `available()` est faux et l'assistant répond par
gabarits à partir des seules données calculées : il reste utilisable et ne cite jamais de chiffre
inventé. Fournisseur pris en charge : anthropic (SDK officiel).

Repli serveur activé (`fallbacks="default"`, beta server-side-fallback-2026-07-01) : si le modèle
décline une requête, l'API la relance sur un modèle de repli dans le même appel.
"""
import logging
from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Optional, TypeVar

from pydantic import BaseModel

from backend.core.config import settings

log = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-opus-5-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
T = TypeVar("T", bound=BaseModel)


class LLMUnavailable(RuntimeError):
    """Le LLM n'a pas pu répondre (pas de clé, refus, erreur réseau) : l'appelant passe aux gabarits."""


def available() -> bool:
    return settings.llm_provider == "anthropic" and bool(settings.llm_api_key)


def model() -> str:
    return settings.llm_model or DEFAULT_MODEL


@lru_cache
def _client():
    import anthropic
    return anthropic.AsyncAnthropic(api_key=settings.llm_api_key, timeout=60.0, max_retries=2)


def _check(response) -> None:
    if response.stop_reason == "refusal":
        raise LLMUnavailable("refus du modèle")


async def structured(system: str, user: str, schema: type[T], effort: str = "medium",
                     max_tokens: int = 4000) -> T:
    """Réponse validée par un modèle Pydantic (sortie structurée)."""
    if not available():
        raise LLMUnavailable("LLM non configuré")
    import anthropic
    try:
        response = await _client().beta.messages.parse(
            model=model(), max_tokens=max_tokens, betas=[FALLBACK_BETA], fallbacks="default",
            system=system, messages=[{"role": "user", "content": user}],
            output_config={"effort": effort}, output_format=schema)
    except anthropic.APIError as e:
        log.warning("LLM structured: %s", e)
        raise LLMUnavailable(str(e)) from e
    _check(response)
    if response.parsed_output is None:
        raise LLMUnavailable("sortie structurée vide")
    return response.parsed_output


async def stream_text(system: str, messages: list[dict], effort: str = "medium",
                      max_tokens: int = 2000) -> AsyncIterator[str]:
    """Texte de la réponse, morceau par morceau."""
    if not available():
        raise LLMUnavailable("LLM non configuré")
    import anthropic
    try:
        async with _client().beta.messages.stream(
                model=model(), max_tokens=max_tokens, betas=[FALLBACK_BETA], fallbacks="default",
                system=system, messages=messages, output_config={"effort": effort}) as stream:
            async for text in stream.text_stream:
                yield text
            final = await stream.get_final_message()
    except anthropic.APIError as e:
        log.warning("LLM stream: %s", e)
        raise LLMUnavailable(str(e)) from e
    _check(final)


async def text(system: str, messages: list[dict], effort: str = "medium", max_tokens: int = 2000) -> str:
    return "".join([t async for t in stream_text(system, messages, effort, max_tokens)])


def first_text(content: Optional[list]) -> str:
    return next((b.text for b in content or [] if getattr(b, "type", None) == "text"), "")
