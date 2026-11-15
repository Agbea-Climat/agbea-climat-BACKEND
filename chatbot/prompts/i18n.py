"""Textes de l'assistant en français et en anglais (M24–M26).

Langues : `fr` (défaut) et `en`. `ee` (éwé) n'est pas encore disponible : repli sur le français
(documenté dans contract/types.ts, type `Lang`).

Nombres : virgule décimale en français (« 273,8 m »), point en anglais (« 273.8 m »), jamais de
séparateur de milliers (« 1234,5 mm ») pour que chaque nombre reste lisible par le garde-fou des chiffres.
"""
from typing import Literal

from backend.core.constants import DISCLAIMER

L = Literal["fr", "en"]

# Traduction de l'avertissement (le champ `disclaimer` garde toujours le texte exact en français)
DISCLAIMER_EN = ("AGBÉA CLIMAT helps you understand the environment. It does not replace official forecasts "
                 "or warning systems.")

MONTHS = {
    "fr": ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
           "novembre", "décembre"),
    "en": ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
           "November", "December"),
}

# Nom de l'indicateur en tête de phrase
NAMES = {
    "fr": {"precipitation": "Pluie", "ndvi": "Végétation (NDVI)", "lst_day": "Température du sol le jour (LST)",
           "elevation": "Altitude"},
    "en": {"precipitation": "Rainfall", "ndvi": "Vegetation greenness (NDVI)",
           "lst_day": "Daytime land surface temperature (LST)", "elevation": "Elevation"},
}
# Nom en milieu de phrase (« la série de pluie »)
NOUNS = {
    "fr": {"precipitation": "pluie", "ndvi": "végétation", "lst_day": "température du sol", "elevation": "altitude"},
    "en": {"precipitation": "rainfall", "ndvi": "vegetation", "lst_day": "land surface temperature",
           "elevation": "elevation"},
}
DECIMALS = {"precipitation": 1, "ndvi": 3, "lst_day": 1}


def lang_of(lang: str | None) -> L:
    return "en" if lang == "en" else "fr"


def disclaimer_text(lang: str | None) -> str:
    return DISCLAIMER_EN if lang_of(lang) == "en" else DISCLAIMER


def month_label(date: str, lang: str | None) -> str:
    """« juillet 2024 » / « July 2024 » pour YYYY-MM ; l'année seule pour YYYY."""
    if len(date) == 4:
        return date
    y, m = date.split("-")[:2]
    return f"{MONTHS[lang_of(lang)][int(m) - 1]} {y}"


def num(x: float, decimals: int, lang: str | None) -> str:
    s = f"{x:.{decimals}f}"
    return s.replace(".", ",") if lang_of(lang) == "fr" else s


def signed(x: float, decimals: int, lang: str | None) -> str:
    s = f"{x:+.{decimals}f}"
    return s.replace(".", ",") if lang_of(lang) == "fr" else s


def name(indicator: str, lang: str | None) -> str:
    return NAMES[lang_of(lang)].get(indicator, indicator)


def noun(indicator: str, lang: str | None) -> str:
    return NOUNS[lang_of(lang)].get(indicator, indicator)


def region_phrase(region_name: str, lang: str | None) -> str:
    return f"region {region_name}" if lang_of(lang) == "en" else f"région {region_name}"


# Phrases fixes : TEXT[clé][langue]
TEXT = {
    "intro": {"fr": "Observations satellites (NASA) pour la région {region} :",
              "en": "NASA satellite observations for the {region} region:"},
    "need_region": {"fr": "Précisez une région du Togo (Maritime, Plateaux, Centrale, Kara ou Savanes) pour que je "
                          "vous donne les observations satellites correspondantes.",
                    "en": "Please name a region of Togo (Maritime, Plateaux, Centrale, Kara or Savanes) so I can "
                          "give you the matching satellite observations."},
    "more": {"fr": "Pour en savoir plus : « {title} ».", "en": "To learn more (in French): \"{title}\"."},
    "latest": {"fr": "Données les plus récentes : {items}.", "en": "Most recent data: {items}."},
    "no_forecast": {
        "fr": "AGBÉA CLIMAT ne fait pas de prévision météo : pour savoir s'il va pleuvoir, consultez la météo "
              "nationale (ANAMET, Agence nationale de la météorologie du Togo). Je peux seulement vous montrer "
              "ce que les satellites ont déjà observé.",
        "en": "AGBÉA CLIMAT does not make weather forecasts: to know whether it will rain, check the national "
              "weather service (ANAMET, Togo's national meteorological agency). I can only show you what "
              "satellites have already observed."},
    "future": {"fr": "{month} est dans le futur : AGBÉA CLIMAT ne montre que des observations passées et ne fait "
                     "pas de prévision.",
               "en": "{month} is in the future: AGBÉA CLIMAT only shows past observations and makes no forecast."},
    "calendar_intro": {"fr": "D'après le document « {title} » :", "en": "According to the document \"{title}\" "
                                                                        "(quoted in French):"},
    "zone_intro": {"fr": "D'après la fiche « {title} » (calculée à partir des mêmes données satellites) :",
                   "en": "According to the fact sheet \"{title}\" (computed from the same satellite data, quoted "
                         "in French):"},
    "calendar_none": {"fr": "Je n'ai pas trouvé le calendrier agricole dans le corpus de documents.",
                      "en": "I could not find the agricultural calendar in the document corpus."},
    "calendar_caveat": {"fr": "Les dates exactes changent chaque année avec le démarrage des pluies : confirmez-les "
                              "avec les services agricoles.",
                        "en": "Exact dates change every year with the onset of the rains: confirm them with the "
                              "agricultural extension services."},
    "trend_lst": {"fr": "Les tendances de température du sol s'arrêtent en 2020 et les valeurs en décembre 2022 : "
                        "ensuite, la dérive de l'orbite du satellite Terra fausse les mesures.",
                  "en": "Land surface temperature trends stop in 2020 and values in December 2022: after that, the "
                        "orbit drift of the Terra satellite distorts the measurements."},
    "trend_note": {"fr": "Une comparaison entre deux décennies décrit le passé ; elle ne dit pas ce qui va se passer.",
                   "en": "A comparison between two decades describes the past; it does not say what will happen."},
    "off_topic": {
        "fr": "Je suis l'assistant d'AGBÉA CLIMAT : je réponds aux questions sur le climat et l'environnement "
              "du Togo (pluie, végétation, température du sol, altitude) à partir des données satellites de la "
              "NASA. Posez-moi par exemple : « Comment évolue la pluie dans les Savanes ? »",
        "en": "I am the AGBÉA CLIMAT assistant: I answer questions about climate and the environment in Togo "
              "(rain, vegetation, land temperature, elevation) from NASA satellite data. Try: \"How is rainfall "
              "changing in Savanes?\""},
    "interrupted": {"fr": "(La réponse rédigée a été interrompue. Voici les données calculées :)",
                    "en": "(The written answer was interrupted. Here is the computed data:)"},
    "doc_pointer": {"fr": "Pour comprendre cet indicateur, voir « {title} ».",
                    "en": "To understand this indicator, see \"{title}\" (in French)."},
}


def t(key: str, lang: str | None, **kw) -> str:
    return TEXT[key][lang_of(lang)].format(**kw)
