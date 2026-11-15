"""Client LLM (M24–M26), choisi par LLM_PROVIDER / LLM_MODEL / LLM_API_KEY / LLM_BASE_URL.

Fournisseurs :
- `anthropic`  : SDK officiel Anthropic, modèle par défaut claude-opus-5-5, repli serveur
                 `fallbacks="default"` (beta server-side-fallback-2026-07-01) si le modèle décline ;
- `openrouter` : API compatible OpenAI (SDK `openai`, base https://openrouter.ai/api/v1), modèle par
                 défaut anthropic/claude-opus-5.5 ; tout id de https://openrouter.ai/models est accepté.

Sans clé, `available()` est faux et l'assistant répond par gabarits à partir des seules données
calculées : il reste utilisable et ne cite jamais de chiffre inventé.
"""
import json
import logging
import re
from collections.abc import AsyncIterator
from functools import lru_cache
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from backend.core.config import settings

log = logging.getLogger(__name__)

DEFAULT_MODELS = {"anthropic": "claude-opus-5-5", "openrouter": "anthropic/claude-opus-5.5"}
OPENROUTER_URL = "https://openrouter.ai/api/v1"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
T = TypeVar("T", bound=BaseModel)


class LLMUnavailable(RuntimeError):
    """Le LLM n'a pas pu répondre (pas de clé, refus, erreur réseau) : l'appelant passe aux gabarits."""


def provider() -> str:
    return settings.llm_provider


def available() -> bool:
    return provider() in DEFAULT_MODELS and bool(settings.llm_api_key)


def model() -> str:
    return settings.llm_model or DEFAULT_MODELS.get(provider(), "")


def _require() -> None:
    if not available():
        raise LLMUnavailable("LLM non configuré")


# ─────────── Anthropic ───────────
@lru_cache
def _anthropic():
    import anthropic
    return anthropic.AsyncAnthropic(api_key=settings.llm_api_key, base_url=settings.llm_base_url or None,
                                    timeout=60.0, max_retries=2)


async def _anthropic_structured(system: str, user: str, schema: type[T], effort: str, max_tokens: int) -> T:
    import anthropic
    try:
        response = await _anthropic().beta.messages.parse(
            model=model(), max_tokens=max_tokens, betas=[FALLBACK_BETA], fallbacks="default",
            system=system, messages=[{"role": "user", "content": user}],
            output_config={"effort": effort}, output_format=schema)
    except anthropic.APIError as e:
        raise LLMUnavailable(str(e)) from e
    if response.stop_reason == "refusal" or response.parsed_output is None:
        raise LLMUnavailable("refus du modèle ou sortie vide")
    return response.parsed_output


async def _anthropic_stream(system: str, messages: list[dict], effort: str, max_tokens: int) -> AsyncIterator[str]:
    import anthropic
    try:
        async with _anthropic().beta.messages.stream(
                model=model(), max_tokens=max_tokens, betas=[FALLBACK_BETA], fallbacks="default",
                system=system, messages=messages, output_config={"effort": effort}) as stream:
            async for text in stream.text_stream:
                yield text
            final = await stream.get_final_message()
    except anthropic.APIError as e:
        raise LLMUnavailable(str(e)) from e
    if final.stop_reason == "refusal":
        raise LLMUnavailable("refus du modèle")


# ─────────── OpenRouter (API compatible OpenAI) ───────────
@lru_cache
def _openrouter():
    from openai import AsyncOpenAI
    headers = {}
    if settings.openrouter_app_url:
        headers["HTTP-Referer"] = settings.openrouter_app_url
    if settings.openrouter_app_name:
        headers["X-Title"] = settings.openrouter_app_name
    return AsyncOpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url or OPENROUTER_URL,
                       default_headers=headers or None, timeout=60.0, max_retries=2)


def _openrouter_extra(effort: str) -> dict:
    # Niveau de raisonnement normalisé par OpenRouter (low | medium | high)
    return {"reasoning": {"effort": effort if effort in ("low", "medium", "high") else "high"}}


def _json_from(text: str) -> str:
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    return fenced.group(1) if fenced else text[text.find("{"):text.rfind("}") + 1]


async def _openrouter_structured(system: str, user: str, schema: type[T], effort: str, max_tokens: int) -> T:
    import openai
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    try:
        completion = await _openrouter().chat.completions.parse(
            model=model(), messages=messages, response_format=schema, max_tokens=max_tokens,
            extra_body=_openrouter_extra(effort))
        msg = completion.choices[0].message
        if msg.parsed is not None:
            return msg.parsed
        if msg.refusal:
            raise LLMUnavailable("refus du modèle")
    except (openai.BadRequestError, openai.LengthFinishReasonError, ValidationError) as e:
        log.info("OpenRouter : sortie structurée refusée (%s), repli JSON", type(e).__name__)
    except openai.APIError as e:
        raise LLMUnavailable(str(e)) from e
    # Repli : JSON demandé dans le prompt, validé par Pydantic
    instruction = (f"\n\nRéponds UNIQUEMENT par un objet JSON conforme à ce schéma, sans texte autour :\n"
                   f"{json.dumps(schema.model_json_schema(), ensure_ascii=False)}")
    try:
        completion = await _openrouter().chat.completions.create(
            model=model(), max_tokens=max_tokens, extra_body=_openrouter_extra(effort),
            messages=[messages[0], {"role": "user", "content": user + instruction}])
        return schema.model_validate_json(_json_from(completion.choices[0].message.content or ""))
    except (openai.APIError, ValidationError, ValueError) as e:
        raise LLMUnavailable(str(e)) from e


async def _openrouter_stream(system: str, messages: list[dict], effort: str, max_tokens: int) -> AsyncIterator[str]:
    import openai
    try:
        stream = await _openrouter().chat.completions.create(
            model=model(), max_tokens=max_tokens, stream=True, extra_body=_openrouter_extra(effort),
            messages=[{"role": "system", "content": system}, *messages])
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except openai.APIError as e:
        raise LLMUnavailable(str(e)) from e


# ─────────── Interface commune ───────────
async def structured(system: str, user: str, schema: type[T], effort: str = "medium",
                     max_tokens: int = 4000) -> T:
    """Réponse validée par un modèle Pydantic (sortie structurée)."""
    _require()
    impl = _openrouter_structured if provider() == "openrouter" else _anthropic_structured
    try:
        return await impl(system, user, schema, effort, max_tokens)
    except LLMUnavailable as e:
        log.warning("LLM %s (structured) : %s", provider(), e)
        raise


async def stream_text(system: str, messages: list[dict], effort: str = "medium",
                      max_tokens: int = 2000) -> AsyncIterator[str]:
    """Texte de la réponse, morceau par morceau."""
    _require()
    impl = _openrouter_stream if provider() == "openrouter" else _anthropic_stream
    try:
        async for piece in impl(system, messages, effort, max_tokens):
            yield piece
    except LLMUnavailable as e:
        log.warning("LLM %s (stream) : %s", provider(), e)
        raise


async def text(system: str, messages: list[dict], effort: str = "medium", max_tokens: int = 2000) -> str:
    return "".join([t async for t in stream_text(system, messages, effort, max_tokens)])
