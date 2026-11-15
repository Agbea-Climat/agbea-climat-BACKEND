"""Lecture de la question (nœud route) : date, régions, indicateurs et intention, en français et en anglais.

Date (`parse_date`) :
- « juillet 2024 », « juil. 2024 », « July 2024 », « 2024-07 », « 2024/07 », « 07/2024 » → month
- « entre juin et août 2024 », « de juin 2023 à août 2024 »                              → month_range
- « entre 2010 et 2020 », « de 2010 à 2020 », « from 2010 to 2020 »                       → year_range
- « en 2015 », « depuis 2015 », « l'an dernier », « il y a 10 ans », « 2024 » seul        → year
- « le mois dernier », « last month »                                                    → month
- « en juillet » (mois sans année)                                                       → month_only
Un nombre n'est une année que dans un contexte de date (« en 2015 », « année 2015 », mois + année,
question réduite à l'année) et jamais s'il est suivi d'une unité (« plus de 2000 mm »).

Intention (`intent`) : `forecast` (demande sur l'avenir, y compris une date future : jamais de réponse
prédictive), `calendar` (semis, récoltes), `trend` (tendance, évolution), sinon None.

Régions (`regions_in`) : dans l'ordre de la phrase ; les mots ambigus (lacs, ave, vo, mango…) ne
comptent qu'avec un contexte (« préfecture des Lacs », majuscule en milieu de phrase) ; une région niée
(« pas à Lomé », « sauf Kara ») est écartée s'il en reste une autre ; « nord / sud / centre du Togo »
donne les régions correspondantes.
"""
import re
import unicodedata
from datetime import date as _date
from typing import Optional

MONTH_WORDS = {
    # français, entiers et abrégés
    "janvier": 1, "janv": 1, "fevrier": 2, "fevr": 2, "fev": 2, "mars": 3, "avril": 4, "avr": 4, "mai": 5,
    "juin": 6, "juillet": 7, "juil": 7, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12,
    # anglais (« may » seulement suivi d'une année : c'est aussi un verbe)
    "january": 1, "february": 2, "march": 3, "april": 4, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11,
    "dec": 12,
}
_M = "|".join(sorted(MONTH_WORDS, key=len, reverse=True)) + "|may"
_Y = r"(?:19|20)\d{2}"
UNITS = r"(?:mm|millimetres?|m\b|metres?|meters?|km|cm|ha|hectares?|°|degres?|degrees?|%|pour ?cent|percent|tonnes?|kg|personnes?|people|habitants?|fois|times|jours?|days?)"
_RE_ISO = re.compile(rf"\b({_Y})[-/](0?[1-9]|1[0-2])\b(?![-/]\d)")
_RE_SLASH = re.compile(rf"\b(0?[1-9]|1[0-2])/({_Y})\b")
_RE_MONTH_RANGE = re.compile(
    rf"\b(?:entre|de|du|from|between)\s+({_M})\.?(?:\s+({_Y}))?\s+(?:et|a|au|to|and|-)\s+({_M})\.?\s+({_Y})\b")
_RE_YEAR_RANGE = re.compile(rf"\b(?:entre|de|from|between)\s+({_Y})\s+(?:et|a|au|to|and)\s+({_Y})\b|\b({_Y})\s*[-–]\s*({_Y})\b")
_RE_NAMED = re.compile(rf"\b({_M})\.?(?:\s+(?:de|of|d))?,?\s+({_Y})\b")
_RE_NAMED_REV = re.compile(rf"\b({_Y})\s+({_M})\b")
_RE_AGO = re.compile(r"\b(?:il y a|y a)\s+(\d{1,2})\s+ans?\b|\b(\d{1,2})\s+years?\s+ago\b")
_RE_YEAR_CTX = re.compile(
    rf"\b(?:en|de|d|depuis|pour|durant|pendant|in|of|since|for|during|annee|year|an|l an|au cours de|cumul|"
    rf"saison|season|mois)\s+({_Y})\b(?!\s*{UNITS})")
_RE_YEAR_ALONE = re.compile(rf"^\s*(?:et\s+|and\s+)?(?:en\s+|in\s+)?({_Y})\s*$")
_FULL_MONTHS = [k for k in MONTH_WORDS if len(k) > 4 or k in ("mars", "mai", "juin", "aout", "june", "july")]
_RE_MONTH_ONLY = re.compile(r"\b(" + "|".join(_FULL_MONTHS) + r")\b")

LAST_YEAR = ("l an dernier", "l annee derniere", "l an passe", "l annee passee", "annee derniere", "last year")
THIS_YEAR = ("cette annee", "this year")
LAST_MONTH = ("le mois dernier", "mois dernier", "le mois passe", "last month")

FORECAST_WORDS = {"demain", "apres-demain", "prevision", "previsions", "prevoir", "prevois", "prevoit", "prevu",
                  "prevue", "predis", "predire", "predit", "predict", "prediction", "predictions", "pleuvra",
                  "pleuvront", "sera", "seront", "tomorrow", "forecast", "forecasts", "forecasting", "bientot",
                  "upcoming", "coming", "likely", "expect", "futur", "future", "avenir"}
FORECAST_PHRASES = ("va pleuvoir", "vais pleuvoir", "va-t-il pleuvoir", "va t il pleuvoir", "will it", "will the",
                    "will there", "will rain", "going to", "next week", "next month", "next year", "this weekend",
                    "ce week-end", "cette semaine", "dans les jours", "prochains jours", "semaine prochaine",
                    "mois prochain", "annee prochaine", "saison prochaine", "il fera", "fera-t-il", "fera t il",
                    "s attendre", "attendez-vous", "attendez vous", "va continuer", "vont continuer", "va-t-il",
                    "vont-ils", "va-t-elle", "a venir", "dans 10 ans", "d ici")
CALENDAR_WORDS = {"semer", "semis", "seme", "semez", "semons", "planter", "plante", "plantation", "plantations",
                  "recolte", "recoltes", "recolter", "calendrier", "cultural", "sow", "sowing", "plant", "planting",
                  "harvest", "harvesting", "calendar"}
CROP_WORDS = {"mais": "mais", "maize": "mais", "corn": "mais", "mil": "mil", "millet": "mil", "sorgho": "sorgho",
              "sorghum": "sorgho", "riz": "riz", "rice": "riz", "igname": "igname", "ignames": "igname",
              "yam": "igname", "yams": "igname", "manioc": "manioc", "cassava": "manioc"}
WHEN_WORDS = {"quand", "when", "periode", "moment"}
TREND_WORDS = {"tendance", "tendances", "evolue", "evolution", "evoluer", "trend", "trends", "changing",
               "change", "changes", "rechauffement", "warming", "decennie", "decennies", "decade", "decades",
               "augmente", "diminue", "hausse", "baisse", "increase", "decrease", "historique"}

# ── Régions ──
REGION_WORDS = {
    "maritime": ("maritime", "lome", "aneho", "tsevie", "golfe", "lacs", "vo", "zio", "yoto", "ave", "agoe"),
    "plateaux": ("plateaux", "atakpame", "kpalime", "badou", "notse", "amlame", "plateau"),
    "centrale": ("centrale", "sokode", "tchamba", "blitta", "sotouboua", "central"),
    "kara": ("kara", "bassar", "niamtougou", "bafilo", "kante"),
    "savanes": ("savanes", "savane", "dapaong", "mango", "oti", "cinkasse", "tandjoare"),
}
# Mots qui ont aussi un sens courant : comptent seulement avec un contexte
AMBIGUOUS = {"lacs", "vo", "ave", "golfe", "zio", "yoto", "mango", "oti", "plateau", "central", "savane"}
PLACE_CONTEXT = {"prefecture", "prefectures", "ville", "commune", "region", "district", "canton"}
NEGATIONS = {"pas", "sauf", "hors", "excepte", "not", "except", "excluding", "sans"}
ZONES = {"nord": ("kara", "savanes"), "north": ("kara", "savanes"), "northern": ("kara", "savanes"),
         "sud": ("maritime", "plateaux"), "south": ("maritime", "plateaux"), "southern": ("maritime", "plateaux"),
         "centre": ("centrale",), "center": ("centrale",)}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower().replace("’", "'"))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9/\-°%.]+", " ", text).replace(". ", " ").strip(" .")


def words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", normalize(text))


def _ym(y, m) -> str:
    return f"{int(y):04d}-{int(m):02d}"


def _month(word: str) -> int:
    return 5 if word == "may" else MONTH_WORDS[word]


def parse_date(text: str, today: Optional[_date] = None) -> Optional[dict]:
    today = today or _date.today()
    n = normalize(text).replace("'", " ")
    padded = f" {n} "
    if m := _RE_MONTH_RANGE.search(n):
        y2 = int(m[4])
        y1 = int(m[2]) if m[2] else y2
        start, end = _ym(y1, _month(m[1])), _ym(y2, _month(m[3]))
        if start <= end:
            return {"kind": "month_range", "value": start, "end": end}
    if m := _RE_ISO.search(n):
        return {"kind": "month", "value": _ym(m[1], m[2])}
    if m := _RE_SLASH.search(n):
        return {"kind": "month", "value": _ym(m[2], m[1])}
    if m := _RE_YEAR_RANGE.search(n):
        a, b = (m[1], m[2]) if m[1] else (m[3], m[4])
        if a < b:
            return {"kind": "year_range", "value": a, "end": b}
    if m := _RE_NAMED.search(n):
        return {"kind": "month", "value": _ym(m[2], _month(m[1]))}
    if m := _RE_NAMED_REV.search(n):
        return {"kind": "month", "value": _ym(m[1], _month(m[2]))}
    if any(f" {p} " in padded for p in LAST_MONTH):
        y, mo = (today.year - 1, 12) if today.month == 1 else (today.year, today.month - 1)
        return {"kind": "month", "value": _ym(y, mo)}
    if any(f" {p} " in padded for p in LAST_YEAR):
        return {"kind": "year", "value": f"{today.year - 1:04d}"}
    if any(f" {p} " in padded for p in THIS_YEAR):
        return {"kind": "year", "value": f"{today.year:04d}"}
    if m := _RE_AGO.search(n):
        return {"kind": "year", "value": f"{today.year - int(m[1] or m[2]):04d}"}
    if m := _RE_YEAR_CTX.search(n) or _RE_YEAR_ALONE.search(n):
        return {"kind": "year", "value": m[1]}
    if m := _RE_MONTH_ONLY.search(n):
        return {"kind": "month_only", "value": f"{MONTH_WORDS[m[1]]:02d}"}
    return None


def is_future(date_req: Optional[dict], today: Optional[_date] = None) -> bool:
    """Date demandée après aujourd'hui (mois ou année à venir)."""
    if not date_req or date_req["kind"] == "month_only":
        return False
    today = today or _date.today()
    last = date_req.get("end") or date_req["value"]
    if len(last) == 4:
        return int(last) > today.year
    return last > f"{today.year:04d}-{today.month:02d}"


def is_forecast(text: str, date_req: Optional[dict] = None, today: Optional[_date] = None) -> bool:
    n = normalize(text).replace("'", " ")
    ws = set(re.findall(r"[a-z0-9\-]+", n))
    padded = f" {n} "
    return (bool(ws & FORECAST_WORDS) or any(f" {p} " in padded or p in n for p in FORECAST_PHRASES)
            or bool(re.search(r"\bwill\b|\bdans \d+ ans\b|\bin \d+ years\b", n)) or is_future(date_req, today))


def crops(text: str) -> list[str]:
    return sorted({CROP_WORDS[w] for w in words(text) if w in CROP_WORDS})


def intent(text: str, date_req: Optional[dict] = None, today: Optional[_date] = None) -> Optional[str]:
    """Intention explicite de la question, ou None (le nœud route garde alors celle du tour précédent)."""
    ws = set(words(text))
    if is_forecast(text, date_req, today):
        return "forecast"
    if ws & CALENDAR_WORDS or (crops(text) and ws & WHEN_WORDS):
        return "calendar"
    if ws & TREND_WORDS or any(w.startswith("evolu") for w in ws):
        return "trend"
    return None


def _tokens(text: str) -> list[tuple[str, str, bool]]:
    """(mot normalisé, mot original, début de phrase) dans l'ordre du texte."""
    out, start = [], True
    for m in re.finditer(r"[^\W\d_]+|\d+|[.!?;:()]", text):
        tok = m.group(0)
        if tok in ".!?;:()":
            start = tok in ".!?"
            continue
        norm = "".join(c for c in unicodedata.normalize("NFKD", tok.lower()) if not unicodedata.combining(c))
        out.append((norm, tok, start))
        start = False
    return out


def regions_in(text: str) -> list[str]:
    """Régions citées, dans l'ordre de la phrase (voir le docstring du module)."""
    toks = _tokens(text)
    found: list[tuple[str, bool]] = []   # (région, niée)
    for i, (w, orig, start) in enumerate(toks):
        rid = next((r for r, ws in REGION_WORDS.items() if w in ws), None)
        if rid is None:
            continue
        if w in AMBIGUOUS:
            ctx = {t[0] for t in toks[max(0, i - 3):i]}
            if not (ctx & PLACE_CONTEXT or (orig[:1].isupper() and not start)):
                continue
        negated = bool({t[0] for t in toks[max(0, i - 3):i]} & NEGATIONS)
        if rid not in [r for r, _ in found]:
            found.append((rid, negated))
    kept = [r for r, neg in found if not neg]
    if found and not kept:
        kept = [r for r, _ in found]
    if not kept:
        for w, _, _ in toks:
            if w in ZONES:
                kept += [r for r in ZONES[w] if r not in kept]
    return kept
