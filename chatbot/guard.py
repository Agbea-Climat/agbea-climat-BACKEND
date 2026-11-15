"""Garde-fous appliqués à tout texte produit par le LLM (chat et /explain).

1. Chiffres : chaque nombre est lu avec son unité (mm, °C, %, m, km) et le couple (nombre, unité) doit
   figurer dans les faits / passages fournis au LLM (« 1,50 mm » = « 1.5 mm ») ; un nombre sans unité
   doit y figurer tel quel, et une année n'est acceptée que comme date (« 2024 mm » est refusé).
   Sinon la phrase est retirée.
2. Prévision : une proposition qui annonce l'avenir (« il va pleuvoir », « la saison sera
   pluvieuse », « attendez-vous à… », « rain is likely ») est retirée avec sa phrase. Une négation
   (« AGBÉA ne fait pas de prévision ») n'excuse que la proposition qui nie, pas la suivante
   (« Pas de prévision officielle, mais il va pleuvoir demain » est retirée).
3. Avertissement : `ensure_disclaimer` exige DISCLAIMER (ou sa traduction) EN FIN de texte.

Le flux SSE passe par `SentenceGate` : le texte n'est envoyé qu'une phrase complète à la fois, après
contrôle, pour ne jamais diffuser un chiffre non vérifié.
"""
import re
from typing import Iterable

from backend.core.constants import DISCLAIMER
from chatbot.prompts import i18n
from chatbot.tools.question import normalize

_QTY = re.compile(r"(\d+(?:[.,]\d+)?)\s*(mm|millim[eè]tres?|°\s?c|°|degr[eé]s?|degrees?|%|pour\s?cent|percent|km|"
                  r"m[eè]tres?|meters?|m)?(?![a-zA-Z])", re.I)
_UNIT = {"mm": "mm", "millimetre": "mm", "millimetres": "mm", "millimètre": "mm", "millimètres": "mm",
         "°c": "°C", "° c": "°C", "°": "°C", "degre": "°C", "degres": "°C", "degré": "°C", "degrés": "°C",
         "degree": "°C", "degrees": "°C", "%": "%", "pour cent": "%", "pourcent": "%", "percent": "%",
         "km": "km", "m": "m", "metre": "m", "metres": "m", "mètre": "m", "mètres": "m", "meter": "m", "meters": "m"}
_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+|\n+")
_CLAUSE = re.compile(r"[,;:—()]| mais | but | however | cependant | pourtant | toutefois ")
PREDICTIVE = re.compile(
    r"\b(va|vont|devrait|devraient|risque|risquent) (continuer|pleuvoir|augmenter|baisser|diminuer|etre|faire|y avoir)"
    r"|\bpleuvra|\bpleuvront|\bil fera\b|\bsera\b|\bseront\b|\bs attendre\b|\battendez vous\b|\ba venir\b|\bdemain\b"
    r"|\bsemaine prochaine\b|\bmois prochain\b|\bannee prochaine\b|\bprochains? (jours|semaines|mois)\b|\bbientot\b"
    r"|\bwill\b|\bgoing to\b|\blikely\b|\bexpect|\bcoming (days|weeks|months|season|year)\b|\btomorrow\b"
    r"|\bnext (week|month|year|season)\b|\bsoon\b|\bforecast to\b|\bis coming\b")
# Une proposition qui nie toute prévision (elle seule est exemptée)
NEGATED = re.compile(r"\b(ne|n) (fait|fais|font|peut|peux|prevoit|predit) (pas|aucune?)\b|\bpas de prevision"
                     r"|\baucune prevision\b|\bdoes not (make|forecast|predict)\b|\bcannot (forecast|predict)\b"
                     r"|\bno forecast\b|\bnot a forecast\b|\bpour savoir s\b|\bto know whether\b|\bto know if\b")


def quantities(text: str) -> set[tuple[str, str]]:
    """{(nombre normalisé, unité)} ; unité "" pour un nombre nu."""
    out = set()
    for num, unit in _QTY.findall(text):
        whole, _, frac = num.replace(",", ".").partition(".")
        whole, frac = whole.lstrip("0") or "0", frac.rstrip("0")
        u = _UNIT.get(re.sub(r"\s+", " ", unit.lower()), "") if unit else ""
        out.add((f"{whole}.{frac}" if frac else whole, u))
    return out


def numbers(text: str) -> set[str]:
    return {n for n, _ in quantities(text)}


def known_numbers(texts: Iterable[str]) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for t in texts:
        out |= quantities(t)
    return out


def numbers_ok(text: str, known: set[tuple[str, str]]) -> bool:
    bare = {n for n, u in known if u == ""}
    any_unit = {n for n, _ in known}
    for n, u in quantities(text):
        if u:
            if (n, u) not in known:
                return False
        elif n not in (bare if re.fullmatch(r"(19|20)\d{2}", n) else any_unit):
            return False
    return True


def is_predictive(sentence: str) -> bool:
    for clause in _CLAUSE.split(f" {normalize(sentence).replace('-', ' ')} "):
        c = f" {clause.strip()} "
        if PREDICTIVE.search(c) and not NEGATED.search(c):
            return True
    return False


def sentence_ok(sentence: str, known: set[tuple[str, str]]) -> bool:
    return numbers_ok(sentence, known) and not is_predictive(sentence)


def split_sentences(text: str) -> list[str]:
    return [s for s in _SENTENCE_END.split(text) if s.strip()]


def filter_text(text: str, known: set[tuple[str, str]]) -> str:
    return " ".join(s.strip() for s in split_sentences(text) if sentence_ok(s, known))


def ensure_disclaimer(text: str, lang: str) -> str:
    """Le texte se termine par l'avertissement (ajouté à la fin s'il manque ou s'il est ailleurs)."""
    text = text.rstrip()
    if text.endswith(DISCLAIMER) or text.endswith(i18n.DISCLAIMER_EN):
        return text
    return f"{text}\n\n{i18n.disclaimer_text(lang)}".strip()


class SentenceGate:
    """Reçoit le texte du LLM morceau par morceau, rend les phrases complètes qui passent les contrôles."""

    def __init__(self, known: set[tuple[str, str]]):
        self.known = known
        self.buffer = ""
        self.kept: list[str] = []
        self.dropped: list[str] = []

    def _judge(self, sentence: str) -> str:
        s = sentence.strip()
        if not s:
            return ""
        if sentence_ok(s, self.known):
            self.kept.append(s)
            return s + " "
        self.dropped.append(s)
        return ""

    def feed(self, piece: str) -> str:
        self.buffer += piece
        parts = _SENTENCE_END.split(self.buffer)
        if len(parts) == 1:
            return ""
        self.buffer = parts[-1]
        return "".join(self._judge(p) for p in parts[:-1])

    def close(self) -> str:
        out = self._judge(self.buffer)
        self.buffer = ""
        return out

    @property
    def text(self) -> str:
        return " ".join(self.kept)
