"""Séries, résumés, comparaisons, avant/après, tableau de bord, agriculture (M14–M20).

Calculs sur le livrable P2 (backend.repositories.store), règles de MISSIONS.md (bloc 4) :
- normale   : moyenne 2001–2020 du même mois calendaire, même région, même indicateur ;
- anomalie  : (value − baseline) / baseline × 100, arrondie à 0,1 ; null si baseline nulle/absente ;
- tendance  : > +10 % above_normal, < −10 % below_normal, sinon normal ; température : écart
              > +1,5 / < −1,5 °C ; valeur absente → unknown ;
- arrondis  : pluie 1 décimale, NDVI 3, température 1.
Tout est déterministe : aucune valeur aléatoire, aucun appel externe.
"""
import math
import re
from functools import lru_cache
from typing import Literal, Optional

from backend.core.constants import DISCLAIMER
from backend.core.exceptions import BadRequest
from backend.repositories import store
from backend.schemas import (AgriInsight, BeforeAfter, Comparison, Dashboard, Granularity,
                             IndicatorId, IndicatorSnapshot, LayerAtDate, Mode, PeriodStats,
                             RegionSummary, Statement, TimePoint, TimeSeries, Trend)

from .catalog import IND2DS, LABELS, dataset_for, get_layer
from .regions import NORTH, REGION_IDS, get_region

TS_INDICATORS = ("precipitation", "ndvi", "lst_day")
DECIMALS = {"precipitation": 1, "ndvi": 3, "lst_day": 1}
BASELINE = (2001, 2020)
ANOMALY_PCT = 10.0       # seuil des tendances en %
LST_DELTA = 1.5          # seuil des tendances de température, en °C
MIN_MONTHS_YEAR = 10     # NDVI / LST : année valide si ≥ 10 mois sur 12 (pluie : 12/12)

MONTHS_FR = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
             "septembre", "octobre", "novembre", "décembre")
MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
YEAR_RE = re.compile(r"^\d{4}$")
DAY_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")


# ─────────── Outils ───────────
def _invalid(message: str) -> BadRequest:
    return BadRequest("invalid_period", message)


def _check_month(value: str, name: str) -> str:
    if not MONTH_RE.match(value or ""):
        raise _invalid(f"{name} doit être au format YYYY-MM (reçu : {value})")
    return value


def _check_ts_indicator(indicator: str) -> None:
    if indicator not in TS_INDICATORS:
        raise BadRequest("no_timeseries", f"Pas de série temporelle pour l'indicateur {indicator}")


def _round(indicator: str, x: Optional[float]) -> Optional[float]:
    return None if x is None else round(x, DECIMALS[indicator])


def _months(start: str, end: str) -> list[str]:
    y, m = map(int, start.split("-"))
    ye, me = map(int, end.split("-"))
    out = []
    while (y, m) <= (ye, me):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def _month_label(date: str) -> str:
    y, m = date.split("-")[:2]
    return f"{MONTHS_FR[int(m) - 1]} {y}"


def _fr(x: float, decimals: int) -> str:
    return f"{x:.{decimals}f}".replace(".", ",")


@lru_cache(maxsize=None)
def baseline(region_id: str, indicator: str, month: int) -> Optional[float]:
    """Normale 2001–2020 du mois calendaire (moyenne des valeurs non nulles)."""
    vals = [o.value for d, o in store.series(region_id, indicator).items()
            if int(d[5:7]) == month and BASELINE[0] <= int(d[:4]) <= BASELINE[1] and o.value is not None]
    return _round(indicator, sum(vals) / len(vals)) if vals else None


def _anomaly_pct(value: Optional[float], base: Optional[float]) -> Optional[float]:
    if value is None or not base:
        return None
    return round((value - base) / base * 100, 1)


def _trend(indicator: str, value: Optional[float], base: Optional[float], anomaly: Optional[float]) -> Trend:
    if value is None or base is None:
        return "unknown"
    if indicator == "lst_day":
        d = value - base
        return "above_normal" if d > LST_DELTA else "below_normal" if d < -LST_DELTA else "normal"
    if anomaly is None:
        return "unknown"
    return "above_normal" if anomaly > ANOMALY_PCT else "below_normal" if anomaly < -ANOMALY_PCT else "normal"


# ─────────── M14 · Résumé régional ───────────
def _plain_summary(indicator: str, value, base, anomaly, trend: Trend, date: str, mode: Mode,
                   valid_frac: Optional[float], low_coverage: bool) -> str:
    label, units = LABELS[indicator], dataset_for(indicator).units
    if value is None:
        return f"{label} : pas de donnée satellite pour {_month_label(date)}."
    dec = DECIMALS[indicator]
    if mode == "scientific":
        u = f" {units}" if units else ""
        text = f"{label} ({_month_label(date)}) : {_fr(value, dec)}{u}"
        if base is not None:
            text += f", normale 2001–2020 : {_fr(base, dec)}{u}"
            text += (f", écart {_fr(value - base, 1)} °C" if indicator == "lst_day"
                     else f", écart {anomaly:+.1f} %".replace(".", ",") if anomaly is not None else "")
        text += "."
    elif trend == "unknown":
        text = f"{label} : pas de normale disponible pour comparer."
    elif trend == "normal":
        text = f"{label} : proche de la normale."
    else:
        side = "au-dessus" if trend == "above_normal" else "en dessous"
        gap = (f"{_fr(abs(value - base), 1)} °C" if indicator == "lst_day" else f"{abs(round(anomaly))} %")
        text = f"{label} : {gap} {side} de la normale."
    if low_coverage and valid_frac is not None:
        text += f" Valeur peu fiable : seulement {round(valid_frac * 100)} % de la région visible (nuages)."
    return text


def snapshot(region_id: str, indicator: str, date: str, mode: Mode = "public",
             fallback: bool = False) -> IndicatorSnapshot:
    """Valeur d'un indicateur pour un mois. `fallback` : si le mois manque, dernier mois disponible avant."""
    obs = store.observation(region_id, indicator, date)
    if fallback and (obs is None or obs.value is None):
        last = store.last_date(indicator, region_id)
        if last is not None and last <= date:
            date, obs = last, store.observation(region_id, indicator, last)
    value = obs.value if obs else None
    base = baseline(region_id, indicator, int(date[5:7]))
    anomaly = _anomaly_pct(value, base)
    trend = _trend(indicator, value, base, anomaly)
    valid_frac = obs.valid_frac if obs else None
    low = bool(obs and obs.low_coverage)
    return IndicatorSnapshot(
        indicator=indicator, label=LABELS[indicator], value=value, units=dataset_for(indicator).units,
        date=date, baseline=base, anomaly_pct=anomaly, trend=trend,
        plain_summary=_plain_summary(indicator, value, base, anomaly, trend, date, mode, valid_frac, low),
        dataset_id=IND2DS[indicator], valid_frac=valid_frac, low_coverage=low)


def summary(region_id: str, date: Optional[str] = None, mode: Mode = "public") -> RegionSummary:
    region = get_region(region_id)
    fallback = date is None
    date = store.last_date() if date is None else _check_month(date, "date")
    snaps = [snapshot(region_id, ind, date, mode, fallback=fallback) for ind in TS_INDICATORS]
    return RegionSummary(region=region, date=date, indicators=snaps)


# ─────────── M15 · Série temporelle ───────────
def _annual(region_id: str, indicator: str, months: list[str]) -> tuple[Optional[float], Optional[float]]:
    """(valeur, normale) agrégées sur des mois d'une même année : cumul pour la pluie, moyenne sinon."""
    vals = [o.value for o in (store.observation(region_id, indicator, d) for d in months) if o and o.value is not None]
    bases = [baseline(region_id, indicator, int(d[5:7])) for d in months]
    if indicator == "precipitation":
        value = sum(vals) if len(vals) == len(months) else None
        base = sum(bases) if None not in bases else None
    else:
        need = max(1, math.ceil(len(months) * MIN_MONTHS_YEAR / 12))
        value = sum(vals) / len(vals) if len(vals) >= need else None
        known = [b for b in bases if b is not None]
        base = sum(known) / len(known) if known else None
    return _round(indicator, value), _round(indicator, base)


def timeseries(region_id: str, indicator: IndicatorId, start: Optional[str] = None, end: Optional[str] = None,
               granularity: Granularity = "month") -> TimeSeries:
    get_region(region_id)
    _check_ts_indicator(indicator)
    end = _check_month(end, "end") if end else (store.last_date(indicator, region_id) or store.last_date())
    start = _check_month(start, "start") if start else f"{int(end[:4]) - 5:04d}-01"
    if start > end:
        raise _invalid(f"Début ({start}) après la fin ({end})")
    months = _months(start, end)
    points: list[TimePoint] = []
    if granularity == "month":
        for d in months:
            obs = store.observation(region_id, indicator, d)
            value = obs.value if obs else None
            base = baseline(region_id, indicator, int(d[5:7]))
            points.append(TimePoint(date=d, value=value, baseline=base, anomaly_pct=_anomaly_pct(value, base),
                                    valid_frac=obs.valid_frac if obs else None,
                                    low_coverage=bool(obs and obs.low_coverage)))
    else:
        for year in sorted({d[:4] for d in months}):
            value, base = _annual(region_id, indicator, [d for d in months if d[:4] == year])
            points.append(TimePoint(date=year, value=value, baseline=base, anomaly_pct=_anomaly_pct(value, base)))
    return TimeSeries(region_id=region_id, indicator=indicator, units=dataset_for(indicator).units,
                      granularity=granularity, points=points, dataset_id=IND2DS[indicator])


# ─────────── M16 · Comparaison de périodes ───────────
def _year_value(region_id: str, indicator: str, year: int) -> Optional[float]:
    return _annual(region_id, indicator, _months(f"{year:04d}-01", f"{year:04d}-12"))[0]


def _period(region_id: str, indicator: str, start: str, end: str) -> PeriodStats:
    vals = [v for v in (_year_value(region_id, indicator, y) for y in range(int(start), int(end) + 1))
            if v is not None]
    if not vals:
        raise _invalid(f"Aucune année complète de données entre {start} et {end}")
    return PeriodStats(label=f"{start}–{end}", start=start, end=end, mean=_round(indicator, sum(vals) / len(vals)),
                       min=_round(indicator, min(vals)), max=_round(indicator, max(vals)))


def compare(region_id: str, indicator: IndicatorId, a_start: str, a_end: str,
            b_start: str, b_end: str) -> Comparison:
    get_region(region_id)
    _check_ts_indicator(indicator)
    for name, v in (("a_start", a_start), ("a_end", a_end), ("b_start", b_start), ("b_end", b_end)):
        if not YEAR_RE.match(v or ""):
            raise _invalid(f"{name} doit être une année YYYY (reçu : {v})")
    if a_start > a_end or b_start > b_end:
        raise _invalid("Chaque période doit avoir un début avant sa fin")
    first, last = store.first_date(indicator), store.last_date(indicator)
    if first is None or min(a_start, b_start) < first[:4] or max(a_end, b_end) > last[:4]:
        raise _invalid(f"Période hors des données disponibles ({first[:4] if first else '?'}–{last[:4] if last else '?'})")
    a = _period(region_id, indicator, a_start, a_end)
    b = _period(region_id, indicator, b_start, b_end)
    delta_abs = _round(indicator, b.mean - a.mean)
    delta_pct = round(delta_abs / a.mean * 100, 1) if a.mean else None
    return Comparison(region_id=region_id, indicator=indicator, units=dataset_for(indicator).units,
                      period_a=a, period_b=b, delta_abs=delta_abs, delta_pct=delta_pct,
                      dataset_id=IND2DS[indicator])


# ─────────── M17 · Export ───────────
def export_timeseries(region_id: str, indicator: IndicatorId, start: Optional[str] = None,
                      end: Optional[str] = None, format: Literal["csv", "json"] = "csv") -> tuple[str, str, str]:
    """Renvoie (contenu, media_type, nom_de_fichier)."""
    ts = timeseries(region_id, indicator, start, end)
    ds = dataset_for(indicator)
    start, end = ts.points[0].date, ts.points[-1].date
    fname = f"agbea_{region_id}_{indicator}_{start}_{end}.{format}"
    if format == "json":
        return ts.model_dump_json(indent=2), "application/json", fname
    cell = lambda x: "" if x is None else str(x)  # noqa: E731
    lines = [f"# source: {ds.name} ({ds.source_url})", f"# units: {ds.units}",
             "date,value,baseline,anomaly_pct"]
    lines += [f"{p.date},{cell(p.value)},{cell(p.baseline)},{cell(p.anomaly_pct)}" for p in ts.points]
    return "\n".join(lines) + "\n", "text/csv", fname


# ─────────── M18 · Avant / après ───────────
def before_after(layer_id: str, before: str, after: str, region_id: Optional[str] = None) -> BeforeAfter:
    layer = get_layer(layer_id)
    for name, v in (("before", before), ("after", after)):
        if not DAY_RE.match(v or ""):
            raise _invalid(f"{name} doit être au format YYYY-MM-DD (reçu : {v})")
    comp = None
    if region_id:
        get_region(region_id)
        try:
            comp = compare(region_id, layer.indicator, before[:4], before[:4], after[:4], after[:4])
        except BadRequest:
            comp = None  # année incomplète ou hors données : on montre les cartes sans chiffres
    return BeforeAfter(layer_id=layer_id,
                       before=LayerAtDate(date=before, url_template=layer.url_template.replace("{date}", before)),
                       after=LayerAtDate(date=after, url_template=layer.url_template.replace("{date}", after)),
                       comparison=comp)


# ─────────── M19 · Tableau de bord ───────────
def _highlight(region_name: str, s: IndicatorSnapshot) -> Statement:
    side = "au-dessus" if (s.value or 0) > (s.baseline or 0) else "en dessous"
    gap = (f"{_fr(abs(s.value - s.baseline), 1)} °C" if s.indicator == "lst_day" else f"{abs(round(s.anomaly_pct))} %")
    text = f"{region_name} : {s.label.lower()} {gap} {side} de la normale en {_month_label(s.date)}."
    if s.low_coverage:
        text += " Valeur peu fiable (nuages)."
    return Statement(text=text, nature="observed", source_ids=[f"ds:{s.dataset_id}"])


def dashboard(date: Optional[str] = None) -> Dashboard:
    summaries = [summary(rid, date) for rid in REGION_IDS]
    date = summaries[0].date
    candidates = [(s.region.name, snap) for s in summaries for snap in s.indicators
                  if snap.anomaly_pct is not None and snap.trend != "unknown"]

    def strength(s: IndicatorSnapshot) -> float:
        """Écart rapporté à son seuil de tendance (1 = seuil) : compare pluie, NDVI et température."""
        if s.indicator == "lst_day":
            return abs(s.value - s.baseline) / LST_DELTA
        return abs(s.anomaly_pct) / ANOMALY_PCT

    # Plus grandes anomalies ; valeurs fiables (couverture ≥ 50 %) d'abord
    candidates.sort(key=lambda c: (c[1].low_coverage, -strength(c[1])))
    return Dashboard(date=date, regions=summaries, highlights=[_highlight(n, s) for n, s in candidates[:3]])


# ─────────── M20 · Agriculture ───────────
# Sud (maritime, plateaux) : deux saisons des pluies (avril–juillet, septembre–octobre) ;
# nord (centrale, kara, savanes) : une saison (mai–octobre). Mois de bascule → transition.
SEASONS = {
    "south": {"rainy": {4, 5, 6, 7, 9, 10}, "transition": {3, 8, 11}},
    "north": {"rainy": {5, 6, 7, 8, 9, 10}, "transition": {4, 11}},
}


def season(region_id: str, month: int) -> Literal["dry", "rainy", "transition"]:
    zone = SEASONS["north" if region_id in NORTH else "south"]
    return "rainy" if month in zone["rainy"] else "transition" if month in zone["transition"] else "dry"


def _advice(seas: str, rain: IndicatorSnapshot, veg: IndicatorSnapshot) -> list[Statement]:
    rain_src, veg_src = [f"ds:{rain.dataset_id}"], [f"ds:{veg.dataset_id}"]
    out: list[Statement] = []
    if seas == "rainy" and rain.trend == "below_normal":
        out.append(Statement(text="Pluie plus faible que d'habitude en saison des pluies : surveillez l'humidité "
                                  "du sol avant de semer.", nature="interpreted", source_ids=rain_src))
    elif seas == "rainy" and rain.trend == "above_normal":
        out.append(Statement(text="Pluie plus forte que d'habitude : surveillez l'eau stagnante dans les champs "
                                  "bas et l'érosion des sols en pente.", nature="interpreted", source_ids=rain_src))
    elif seas == "transition":
        out.append(Statement(text="Mois de bascule entre saisons : suivez l'arrivée ou l'arrêt des pluies avant "
                                  "de planifier semis ou récoltes.", nature="interpreted", source_ids=rain_src))
    if veg.trend == "below_normal":
        out.append(Statement(text="La végétation est moins verte que d'habitude : vérifiez l'état des cultures "
                                  "et des pâturages.", nature="interpreted", source_ids=veg_src))
    if not out:
        text = ("Pluie et végétation proches de l'habitude pour la saison : pas de signal particulier."
                if seas != "dry" else "Saison sèche : les observations satellites varient peu, l'arrosage et la "
                                      "conservation de l'eau restent prioritaires.")
        out.append(Statement(text=text, nature="interpreted", source_ids=rain_src + veg_src))
    return out[:2]


def agriculture(region_id: str, date: Optional[str] = None) -> AgriInsight:
    s = summary(region_id, date)
    by = {i.indicator: i for i in s.indicators}
    rain, veg = by["precipitation"], by["ndvi"]
    seas = season(region_id, int(s.date[5:7]))
    observed = [Statement(text=x.plain_summary, nature="observed", source_ids=[f"ds:{x.dataset_id}"])
                for x in (rain, veg) if x.value is not None]
    return AgriInsight(region_id=region_id, date=s.date, season=seas,
                       rainfall_status=rain.trend, vegetation_status=veg.trend,
                       statements=observed + _advice(seas, rain, veg), disclaimer=DISCLAIMER)
