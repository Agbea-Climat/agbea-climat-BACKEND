"""Faits chiffrés de l'assistant (nœud fetch_data et /explain) : uniquement via backend.services.

Chaque chiffre cité par l'IA vient d'un fait construit ici à partir d'un service (M14 snapshot,
M15 série, M16 comparaison, altitude de static.json) et porte une source « computed » :

    computed:<region>:<indicator>:<date>
        <date> = YYYY-MM     valeur d'un mois (M14)
               = YYYY        valeur annuelle : cumul (pluie) ou moyenne (NDVI, température) (M15)
               = YYYY/YYYY   période d'années (intervalle ISO 8601) : moyenne M16 ou série annuelle M15
               = YYYY-MM/YYYY-MM  série mensuelle d'une plage de mois (M15)
               = static      altitude (NASADEM, ne dépend pas du temps)

Chaque fait cite aussi le jeu de données (`ds:<dataset_id>`). Chaque valeur est datée dans son texte
(« Pluie en septembre 2025… ») : les séries s'arrêtent à des mois différents (pluie IMERG Final
publiée avec retard, température du sol arrêtée en 2022-12, décision D30).
"""
import re
from datetime import date as _date
from typing import Optional

from backend.core.exceptions import ApiError, BadRequest
from backend.repositories import store
from backend.schemas import IndicatorSnapshot, Source
from backend.services import catalog, indicators, regions
from chatbot.prompts import i18n

TS = indicators.TS_INDICATORS
BASE_LABEL = "2001-2020"
FIRST_DECADE = ("2001", "2010")
LST_TREND_LAST_YEAR = 2020   # décision D27 : tendances de température arrêtées à 2020
MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

TREND_WORDS = {
    "fr": {"above_normal": "au-dessus de la normale {p}", "below_normal": "en dessous de la normale {p}",
           "normal": "proche de la normale {p}"},
    "en": {"above_normal": "above the {p} normal", "below_normal": "below the {p} normal",
           "normal": "close to the {p} normal"},
}


def pct(x: float, lang: str) -> str:
    """« -23,1 % » en français, « -23.1% » en anglais."""
    return f"{i18n.signed(x, 1, lang)} %" if lang == "fr" else f"{i18n.signed(x, 1, lang)}%"


def computed_id(region_id: str, indicator: str, date: str) -> str:
    return f"computed:{region_id}:{indicator}:{date}"


def check_date_format(value: Optional[str]) -> Optional[str]:
    if value is not None and not MONTH_RE.match(value):
        raise BadRequest("invalid_period", f"date doit être au format YYYY-MM (reçu : {value})")
    return value


def check_in_data(value: str) -> str:
    """Mois dans la période des données toutes séries confondues, sinon 400 invalid_period."""
    first, last = store.first_date(), store.last_date()
    if first is None or not first <= value <= last:
        raise BadRequest("invalid_period", f"date ({value}) hors de la période des données ({first} → {last})")
    return value


def last_complete_year(indicator: str, region_id: str) -> Optional[int]:
    last = store.last_date(indicator, region_id)
    if last is None:
        return None
    return int(last[:4]) if last[5:7] == "12" else int(last[:4]) - 1


def _prev_month_with_value(region_id: str, indicator: str, date: str) -> Optional[str]:
    return max((d for d, o in store.series(region_id, indicator).items() if d < date and o.value is not None),
               default=None)


class Collector:
    """Rassemble faits, sources, snapshots et séries pour une région, dans une langue."""

    def __init__(self, region_id: str, lang: str = "fr", mode: str = "public", style: str = "public"):
        self.region_id = region_id
        self.region = regions.get_region(region_id)
        self.lang = i18n.lang_of(lang)
        self.mode = mode
        self.style = style
        self.facts: list[dict] = []
        self.sources: dict[str, Source] = {}
        self.snapshots: list[IndicatorSnapshot] = []
        self.series: list = []
        self.latest_dates: dict[str, str] = {}   # indicateur → mois de la donnée la plus récente citée

    # ── sources ──
    def _ds(self, dataset_id: str) -> str:
        ds = catalog.get_dataset(dataset_id)
        sid = f"ds:{ds.id}"
        self.sources.setdefault(sid, Source(id=sid, kind="dataset", title=ds.name, dataset_id=ds.id,
                                            url=ds.source_url))
        return sid

    def _computed(self, indicator: str, date: str, title: str) -> str:
        ds = catalog.dataset_for(indicator)
        sid = computed_id(self.region_id, indicator, date)
        self.sources.setdefault(sid, Source(id=sid, kind="computed", title=title, dataset_id=ds.id,
                                            url=ds.source_url))
        return sid

    def _add(self, indicator: str, kind: str, text: str, source_ids: list[str], date: Optional[str] = None,
             has_value: bool = False) -> dict:
        fact = {"indicator": indicator, "kind": kind, "text": text, "source_ids": source_ids,
                "source_id": source_ids[0], "date": date, "has_value": has_value}
        self.facts.append(fact)
        return fact

    # ── textes ──
    def _units(self, indicator: str) -> str:
        u = catalog.dataset_for(indicator).units
        return f" {u}" if u else ""

    def _normal_part(self, indicator: str, base: Optional[float], anomaly: Optional[float]) -> str:
        if base is None:
            return ""
        lang, u, dec = self.lang, self._units(indicator), i18n.DECIMALS[indicator]
        parts = [f"{i18n.num(base, dec, lang)}{u}"]
        if anomaly is not None and indicator != "lst_day":
            word = "écart" if lang == "fr" else "anomaly"
            parts.append(f"{word} {pct(anomaly, lang)}")
        sep = " ; " if lang == "fr" else "; "
        return sep.join(parts)

    def _coverage(self, valid_frac: Optional[float], low: bool) -> str:
        if valid_frac is None:
            return ""
        pct = round(valid_frac * 100)
        if low:
            return (f" Attention, cette valeur est peu fiable : les nuages ne laissaient voir que {pct} % de la "
                    "région ce mois-là." if self.lang == "fr"
                    else f" Note that this value is uncertain: clouds left only {pct}% of the region visible that month.")
        if self.style == "scientific":
            return (f" Part de la région visible ce mois-là : {pct} %." if self.lang == "fr"
                    else f" Share of the region visible that month: {pct}%.")
        return ""

    def _body(self, ind: str, value: float, yearly: bool = False) -> str:
        """« il est tombé 31,8 mm de pluie en moyenne sur la région Maritime » (sans majuscule ni point)."""
        v, r = i18n.num(value, i18n.DECIMALS[ind], self.lang), self.region.name
        if self.lang == "fr":
            return {
                "precipitation": (f"il est tombé au total {v} mm de pluie sur la région {r}" if yearly
                                  else f"il est tombé {v} mm de pluie en moyenne sur la région {r}"),
                "ndvi": f"l'indice de verdure de la végétation (NDVI) était en moyenne de {v} sur la région {r}",
                "lst_day": f"la température du sol en journée était en moyenne de {v} °C dans la région {r}",
            }[ind]
        return {
            "precipitation": (f"a total of {v} mm of rain fell over the {r} region" if yearly
                              else f"{v} mm of rain fell on average over the {r} region"),
            "ndvi": f"the vegetation greenness index (NDVI) averaged {v} over the {r} region",
            "lst_day": f"the daytime land surface temperature averaged {v} °C in the {r} region",
        }[ind]

    @staticmethod
    def _trend_of(ind: str, value: Optional[float], base: Optional[float], anomaly: Optional[float]) -> Optional[str]:
        """Même règle que le service (±10 %, ±1,5 °C pour la température), pour les valeurs annuelles."""
        if value is None or base is None:
            return None
        if ind == "lst_day":
            d = value - base
            return "above_normal" if d > 1.5 else "below_normal" if d < -1.5 else "normal"
        if anomaly is None:
            return None
        return "above_normal" if anomaly > 10 else "below_normal" if anomaly < -10 else "normal"

    def _compare(self, ind: str, base: Optional[float], anomaly: Optional[float], trend: Optional[str],
                 month: Optional[str] = None) -> str:
        """« C'est moins de pluie que d'habitude pour un mois de juillet : la moyenne 2001-2020 est de … »"""
        if base is None or trend is None:
            return ""
        fr = self.lang == "fr"
        u = {"precipitation": " mm", "ndvi": "", "lst_day": " °C"}[ind]
        b = f"{i18n.num(base, i18n.DECIMALS[ind], self.lang)}{u}"
        words = {
            "fr": {"precipitation": ("plus de pluie que d'habitude", "moins de pluie que d'habitude",
                                     "une quantité de pluie proche de l'habitude"),
                   "ndvi": ("une végétation plus verte que d'habitude", "une végétation moins verte que d'habitude",
                            "une végétation proche de l'habitude"),
                   "lst_day": ("un sol plus chaud que d'habitude", "un sol plus frais que d'habitude",
                               "une température proche de l'habitude")},
            "en": {"precipitation": ("more rain than usual", "less rain than usual", "about the usual amount of rain"),
                   "ndvi": ("greener vegetation than usual", "less green vegetation than usual",
                            "vegetation close to usual"),
                   "lst_day": ("a warmer ground than usual", "a cooler ground than usual",
                               "a temperature close to usual")},
        }["fr" if fr else "en"][ind]
        w = {"above_normal": words[0], "below_normal": words[1], "normal": words[2]}[trend]
        if fr:
            if month:
                m = i18n.MONTHS["fr"][int(month[5:7]) - 1]
                when = f" pour un mois d'{m}" if m[0] in "aeiouéèêàâîôûy" else f" pour un mois de {m}"
                text = f" C'est {w}{when} : la moyenne {BASE_LABEL} est de {b}"
            else:
                text = f" C'est {w} : la moyenne annuelle {BASE_LABEL} est de {b}"
            if anomaly is not None and ind != "lst_day":
                text += f", soit un écart de {pct(anomaly, self.lang)}"
        else:
            if month:
                text = f" That is {w} for {i18n.MONTHS['en'][int(month[5:7]) - 1]}: the {BASE_LABEL} average is {b}"
            else:
                text = f" That is {w}: the {BASE_LABEL} yearly average is {b}"
            if anomaly is not None and ind != "lst_day":
                text += f", an anomaly of {pct(anomaly, self.lang)}"
        return text + "."

    def value_text(self, s: IndicatorSnapshot, latest: bool = False) -> str:
        lang, ind = self.lang, s.indicator
        when = i18n.month_label(s.date, lang)
        body = self._body(ind, s.value)
        if lang == "fr":
            text = (f"Les dernières mesures disponibles datent de {when} : {body}." if latest
                    else f"En {when}, {body}.")
        else:
            text = (f"The latest available measurements are from {when}: {body}." if latest
                    else f"In {when}, {body}.")
        text += self._compare(ind, s.baseline, s.anomaly_pct, s.trend if s.trend != "unknown" else None, s.date)
        return text + self._coverage(s.valid_frac, s.low_coverage)

    # ── faits ──
    def _snapshot(self, indicator: str, date: str) -> IndicatorSnapshot:
        return indicators.snapshot(self.region_id, indicator, date, self.mode)

    def _value_fact(self, s: IndicatorSnapshot, kind: str, latest: bool = False) -> dict:
        ds = self._ds(s.dataset_id)
        sid = self._computed(s.indicator, s.date, f"{s.label} — {self.region.name} ({s.date})")
        text = self.value_text(s, latest=latest)
        self.snapshots.append(s)
        prev = self.latest_dates.get(s.indicator)
        if prev is None or s.date > prev:
            self.latest_dates[s.indicator] = s.date
        return self._add(s.indicator, kind, text, [sid, ds], date=s.date, has_value=True)

    def latest(self, indicator: str, before: Optional[str] = None) -> Optional[dict]:
        """Dernière valeur disponible de l'indicateur (avant `before` si précisé), datée."""
        last = store.last_date(indicator, self.region_id)
        if before is not None and (last is None or last >= before):
            last = _prev_month_with_value(self.region_id, indicator, before)
        if last is None:
            return None
        return self._value_fact(self._snapshot(indicator, last), "latest", latest=before is not None)

    def month(self, indicator: str, date: str, today: Optional[_date] = None) -> dict:
        """Valeur d'un mois demandé. Absente → on le dit, puis dernière valeur disponible DATÉE."""
        today = today or _date.today()
        lang, noun, ds = self.lang, i18n.noun(indicator, self.lang), self._ds(catalog.dataset_for(indicator).id)
        when = i18n.month_label(date, lang)
        first, last = store.first_date(indicator), store.last_date(indicator, self.region_id)
        if date > f"{today.year:04d}-{today.month:02d}":
            fact = self._add(indicator, "future", i18n.t("future", lang, month=when[0].upper() + when[1:]), [ds],
                             date=date)
            self.latest(indicator)
            return fact
        if first is not None and date < first:
            text = (f"Les données de {noun} commencent en {i18n.month_label(first, lang)} : je n'ai donc rien "
                    f"pour {when}."
                    if lang == "fr" else
                    f"{noun.capitalize()} data start in {i18n.month_label(first, lang)}: nothing for {when}.")
            return self._add(indicator, "out_of_range", text, [ds], date=date)
        s = self._snapshot(indicator, date)
        if s.value is not None:
            return self._value_fact(s, "value")
        stops = last is not None and last < date
        if lang == "fr":
            text = f"Pas de donnée de {noun} pour {when} dans la région {self.region.name}"
            text += (f" pour l'instant : les mesures s'arrêtent en {i18n.month_label(last, lang)}." if stops
                     else " : les satellites n'ont rien pu mesurer ce mois-là.")
        else:
            text = f"No {noun} data for {when} in the {self.region.name} region"
            text += (f" yet: measurements stop in {i18n.month_label(last, lang)}." if stops
                     else ": the satellites could not measure anything that month.")
        fact = self._add(indicator, "missing", text, [ds], date=date)
        self.latest(indicator, before=date)
        return fact

    def month_only(self, indicator: str, month: str) -> dict:
        """« en juillet » sans année : le mois le plus récent disponible pour cet indicateur."""
        last = store.last_date(indicator, self.region_id)
        if last is None:
            return self.month(indicator, f"{_date.today().year:04d}-{month}")
        year = int(last[:4]) if last[5:7] >= month else int(last[:4]) - 1
        return self.month(indicator, f"{year:04d}-{month}")

    def year(self, indicator: str, year: str) -> dict:
        """Valeur annuelle (M15, granularity=year) ; année incomplète → on le dit + dernier mois de l'année."""
        lang, noun, ds = self.lang, i18n.noun(indicator, self.lang), self._ds(catalog.dataset_for(indicator).id)
        first, last = store.first_date(indicator), store.last_date(indicator, self.region_id)
        g_first, g_last = store.first_date(), store.last_date()
        if first is None or last is None or year < first[:4] or year > g_last[:4]:
            text = (f"Pas de donnée de {noun} pour {year} : la série couvre {first[:4] if first else '?'}–"
                    f"{last[:4] if last else '?'}." if lang == "fr" else
                    f"No {noun} data for {year}: the series covers {first[:4] if first else '?'}–"
                    f"{last[:4] if last else '?'}.")
            return self._add(indicator, "out_of_range", text, [ds], date=year)
        start, end = max(f"{year}-01", g_first), min(f"{year}-12", g_last)
        ts = indicators.timeseries(self.region_id, indicator, start, end, "year")
        p = next((p for p in ts.points if p.date == year), None)
        agg = {"fr": "cumul annuel" if indicator == "precipitation" else "moyenne annuelle",
               "en": "annual total" if indicator == "precipitation" else "annual mean"}[lang]
        if p is None or p.value is None:
            if lang == "fr":
                text = (f"Pas de {agg} de {noun} pour {year} dans la {i18n.region_phrase(self.region.name, lang)} : "
                        f"l'année est incomplète dans les données")
                text += f" (la série s'arrête en {i18n.month_label(last, lang)})." if last[:4] <= year else "."
            else:
                text = f"No {agg} of {noun} for {year} in the {self.region.name} region: the year is incomplete"
                text += f" (the series ends in {i18n.month_label(last, lang)})." if last[:4] <= year else "."
            fact = self._add(indicator, "year_incomplete", text, [ds], date=year)
            if last >= f"{year}-01":   # des mois de cette année existent : le plus récent, daté
                self.latest(indicator, before=f"{int(year) + 1:04d}-01")
            return fact
        sid = self._computed(indicator, year, f"{catalog.LABELS[indicator]} — {self.region.name} ({year})")
        body = self._body(indicator, p.value, yearly=True)
        text = f"En {year}, {body}." if lang == "fr" else f"In {year}, {body}."
        text += self._compare(indicator, p.baseline, p.anomaly_pct,
                              self._trend_of(indicator, p.value, p.baseline, p.anomaly_pct))
        text += self._year_coverage(p)
        self.series.append(ts)
        return self._add(indicator, "year", text, [sid, ds], date=year, has_value=True)

    def trend(self, indicator: str) -> list[dict]:
        """Évolution : moyenne 2001–2010 contre la dernière décennie complète (M16) + série annuelle (M15)."""
        lang, ds = self.lang, self._ds(catalog.dataset_for(indicator).id)
        y_last = last_complete_year(indicator, self.region_id)
        if y_last is None:
            return []
        out = []
        b_end = min(y_last, LST_TREND_LAST_YEAR) if indicator == "lst_day" else y_last
        u, dec = self._units(indicator), i18n.DECIMALS[indicator]
        try:
            c = indicators.compare(self.region_id, indicator, *FIRST_DECADE, f"{b_end - 9:04d}", f"{b_end:04d}")
        except ApiError:
            c = None
        if c is not None and c.period_a.mean is not None and c.period_b.mean is not None:
            label = catalog.LABELS[indicator]
            sa = self._computed(indicator, f"{c.period_a.start}/{c.period_a.end}",
                                f"{label} — {self.region.name} (moyenne {c.period_a.label})")
            sb = self._computed(indicator, f"{c.period_b.start}/{c.period_b.end}",
                                f"{label} — {self.region.name} (moyenne {c.period_b.label})")
            agg = {"fr": "cumul annuel moyen" if indicator == "precipitation" else "moyenne annuelle",
                   "en": "mean annual total" if indicator == "precipitation" else "annual mean"}[lang]
            a_v, b_v = i18n.num(c.period_a.mean, dec, lang), i18n.num(c.period_b.mean, dec, lang)
            delta = [f"{i18n.signed(c.delta_abs, dec, lang)}{u}"] if c.delta_abs is not None else []
            if c.delta_pct is not None and indicator != "lst_day":
                delta.append(pct(c.delta_pct, lang))
            pa, pb = c.period_a.label.replace("–", "-"), c.period_b.label.replace("–", "-")
            if lang == "fr":
                what = {"precipitation": "il tombait en moyenne", "ndvi": "l'indice de verdure (NDVI) était en moyenne de",
                        "lst_day": "la température du sol en journée était en moyenne de"}[indicator]
                per = " de pluie par an" if indicator == "precipitation" else ""
                text = (f"Dans la région {self.region.name}, {what} {a_v}{u}{per} sur {pa}, "
                        f"contre {b_v}{u} sur {pb}")
                text += f", soit un écart de {' ou '.join(delta)}." if delta else "."
            else:
                what = {"precipitation": "average yearly rainfall was", "ndvi": "the greenness index (NDVI) averaged",
                        "lst_day": "the daytime land surface temperature averaged"}[indicator]
                text = f"In the {self.region.name} region, {what} {a_v}{u} over {pa}, versus {b_v}{u} over {pb}"
                text += f", a difference of {' or '.join(delta)}." if delta else "."
            out.append(self._add(indicator, "trend", text, [sa, sb, ds], date=f"{c.period_b.start}/{c.period_b.end}",
                                 has_value=True))
        # Série annuelle complète (graphe) et dernière année complète
        g_first = store.first_date()
        ts = indicators.timeseries(self.region_id, indicator, g_first, f"{y_last:04d}-12", "year")
        self.series.append(ts)
        p = next((p for p in reversed(ts.points) if p.value is not None), None)
        if p is not None:
            agg = {"fr": "cumul" if indicator == "precipitation" else "moyenne",
                   "en": "total" if indicator == "precipitation" else "mean"}[lang]
            sid = self._computed(indicator, p.date, f"{catalog.LABELS[indicator]} — {self.region.name} ({p.date})")
            normal = self._normal_part(indicator, p.baseline, p.anomaly_pct)
            body = self._body(indicator, p.value, yearly=True)
            text = (f"En {p.date}, dernière année complète, {body}." if lang == "fr"
                    else f"In {p.date}, the latest complete year, {body}.")
            text += self._compare(indicator, p.baseline, p.anomaly_pct,
                                  self._trend_of(indicator, p.value, p.baseline, p.anomaly_pct))
            text += self._year_coverage(p)
            out.append(self._add(indicator, "year", text, [sid, ds], date=p.date, has_value=True))
        return out

    def _year_coverage(self, p) -> str:
        """Mention de faible couverture d'un point annuel (au moins un mois agrégé peu fiable)."""
        if not p.low_coverage:
            return ""
        pct = (f" (certains mois, seulement {round(p.valid_frac * 100)} % de la région était visible)"
               if p.valid_frac is not None else "")
        pct_en = (f" (some months, only {round(p.valid_frac * 100)}% of the region was visible)"
                  if p.valid_frac is not None else "")
        return (f" Attention, cette valeur est peu fiable : les nuages ont caché une grande partie de la région au moins "
                f"un mois de l'année{pct}." if self.lang == "fr"
                else f" Note that this value is uncertain: clouds hid much of the region at least one month of the "
                     f"year{pct_en}.")

    def _range_items(self, indicator: str, points, label) -> str:
        lang, u, dec = self.lang, self._units(indicator), i18n.DECIMALS[indicator]
        items = []
        for p in points:
            if p.value is None:
                items.append(f"{label(p.date)} : pas de donnée" if lang == "fr" else f"{label(p.date)}: no data")
                continue
            v = f"{i18n.num(p.value, dec, lang)}{u}"
            if p.anomaly_pct is not None and indicator != "lst_day":
                v += f" ({'écart' if lang == 'fr' else 'anomaly'} {pct(p.anomaly_pct, lang)})"
            if p.low_coverage:
                v += " (peu fiable, nuages)" if lang == "fr" else " (low confidence, clouds)"
            items.append(f"{label(p.date)} : {v}" if lang == "fr" else f"{label(p.date)}: {v}")
        if len(items) > 12:
            items = items[:3] + ["…"] + items[-3:]
        return " ; ".join(items) if lang == "fr" else "; ".join(items)

    def _range(self, indicator: str, start: str, end: str, granularity: str) -> Optional[dict]:
        """Série d'une plage (M15) : chaque mois / année de la plage, daté, dans un seul fait."""
        lang, noun, ds = self.lang, i18n.noun(indicator, self.lang), self._ds(catalog.dataset_for(indicator).id)
        g_first, g_last = store.first_date(), store.last_date()
        s = start if granularity == "month" else f"{start}-01"
        e = end if granularity == "month" else f"{end}-12"
        s, e = max(s, g_first), min(e, g_last)
        label = (lambda d: i18n.month_label(d, lang)) if granularity == "month" else (lambda d: d)
        if s > e:
            text = (f"Pas de donnée de {noun} entre {label(start)} et {label(end)} : les données couvrent "
                    f"{i18n.month_label(g_first, lang)} – {i18n.month_label(g_last, lang)}." if lang == "fr" else
                    f"No {noun} data between {label(start)} and {label(end)}: the data cover "
                    f"{i18n.month_label(g_first, lang)} – {i18n.month_label(g_last, lang)}.")
            return self._add(indicator, "out_of_range", text, [ds], date=f"{start}/{end}")
        ts = indicators.timeseries(self.region_id, indicator, s, e, granularity)
        self.series.append(ts)
        first, last = ts.points[0].date, ts.points[-1].date
        sid = self._computed(indicator, f"{first}/{last}",
                             f"{catalog.LABELS[indicator]} — {self.region.name} ({first} → {last})")
        agg = "" if granularity == "month" else (
            {"fr": " (cumuls annuels)", "en": " (annual totals)"} if indicator == "precipitation" else
            {"fr": " (moyennes annuelles)", "en": " (annual means)"})[lang]
        head = (f"{i18n.name(indicator, lang)}, {i18n.region_phrase(self.region.name, lang)}, de {label(first)} à "
                f"{label(last)}{agg} : " if lang == "fr" else
                f"{i18n.name(indicator, lang)}, {self.region.name} region, {label(first)} to {label(last)}{agg}: ")
        has_value = any(p.value is not None for p in ts.points)
        return self._add(indicator, "range", head + self._range_items(indicator, ts.points, label) + ".",
                         [sid, ds], date=f"{first}/{last}", has_value=has_value)

    def month_range(self, indicator: str, start: str, end: str) -> Optional[dict]:
        return self._range(indicator, start, end, "month")

    def year_range(self, indicator: str, start: str, end: str) -> Optional[dict]:
        return self._range(indicator, start, end, "year")

    def elevation(self) -> Optional[dict]:
        try:
            e = store.static()["regions"][self.region_id]["elevation"]
        except (KeyError, store.DataUnavailable):
            return None
        lang = self.lang
        ds = self._ds("srtm")
        sid = self._computed("elevation", "static", f"Altitude — {self.region.name}")
        n = lambda x: i18n.num(x, 1, lang)  # noqa: E731
        if lang == "fr":
            text = (f"La région {self.region.name} a une altitude moyenne de {n(e['mean'])} m (médiane "
                    f"{n(e['median'])} m). Un dixième de son territoire est sous {n(e['p10'])} m et le point le "
                    f"plus haut atteint {n(e['max'])} m, d'après le relief mesuré par la NASA (NASADEM).")
        else:
            text = (f"The {self.region.name} region has a mean elevation of {n(e['mean'])} m (median "
                    f"{n(e['median'])} m). A tenth of its land lies below {n(e['p10'])} m and the highest point "
                    f"reaches {n(e['max'])} m, according to NASA's terrain data (NASADEM).")
        return self._add("elevation", "elevation", text, [sid, ds], date="static", has_value=True)

    def recency_text(self) -> Optional[str]:
        """« À noter : les mesures les plus récentes datent de septembre 2025 pour la pluie et d'octobre 2026
        pour la végétation. » Seulement si plusieurs indicateurs s'arrêtent à des mois différents."""
        if len(set(self.latest_dates.values())) < 2:
            return None
        fr = self.lang == "fr"
        art = {"precipitation": "la pluie", "ndvi": "la végétation", "lst_day": "la température du sol"}
        items = []
        for i, d in self.latest_dates.items():
            m = i18n.month_label(d, self.lang)
            if fr:
                de = "d'" if m[0] in "aeiouéèêàâîôûAEIOU" else "de "
                items.append(f"{de}{m} pour {art.get(i, i18n.noun(i, self.lang))}")
            else:
                items.append(f"{m} for {i18n.noun(i, self.lang)}")
        joined = (", ".join(items[:-1]) + (" et " if fr else " and ") + items[-1]) if len(items) > 1 else items[0]
        return i18n.t("latest", self.lang, items=joined)

    def dump(self) -> dict:
        return {"facts": self.facts, "sources": [s.model_dump() for s in self.sources.values()],
                "snapshots": [s.model_dump() for s in self.snapshots],
                "series": [s.model_dump() for s in self.series]}
