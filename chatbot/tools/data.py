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
BASE_LABEL = "2001–2020"
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
            return (f" Valeur peu fiable : seulement {pct} % de la région visible (nuages)." if self.lang == "fr"
                    else f" Low-confidence value: only {pct}% of the region was visible (clouds).")
        if self.style == "scientific":
            return (f" Part de la région visible : {pct} %." if self.lang == "fr"
                    else f" Share of the region visible: {pct}%.")
        return ""

    def value_text(self, s: IndicatorSnapshot) -> str:
        lang, ind = self.lang, s.indicator
        when = i18n.month_label(s.date, lang)
        head = (f"{i18n.name(ind, lang)} en {when}, {i18n.region_phrase(self.region.name, lang)} : "
                if lang == "fr" else f"{i18n.name(ind, lang)} in {when}, {self.region.name} region: ")
        text = head + f"{i18n.num(s.value, i18n.DECIMALS[ind], lang)}{self._units(ind)}"
        normal = self._normal_part(ind, s.baseline, s.anomaly_pct)
        if normal:
            trend = TREND_WORDS[lang].get(s.trend)
            ref = trend.format(p=BASE_LABEL) if trend else (
                f"normale {BASE_LABEL}" if lang == "fr" else f"{BASE_LABEL} normal")
            text += f", {ref} ({normal})"
        return text + "." + self._coverage(s.valid_frac, s.low_coverage)

    # ── faits ──
    def _snapshot(self, indicator: str, date: str) -> IndicatorSnapshot:
        return indicators.snapshot(self.region_id, indicator, date, self.mode)

    def _value_fact(self, s: IndicatorSnapshot, kind: str, prefix: str = "") -> dict:
        ds = self._ds(s.dataset_id)
        sid = self._computed(s.indicator, s.date, f"{s.label} — {self.region.name} ({s.date})")
        text = self.value_text(s)
        if prefix:
            text = prefix + text[0].lower() + text[1:]
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
        prefix = "" if before is None else ("Dernière valeur disponible — " if self.lang == "fr"
                                            else "Latest available value — ")
        return self._value_fact(self._snapshot(indicator, last), "latest", prefix)

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
            text = (f"Les données de {noun} commencent en {i18n.month_label(first, lang)} : rien pour {when}."
                    if lang == "fr" else
                    f"{noun.capitalize()} data start in {i18n.month_label(first, lang)}: nothing for {when}.")
            return self._add(indicator, "out_of_range", text, [ds], date=date)
        s = self._snapshot(indicator, date)
        if s.value is not None:
            return self._value_fact(s, "value")
        stops = last is not None and last < date
        if lang == "fr":
            text = f"Pas de donnée satellite de {noun} pour {when} dans la {i18n.region_phrase(self.region.name, lang)}"
            text += f" : la série s'arrête en {i18n.month_label(last, lang)}." if stops else " (mois sans mesure)."
        else:
            text = f"No {noun} satellite data for {when} in the {self.region.name} region"
            text += f": the series ends in {i18n.month_label(last, lang)}." if stops else " (month without measurement)."
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
        u, dec = self._units(indicator), i18n.DECIMALS[indicator]
        sid = self._computed(indicator, year, f"{catalog.LABELS[indicator]} — {self.region.name} ({year})")
        text = (f"{i18n.name(indicator, lang)} en {year}, {i18n.region_phrase(self.region.name, lang)} : {agg} "
                if lang == "fr" else f"{i18n.name(indicator, lang)} in {year}, {self.region.name} region: {agg} ")
        text += f"{i18n.num(p.value, dec, lang)}{u}"
        normal = self._normal_part(indicator, p.baseline, p.anomaly_pct)
        if normal:
            text += (f" (normale {BASE_LABEL} : {normal})" if lang == "fr" else f" ({BASE_LABEL} normal: {normal})")
        text += "." + self._year_coverage(p)
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
            if lang == "fr":
                text = (f"{i18n.name(indicator, lang)}, {i18n.region_phrase(self.region.name, lang)} : {agg} "
                        f"{a_v}{u} sur {c.period_a.label} contre {b_v}{u} sur {c.period_b.label}")
                text += f" (écart {', '.join(delta)})." if delta else "."
            else:
                text = (f"{i18n.name(indicator, lang)}, {self.region.name} region: {agg} {a_v}{u} over "
                        f"{c.period_a.label} versus {b_v}{u} over {c.period_b.label}")
                text += f" (difference {', '.join(delta)})." if delta else "."
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
            if lang == "fr":
                text = f"Dernière année complète, {p.date} : {agg} {i18n.num(p.value, dec, lang)}{u}"
                text += f" (normale {BASE_LABEL} : {normal})." if normal else "."
            else:
                text = f"Latest complete year, {p.date}: {agg} {i18n.num(p.value, dec, lang)}{u}"
                text += f" ({BASE_LABEL} normal: {normal})." if normal else "."
            text += self._year_coverage(p)
            out.append(self._add(indicator, "year", text, [sid, ds], date=p.date, has_value=True))
        return out

    def _year_coverage(self, p) -> str:
        """Mention de faible couverture d'un point annuel (au moins un mois agrégé peu fiable)."""
        if not p.low_coverage:
            return ""
        pct = f" (jusqu'à {round(p.valid_frac * 100)} % de la région visible)" if p.valid_frac is not None else ""
        pct_en = f" (as little as {round(p.valid_frac * 100)}% of the region visible)" if p.valid_frac is not None else ""
        return (f" Valeur peu fiable : au moins un mois de l'année est mal couvert{pct} (nuages)." if self.lang == "fr"
                else f" Low-confidence value: at least one month of the year is poorly covered{pct_en} (clouds).")

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
            text = (f"Altitude de la région {self.region.name} (NASADEM) : moyenne {n(e['mean'])} m, médiane "
                    f"{n(e['median'])} m, 10 % des points sous {n(e['p10'])} m, maximum {n(e['max'])} m.")
        else:
            text = (f"Elevation of the {self.region.name} region (NASADEM): mean {n(e['mean'])} m, median "
                    f"{n(e['median'])} m, 10% of points below {n(e['p10'])} m, maximum {n(e['max'])} m.")
        return self._add("elevation", "elevation", text, [sid, ds], date="static", has_value=True)

    def recency_text(self) -> Optional[str]:
        """« Données les plus récentes : pluie septembre 2025, végétation octobre 2026. »"""
        if not self.latest_dates:
            return None
        items = ", ".join(f"{i18n.noun(i, self.lang)} {i18n.month_label(d, self.lang)}"
                          for i, d in self.latest_dates.items())
        return i18n.t("latest", self.lang, items=items)

    def dump(self) -> dict:
        return {"facts": self.facts, "sources": [s.model_dump() for s in self.sources.values()],
                "snapshots": [s.model_dump() for s in self.snapshots],
                "series": [s.model_dump() for s in self.series]}
