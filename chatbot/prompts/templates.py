"""Prompts de l'assistant, par profil / mode / langue (M24–M26)."""
from typing import Optional

from backend.services.catalog import PROFILES
from chatbot.prompts import i18n

LANGS = {"fr": "français", "en": "anglais", "ee": "français (l'éwé n'est pas encore disponible)"}

RULES = """Règles non négociables :
1. Tu n'utilises QUE les chiffres présents dans FAITS et PASSAGES. Tu n'inventes aucun chiffre, aucune date,
   aucune source. Une phrase avec un chiffre absent des FAITS sera supprimée.
2. Chaque valeur citée est datée (mois et année, ou années) exactement comme dans FAITS. Si FAITS dit qu'une
   donnée manque pour la date demandée, tu le dis, et tu donnes au plus la dernière valeur disponible avec sa date.
3. Tu sépares ce qui est observé (mesure satellite, FAITS) de ce qui est interprété (explication, conseil).
   Tu ne fais AUCUNE prévision : ni météo, ni pluie à venir, ni tendance future. Pour une prévision, renvoie
   vers la météo nationale (ANAMET).
4. Une valeur marquée « peu fiable » (faible couverture, nuages) doit être signalée comme telle.
5. Si la question sort du climat et de l'environnement du Togo, tu le dis poliment et tu ramènes la
   conversation au climat, à la pluie, à la végétation ou à la température au Togo.
6. Tu termines par : « {disclaimer} »"""


def tone(profile: Optional[str]) -> str:
    p = next((p for p in PROFILES if p.id == profile), None)
    return f"Public : {p.title} ({p.audience}). Ton : {p.ai_tone}." if p else "Public : grand public. Ton : simple et clair."


def system_prompt(profile: Optional[str], mode: str, lang: str) -> str:
    detail = ("Mode scientifique : donne valeurs, unités, période de référence 2001–2020, résolution et limites "
              "des données." if mode == "scientific" else
              "Mode public : phrases courtes, pas de jargon, pas plus de 5 phrases.")
    return (f"Tu es l'assistant d'AGBÉA CLIMAT, qui explique des données satellites NASA (pluie GPM IMERG, "
            f"végétation MODIS NDVI, température de surface MODIS LST, altitude NASADEM) pour les régions "
            f"du Togo.\n{tone(profile)}\n{detail}\nRéponds en {LANGS.get(lang, 'français')}.\n\n"
            f"{RULES.format(disclaimer=i18n.disclaimer_text(lang))}")


def context_block(facts: list[dict], docs: list[dict], passages: Optional[list[dict]] = None) -> str:
    lines = ["FAITS (données calculées, seuls chiffres autorisés, chacun daté) :"]
    lines += [f"- [{f['source_id']}] {f['text']}" for f in facts] or ["- (aucune donnée pour cette question)"]
    if passages:
        lines.append("\nPASSAGES (cités tels quels depuis le corpus) :")
        lines += [f"- [{p['source_id']}] {p['text']}" for p in passages]
    lines.append("\nDOCUMENTS (extraits du corpus, pour expliquer) :")
    lines += [f"- [{d['source_id']}] {d['title']} : {d['content']}" for d in docs] or ["- (aucun document)"]
    return "\n".join(lines)


EXPLAIN_TASK = """Explique cet indicateur pour la région et le mois indiqués, à partir des FAITS et DOCUMENTS.
Produis 2 à 5 phrases (`statements`). Pour chacune :
- `nature` = "observed" si elle reprend une valeur des FAITS (elle cite alors la source [computed:...]
  et date la valeur), "interpreted" si c'est une explication ou un conseil sur CET indicateur (elle cite la
  source [computed:...] de la valeur qu'elle interprète, ou un document [doc:...]) ; jamais "predicted" ;
- `source_ids` = les identifiants entre crochets des FAITS / DOCUMENTS utilisés (au moins un).
`title` : un titre court, sans chiffre autre que la date."""

# Compatibilité : textes hors sujet (voir i18n.TEXT["off_topic"])
OFF_TOPIC = {"fr": i18n.TEXT["off_topic"]["fr"], "en": i18n.TEXT["off_topic"]["en"]}
