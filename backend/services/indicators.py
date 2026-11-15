"""Séries, résumés, comparaisons, avant/après, tableau de bord, agriculture (M14–M20).

Calculs sur le livrable P2 (backend.repositories.store), règles de MISSIONS.md (bloc 4) :
- normale   : moyenne 2001–2020 du même mois calendaire, même région, même indicateur ;
- anomalie  : (value − baseline) / baseline × 100, arrondie à 0,1 ; null si baseline nulle/absente ;
- tendance  : > +10 % above_normal, < −10 % below_normal, sinon normal ; température : écart
              > +1,5 / < −1,5 °C ; valeur absente → unknown ;
- arrondis  : pluie 1 décimale, NDVI 3, température 1, anomalie % 1.
Précision : sommes exactes (math.fsum) ; normales, agrégats annuels, moyennes de période, anomalies
et deltas sont calculés en PLEINE précision ; on n'arrondit qu'à la sortie (champs renvoyés, textes),
« moitié vers le haut » (voir _rnd).
Tendance : elle se lit sur l'écart AFFICHÉ, pour que texte, chiffres et tendance concordent :
anomalie % arrondie à 0,1 (pluie, NDVI) ; écart de température = valeur − normale affichée, à 0,1 °C.
Ex. : anomalie affichée +10,0 % → normal ; +10,1 % → above_normal.
Période des données : du premier au dernier mois présent dans monthly.parquet, toutes séries
confondues (store.first_date() → store.last_date()). Les séries s'arrêtent à des mois différents
(pluie IMERG Final publiée avec retard, température du sol arrêtée en 2022-12 : décision D30).
Tout est déterministe : aucune valeur aléatoire, aucun appel externe.
"""
import bisect
import datetime as dt
import math
import re
from collections import Counter
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
from typing import Literal, Optional

from backend.core.constants import DISCLAIMER
from backend.core.exceptions import BadRequest
from backend.repositories import store
from backend.schemas import (AgriInsight, BeforeAfter, Comparison, Dashboard, Granularity,
                             IndicatorId, IndicatorSnapshot, LayerAtDate, MapLayer, Mode, PeriodStats,
                             RegionSummary, Statement, TimePoint, TimeSeries, Trend)

from .catalog import IND2DS, LABELS, dataset_for, get_layer
from .regions import NORTH, REGION_IDS, get_region

TS_INDICATORS = ("precipitation", "ndvi", "lst_day")
DECIMALS = {"precipitation": 1, "ndvi": 3, "lst_day": 1}
BASELINE = (2001, 2020)
ANOMALY_PCT = 10.0       # seuil des tendances en %
LST_DELTA = 1.5          # seuil des tendances de température, en °C
# Série annuelle (granularité year) : pluie = cumul des 12 mois (un cumul partiel sous-estimerait
# l'année) ; NDVI / température = moyenne d'au moins 10 mois (trous de nuages), la normale étant
# calculée sur les mêmes mois. L'année partielle est signalée par TimePoint.months_count < 12.
# Comparaisons (compare, before-after) : seules les années ENTIÈRES (12 mois) comptent, pour tous les
# indicateurs (une année partielle n'est pas comparable à une année entière).
MIN_MONTHS_YEAR = 10
# before-after : si une des deux années est incomplète, comparaison sur les mois communs aux deux
# années, à condition d'en avoir au moins la moitié.
MIN_COMMON_MONTHS = 6

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


def _data_range() -> tuple[str, str]:
    """(premier mois, dernier mois) des données, toutes séries confondues."""
    first, last = store.first_date(), store.last_date()
    if first is None or last is None:
        raise store.DataUnavailable("data_unavailable", "monthly.parquet ne contient aucune valeur")
    return first, last


def _check_in_data(value: str, name: str) -> str:
    """Un mois demandé doit être dans la période des données (sinon tout serait null)."""
    first, last = _data_range()
    if not first <= value <= last:
        raise _invalid(f"{name} ({value}) hors de la période des données ({first} → {last})")
    return value


def _check_ts_indicator(indicator: str) -> None:
    if indicator not in TS_INDICATORS:
        raise BadRequest("no_timeseries", f"Pas de série temporelle pour l'indicateur {indicator}")


def _rnd(x: float, decimals: int) -> float:
    """Arrondi d'affichage « moitié vers le haut » (en valeur absolue : 27,95 → 28,0 ; −2,15 → −2,2).

    Le résultat flottant est d'abord ramené à 10 décimales, ce qui efface les résidus binaires des
    opérations (25,8 − 27,95 = −2,1499999999999986 → −2,15 ; 0,7314999… → 0,7315) : les valeurs du
    parquet ont au plus 3 décimales, donc aucune vraie décimale n'est perdue. −0,0 devient 0,0."""
    d = Decimal(repr(round(float(x), 10))).quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)
    return float(d) + 0.0


def _round(indicator: str, x: Optional[float]) -> Optional[float]:
    return None if x is None else _rnd(x, DECIMALS[indicator])


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
    return f"{x + 0.0:.{decimals}f}".replace(".", ",")


def _signed(x: float, decimals: int = 1) -> str:
    """« +1,2 », « −0,4 », et « 0,0 » sans signe pour un écart nul."""
    x = _rnd(x, decimals)
    return _fr(0.0, decimals) if x == 0 else f"{x:+.{decimals}f}".replace(".", ",")


def _half_up(x: float) -> int:
    return int(_rnd(abs(x), 0))


@lru_cache(maxsize=None)
def _baseline_raw(region_id: str, indicator: str, month: int) -> Optional[float]:
    """Normale 2001–2020 du mois calendaire, pleine précision (moyenne des valeurs non nulles)."""
    vals = [o.value for d, o in store.series(region_id, indicator).items()
            if int(d[5:7]) == month and BASELINE[0] <= int(d[:4]) <= BASELINE[1] and o.value is not None]
    return math.fsum(vals) / len(vals) if vals else None


def baseline(region_id: str, indicator: str, month: int) -> Optional[float]:
    """Normale 2001–2020 du mois calendaire, arrondie pour l'affichage."""
    return _round(indicator, _baseline_raw(region_id, indicator, month))


def _anomaly_pct(value: Optional[float], base: Optional[float]) -> Optional[float]:
    """Anomalie en %, calculée sur les valeurs pleine précision, arrondie à 0,1."""
    if value is None or not base:
        return None
    return _rnd((value - base) / base * 100, 1)


def _gap(value: Optional[float], base: Optional[float]) -> Optional[float]:
    """Écart de température affiché, en °C : valeur − normale AFFICHÉE (à 0,1 °C). Les valeurs LST du
    parquet sont déjà à 0,1 °C : l'écart se vérifie à partir des deux nombres affichés, et c'est le même
    partout (résumé, tableau de bord)."""
    return None if value is None or base is None else _rnd(value - _rnd(base, 1), 1)


def _trend(indicator: str, value: Optional[float], base: Optional[float], anomaly: Optional[float]) -> Trend:
    """Tendance lue sur l'écart affiché (anomalie à 0,1 % ; écart de température à 0,1 °C)."""
    if value is None or base is None:
        return "unknown"
    if indicator == "lst_day":
        d = _gap(value, base)
        return "above_normal" if d > LST_DELTA else "below_normal" if d < -LST_DELTA else "normal"
    if anomaly is None:
        return "unknown"
    return "above_normal" if anomaly > ANOMALY_PCT else "below_normal" if anomaly < -ANOMALY_PCT else "normal"


# ─────────── M14 · Résumé régional ───────────
def _plain_summary(indicator: str, value, base, anomaly, trend: Trend, date: str, mode: Mode,
                   valid_frac: Optional[float], low_coverage: bool, stale: bool = False,
                   last: Optional[str] = None) -> str:
    """Phrase gabarit. `stale` : la valeur vient d'un mois antérieur au mois demandé (repli) → le mois
    est toujours écrit. `last` : dernier mois disponible, cité quand la valeur manque."""
    label, units = LABELS[indicator], dataset_for(indicator).units
    month = _month_label(date)
    if value is None:
        text = f"{label} : pas de donnée satellite pour {month}"
        if last and last < date:
            text += f" (dernière donnée : {_month_label(last)})"
        return text + "."
    head = (f"{label} ({month}, dernier mois disponible)" if stale
            else f"{label} ({month})" if mode == "scientific" else label)
    dec = DECIMALS[indicator]
    if mode == "scientific":
        u = f" {units}" if units else ""
        text = f"{head} : {_fr(value, dec)}{u}"
        if base is not None:
            text += f", normale 2001–2020 : {_fr(_round(indicator, base), dec)}{u}"
            text += (f", écart {_signed(_gap(value, base))} °C" if indicator == "lst_day"
                     else f", écart {_signed(anomaly)} %" if anomaly is not None else "")
        text += "."
    elif trend == "unknown":
        text = f"{head} : pas de normale disponible pour comparer."
    elif trend == "normal":
        text = f"{head} : proche de la normale."
    else:
        side = "au-dessus" if trend == "above_normal" else "en dessous"
        gap = (f"{_fr(abs(_gap(value, base)), 1)} °C" if indicator == "lst_day" else f"{_half_up(anomaly)} %")
        text = f"{head} : {gap} {side} de la normale."
    if low_coverage and valid_frac is not None:
        text += f" Valeur peu fiable : seulement {round(valid_frac * 100)} % de la région visible (nuages)."
    return text


def snapshot(region_id: str, indicator: str, date: str, mode: Mode = "public",
             fallback: bool = False) -> IndicatorSnapshot:
    """Valeur d'un indicateur pour le mois `date`.

    `fallback` : si ce mois n'a pas de valeur, prend le dernier mois disponible AVANT `date`. Le
    snapshot garde alors sa date réelle (`snapshot.date` ≠ `date`) et `plain_summary` cite ce mois
    (« Pluie du mois (septembre 2025, dernier mois disponible) : … »). Sans `fallback` : valeur
    absente → value null, trend unknown, date demandée."""
    requested = date
    last = store.last_date(indicator, region_id)
    obs = store.observation(region_id, indicator, date)
    if fallback and (obs is None or obs.value is None) and last is not None and last < date:
        date, obs = last, store.observation(region_id, indicator, last)
    value = obs.value if obs else None
    base = _baseline_raw(region_id, indicator, int(date[5:7]))
    anomaly = _anomaly_pct(value, base)
    trend = _trend(indicator, value, base, anomaly)
    valid_frac = obs.valid_frac if obs else None
    low = bool(obs and obs.low_coverage)
    return IndicatorSnapshot(
        indicator=indicator, label=LABELS[indicator], value=value, units=dataset_for(indicator).units,
        date=date, baseline=_round(indicator, base), anomaly_pct=anomaly, trend=trend,
        plain_summary=_plain_summary(indicator, value, base, anomaly, trend, date, mode, valid_frac, low,
                                     stale=date != requested, last=last),
        dataset_id=IND2DS[indicator], valid_frac=valid_frac, low_coverage=low)


def summary(region_id: str, date: Optional[str] = None, mode: Mode = "public") -> RegionSummary:
    """Résumé d'une région pour un mois.

    Règle des dates :
    - `date` absente → `RegionSummary.date` = dernier mois des données toutes séries confondues ;
      un indicateur sans valeur ce mois-là se replie sur SON dernier mois disponible : son snapshot
      garde sa date réelle (≠ `RegionSummary.date`) et son `plain_summary` la cite ;
    - `date` fournie → pas de repli : valeur absente → value null, trend unknown, et le texte cite la
      dernière donnée disponible ; `date` hors de la période des données → 400 invalid_period.
    """
    region = get_region(region_id)
    fallback = date is None
    date = _data_range()[1] if date is None else _check_in_data(_check_month(date, "date"), "date")
    snaps = [snapshot(region_id, ind, date, mode, fallback=fallback) for ind in TS_INDICATORS]
    return RegionSummary(region=region, date=date, indicators=snaps)


# ─────────── M15 · Série temporelle ───────────
def _on_months(region_id: str, indicator: str, pairs: list) -> tuple[float, Optional[float]]:
    """(valeur, normale) pleine précision sur des mois (date, Obs) : cumul pour la pluie, moyenne sinon ;
    la normale est agrégée sur les MÊMES mois."""
    vals = [o.value for _, o in pairs]
    bases = [_baseline_raw(region_id, indicator, int(d[5:7])) for d, _ in pairs]
    if indicator == "precipitation":
        return math.fsum(vals), (None if None in bases else math.fsum(bases))
    return math.fsum(vals) / len(vals), (None if None in bases else math.fsum(bases) / len(bases))


def _pairs(region_id: str, indicator: str, months: list[str]) -> list:
    return [(d, o) for d in months if (o := store.observation(region_id, indicator, d)) and o.value is not None]


def _annual(region_id: str, indicator: str, months: list[str]
            ) -> tuple[Optional[float], Optional[float], Optional[float], bool, int]:
    """Agrégat d'une année sur ses mois `months` (ceux de l'année compris dans la plage demandée).

    Renvoie (valeur, normale, valid_frac, low_coverage, nombre de mois avec valeur), pleine précision :
    - pluie : cumul, seulement si les 12 mois de l'année ont une valeur ;
    - NDVI / température : moyenne, si au moins MIN_MONTHS_YEAR mois ont une valeur ;
    - normale : agrégée (cumul / moyenne) sur les MÊMES mois que la valeur ;
    - valid_frac : part visible du mois le moins couvert ; low_coverage : un des mois l'est.
    Année non valide → (None, None, None, False, n)."""
    pairs = _pairs(region_id, indicator, months)
    need = 12 if indicator == "precipitation" else MIN_MONTHS_YEAR
    if len(pairs) < need:
        return None, None, None, False, len(pairs)
    value, base = _on_months(region_id, indicator, pairs)
    fracs = [o.valid_frac for _, o in pairs if o.valid_frac is not None]
    return value, base, (min(fracs) if fracs else None), any(o.low_coverage for _, o in pairs), len(pairs)


def timeseries(region_id: str, indicator: IndicatorId, start: Optional[str] = None, end: Optional[str] = None,
               granularity: Granularity = "month") -> TimeSeries:
    """Série de `start` à `end` (mois contigus, mois sans donnée → value null).

    Bornes : `start` et `end` doivent être dans la période des données toutes séries confondues
    (sinon 400 invalid_period) : une série reste bornée (~310 mois) et ses trous sont réels.
    Granularité year : `months_count` = nombre de mois agrégés (< 12 : année partielle)."""
    get_region(region_id)
    _check_ts_indicator(indicator)
    end = _check_month(end, "end") if end else (store.last_date(indicator, region_id) or _data_range()[1])
    start = _check_month(start, "start") if start else f"{int(end[:4]) - 5:04d}-01"
    if start > end:
        raise _invalid(f"Début ({start}) après la fin ({end})")
    _check_in_data(start, "start")
    _check_in_data(end, "end")
    months = _months(start, end)
    points: list[TimePoint] = []
    if granularity == "month":
        for d in months:
            obs = store.observation(region_id, indicator, d)
            value = obs.value if obs else None
            base = _baseline_raw(region_id, indicator, int(d[5:7]))
            points.append(TimePoint(date=d, value=value, baseline=_round(indicator, base),
                                    anomaly_pct=_anomaly_pct(value, base),
                                    valid_frac=obs.valid_frac if obs else None,
                                    low_coverage=bool(obs and obs.low_coverage)))
    else:
        for year in sorted({d[:4] for d in months}):
            value, base, frac, low, n = _annual(region_id, indicator, [d for d in months if d[:4] == year])
            points.append(TimePoint(date=year, value=_round(indicator, value), baseline=_round(indicator, base),
                                    anomaly_pct=_anomaly_pct(value, base), valid_frac=frac, low_coverage=low,
                                    months_count=n))
    return TimeSeries(region_id=region_id, indicator=indicator, units=dataset_for(indicator).units,
                      granularity=granularity, points=points, dataset_id=IND2DS[indicator])


# ─────────── M16 · Comparaison de périodes ───────────
def _year_value(region_id: str, indicator: str, year: int) -> Optional[float]:
    """Valeur d'une année ENTIÈRE (12 mois avec valeur), pleine précision ; sinon None.
    Règle des comparaisons, la même pour les 3 indicateurs."""
    pairs = _pairs(region_id, indicator, _months(f"{year:04d}-01", f"{year:04d}-12"))
    return _on_months(region_id, indicator, pairs)[0] if len(pairs) == 12 else None


def _years_label(start: int, end: int) -> str:
    return f"{start:04d}" if start == end else f"{start:04d}–{end:04d}"


def _period(region_id: str, indicator: str, start: str, end: str) -> tuple[PeriodStats, float]:
    """Statistiques sur les années ENTIÈRES de la période (12 mois de données).

    Règle (la même pour pluie, NDVI et température) : la période est ramenée aux années entières
    réellement utilisées (start, end et label les reflètent : « 2016–2024 » si 2025 est incomplète,
    « 2016–2022 » pour la température arrêtée en 2022 ; « 2001–2010 (sans 2005) » s'il manque une
    année au milieu). Si moins de la moitié des années demandées sont entières → 400 invalid_period.
    Renvoie aussi la moyenne pleine précision (pour delta_abs / delta_pct)."""
    years = range(int(start), int(end) + 1)
    first, last = store.first_date(indicator), store.last_date(indicator)
    span = range(max(int(start), int(first[:4])), min(int(end), int(last[:4])) + 1) if first and last else range(0)
    vals = {y: v for y in span if (v := _year_value(region_id, indicator, y)) is not None}
    need = math.ceil(len(years) / 2)
    if len(vals) < need:
        raise _invalid(f"Période {_years_label(int(start), int(end))} : {len(vals)} année(s) entière(s) de données "
                       f"sur {len(years)}, il en faut au moins {need} (une année compte si elle a ses 12 mois ; "
                       f"données disponibles : {first or '?'} → {last or '?'})")
    used = sorted(vals)
    s, e = used[0], used[-1]
    label = _years_label(s, e)
    missing = [str(y) for y in range(s, e + 1) if y not in vals]
    if missing:
        label += f" (sans {', '.join(missing)})"
    v = list(vals.values())
    mean = math.fsum(v) / len(v)
    return PeriodStats(label=label, start=f"{s:04d}", end=f"{e:04d}", mean=_round(indicator, mean),
                       min=_round(indicator, min(v)), max=_round(indicator, max(v))), mean


def _comparison(region_id: str, indicator: str, a: PeriodStats, a_mean: float,
                b: PeriodStats, b_mean: float) -> Comparison:
    delta = b_mean - a_mean
    return Comparison(region_id=region_id, indicator=indicator, units=dataset_for(indicator).units,
                      period_a=a, period_b=b, delta_abs=_round(indicator, delta),
                      delta_pct=_rnd(delta / a_mean * 100, 1) if a_mean else None,
                      dataset_id=IND2DS[indicator])


def compare(region_id: str, indicator: IndicatorId, a_start: str, a_end: str,
            b_start: str, b_end: str) -> Comparison:
    """Comparaison de deux périodes d'années (M16), sur les années entières (voir _period)."""
    get_region(region_id)
    _check_ts_indicator(indicator)
    for name, v in (("a_start", a_start), ("a_end", a_end), ("b_start", b_start), ("b_end", b_end)):
        if not YEAR_RE.match(v or ""):
            raise _invalid(f"{name} doit être une année YYYY (reçu : {v})")
    if a_start > a_end or b_start > b_end:
        raise _invalid("Chaque période doit avoir un début avant sa fin")
    a, a_mean = _period(region_id, indicator, a_start, a_end)
    b, b_mean = _period(region_id, indicator, b_start, b_end)
    return _comparison(region_id, indicator, a, a_mean, b, b_mean)


# ─────────── M17 · Export ───────────
def export_timeseries(region_id: str, indicator: IndicatorId, start: Optional[str] = None,
                      end: Optional[str] = None, format: Literal["csv", "json"] = "csv") -> tuple[str, str, str]:
    """Renvoie (contenu, media_type, nom_de_fichier).

    CSV : en-tête `# source`, `# units`, colonnes `date,value,baseline,anomaly_pct` (M17), puis une
    ligne de commentaire `# low_coverage: <date> …` par valeur à faible couverture (à la fin, pour ne
    pas casser les lecteurs qui attendent l'en-tête en 3e ligne ; lire avec comment="#")."""
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
    lines += [f"# low_coverage: {p.date} valid_frac={p.valid_frac:.2f} : moins de 50 % de la région visible "
              f"(nuages), valeur peu fiable" for p in ts.points if p.low_coverage and p.valid_frac is not None]
    return "\n".join(lines) + "\n", "text/csv", fname


# ─────────── M18 · Avant / après ───────────
def _check_day(value: str, name: str) -> str:
    if not DAY_RE.match(value or ""):
        raise _invalid(f"{name} doit être au format YYYY-MM-DD (reçu : {value})")
    try:
        dt.date.fromisoformat(value)
    except ValueError:
        raise _invalid(f"{name} n'est pas une date du calendrier (reçu : {value})") from None
    return value


def _step(dates: list[str]) -> int:
    """Pas des images de la couche, en jours (le plus fréquent : 16, 8 ou 1)."""
    diffs = Counter((dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days for a, b in zip(dates, dates[1:]))
    return diffs.most_common(1)[0][0] if diffs else 1


def _check_layer_date(layer: MapLayer, value: str, name: str) -> str:
    """Une date est servie si c'est une date d'image de la couche (`available_dates`) ou si elle tombe
    dans la période couverte par une image (GIBS renvoie alors l'image précédente). Hors des plages de
    la couche (avant la première, après la dernière, ou dans un trou entre deux plages) → invalid_period."""
    _check_day(value, name)
    dates = layer.available_dates
    if not dates:
        return value
    step = _step(dates)
    i = bisect.bisect_right(dates, value) - 1
    ok = i >= 0 and (dates[i] == value or (
        i + 1 < len(dates)
        and (dt.date.fromisoformat(dates[i + 1]) - dt.date.fromisoformat(dates[i])).days == step))
    if not ok:
        raise _invalid(f"{name} ({value}) : pas d'image de la couche {layer.id} à cette date (images du "
                       f"{dates[0]} au {dates[-1]}, une tous les {step} jour(s) ; dates exactes dans GET /layers)")
    return value


def _default_before(layer: MapLayer, after: str) -> str:
    """Date « avant » par défaut : l'image la plus proche du même jour, le plus d'années possible avant
    `after` dans les dates de la couche (même saison) ; à défaut, la première date de la couche."""
    dates = layer.available_dates
    a = dt.date.fromisoformat(after)
    for n in range(a.year - int(dates[0][:4]), 0, -1):
        try:
            target = a.replace(year=a.year - n)
        except ValueError:          # 29 février
            target = a.replace(year=a.year - n, day=28)
        if target.isoformat() >= dates[0]:
            return min(dates, key=lambda d: abs((dt.date.fromisoformat(d) - target).days))
    return dates[0]


def _months_label(months: list[int]) -> str:
    if len(months) == 1:
        return MONTHS_FR[months[0] - 1]
    if months == list(range(months[0], months[-1] + 1)):
        return f"{MONTHS_FR[months[0] - 1]}–{MONTHS_FR[months[-1] - 1]}"
    return f"{len(months)} mois communs"


def _year_vs_year(region_id: str, indicator: str, yb: str, ya: str) -> tuple[Optional[Comparison], Optional[str]]:
    """Comparaison de l'année `yb` avec l'année `ya` (M18).

    - deux années entières → comparaison M16 sur l'année entière ;
    - sinon, comparaison sur les mois communs aux deux années (même saison des deux côtés), s'il y en
      a au moins MIN_COMMON_MONTHS ; `comparison_note` le dit et le label des périodes nomme les mois ;
    - sinon → pas de comparaison, `comparison_note` dit pourquoi."""
    name = LABELS[indicator].lower()
    pb = {int(d[5:7]): (d, o) for d, o in _pairs(region_id, indicator, _months(f"{yb}-01", f"{yb}-12"))}
    pa = {int(d[5:7]): (d, o) for d, o in _pairs(region_id, indicator, _months(f"{ya}-01", f"{ya}-12"))}
    common = sorted(set(pb) & set(pa))
    if len(common) == 12:
        return compare(region_id, indicator, yb, yb, ya, ya), None
    partial = [f"{y} ({len(p)} mois sur 12)" for y, p in ((yb, pb), (ya, pa)) if len(p) < 12]
    if len(common) < MIN_COMMON_MONTHS:
        last = store.last_date(indicator, region_id)
        note = (f"Pas de comparaison chiffrée entre {yb} et {ya} : données de {name} incomplètes pour "
                f"{', '.join(dict.fromkeys(partial))}, moins de {MIN_COMMON_MONTHS} mois communs aux deux années")
        note += f" (dernière donnée : {_month_label(last)})." if last else "."
        return None, note
    mlabel = _months_label(common)
    stats = []
    for y, p in ((yb, pb), (ya, pa)):
        value, _ = _on_months(region_id, indicator, [p[m] for m in common])
        r = _round(indicator, value)
        stats.append((PeriodStats(label=f"{y} ({mlabel})", start=y, end=y, mean=r, min=r, max=r), value))
    note = (f"Comparaison sur les mêmes mois ({mlabel}) : {' et '.join(dict.fromkeys(partial))} "
            f"incomplète(s) dans les données ; une année partielle n'est pas comparée à une année entière.")
    return _comparison(region_id, indicator, stats[0][0], stats[0][1], stats[1][0], stats[1][1]), note


def before_after(layer_id: str, before: Optional[str] = None, after: Optional[str] = None,
                 region_id: Optional[str] = None) -> BeforeAfter:
    """Cartes de deux dates ; si `region_id`, comparaison de l'année de `before` avec celle de `after`.

    Dates : elles doivent être servies par la couche (voir _check_layer_date), sinon 400 invalid_period.
    Par défaut : `after` = dernière date de la couche ; `before` = même jour, le plus d'années possible
    avant (voir _default_before). `before` doit précéder (ou égaler) `after`.
    Comparaison : voir _year_vs_year ; si elle est impossible, les cartes restent servies, `comparison`
    est null et `comparison_note` dit pourquoi."""
    layer = get_layer(layer_id)
    after = _check_layer_date(layer, after, "after") if after else (layer.default_date or layer.available_dates[-1])
    before = _check_layer_date(layer, before, "before") if before else _default_before(layer, after)
    if before > after:
        raise _invalid(f"before ({before}) doit précéder after ({after})")
    comp, note = None, None
    if region_id:
        get_region(region_id)
        comp, note = _year_vs_year(region_id, layer.indicator, before[:4], after[:4])
    return BeforeAfter(layer_id=layer_id,
                       before=LayerAtDate(date=before, url_template=layer.url_template.replace("{date}", before)),
                       after=LayerAtDate(date=after, url_template=layer.url_template.replace("{date}", after)),
                       comparison=comp, comparison_note=note)


# ─────────── M19 · Tableau de bord ───────────
HIGHLIGHTS = 3
MIN_RAIN_BASE_MM = 20.0   # pluie : pas de fait marquant si la normale du mois est sous 20 mm (saison sèche)
_NAMES = {"precipitation": "la pluie", "ndvi": "la verdure (NDVI)", "lst_day": "la température du sol"}
_SHORT = {"precipitation": "pluie du mois", "ndvi": "verdure (NDVI)", "lst_day": "température du sol"}
_THRESHOLDS = {"precipitation": "±10 %", "ndvi": "±10 %", "lst_day": "±1,5 °C"}


def _strength(s: IndicatorSnapshot) -> float:
    """Écart à la normale rapporté à son seuil de tendance (1 = seuil) : rend comparables pluie,
    NDVI (en %) et température (en °C ; un % de degrés n'aurait pas de sens)."""
    if s.indicator == "lst_day":
        return abs(_rnd(s.value - s.baseline, 1)) / LST_DELTA
    return abs(s.anomaly_pct) / ANOMALY_PCT


def _highlight(region_name: str, s: IndicatorSnapshot, total: int, clouds: bool) -> Statement:
    """Phrase d'un fait marquant. Les chiffres sont ceux du snapshot (même écart affiché)."""
    side = "au-dessus" if s.trend == "above_normal" else "en dessous"
    gap = (f"{_fr(abs(_rnd(s.value - s.baseline, 1)), 1)} °C" if s.indicator == "lst_day"
           else f"{_half_up(s.anomaly_pct)} %")
    rank = ("le seul écart notable du mois" if total == 1
            else f"l'un des {total} écarts notables du mois" if total <= HIGHLIGHTS
            else f"l'un des {HIGHLIGHTS} plus grands écarts du mois (sur {total} écarts notables)")
    text = f"{region_name}, {_month_label(s.date)} : {_SHORT[s.indicator]} {gap} {side} de la normale 2001–2020, {rank}"
    text += " ; valeurs peu fiables à cause des nuages écartées." if clouds else "."
    return Statement(text=text, nature="observed", source_ids=[f"ds:{s.dataset_id}"])


def dashboard(date: Optional[str] = None) -> Dashboard:
    """Vue nationale (M19). Faits marquants (`highlights`) = les 3 plus grands écarts à la normale du
    mois du tableau de bord, toutes régions et indicateurs confondus. Règles :
    1. seulement les valeurs DU mois (un snapshot replié sur un mois antérieur est exclu) ;
    2. seulement les écarts notables (trend above/below) : une valeur « normale » n'est pas un fait marquant ;
    3. pluie : ignorée si la normale du mois est sous MIN_RAIN_BASE_MM (20 mm) — en saison sèche, quelques
       millimètres font des % énormes sans signification ;
    4. valeurs à faible couverture (< 50 % de la région visible) écartées : trop peu fiables pour être
       mises en avant (elles restent signalées dans `regions`) ; la phrase le dit si c'est arrivé ;
    5. écarts classés en multiples de leur seuil (10 % pluie / NDVI, 1,5 °C température) ;
    6. la phrase dit le rang réel (« le seul écart notable », « l'un des 2 », « l'un des 3 plus grands »).
    Aucun candidat → une phrase qui le dit (mois sans écart notable)."""
    summaries = [summary(rid, date) for rid in REGION_IDS]
    date = summaries[0].date
    month_snaps = [(s.region.name, snap) for s in summaries for snap in s.indicators if snap.date == date]
    notable = [(n, snap) for n, snap in month_snaps
               if snap.trend in ("above_normal", "below_normal")
               and not (snap.indicator == "precipitation" and (snap.baseline or 0) < MIN_RAIN_BASE_MM)]
    candidates = [(n, snap) for n, snap in notable if not snap.low_coverage]
    clouds = len(candidates) < len(notable)
    candidates.sort(key=lambda c: -_strength(c[1]))  # tri stable : ordre des régions en cas d'égalité
    highlights = [_highlight(n, s, len(candidates), clouds) for n, s in candidates[:HIGHLIGHTS]]
    if not highlights:
        with_data = [i for i in TS_INDICATORS
                     if any(sn.indicator == i and sn.value is not None for _, sn in month_snaps)]
        missing = [_NAMES[i] for i in TS_INDICATORS if i not in with_data]
        if with_data:
            text = (f"{_month_label(date)} : aucune valeur fiable ne s'écarte nettement de la normale 2001–2020 "
                    f"pour {' ni '.join(f'{_NAMES[i]} ({_THRESHOLDS[i]})' for i in with_data)}")
            if "precipitation" in with_data:
                text += f" (pluie : seulement là où la normale du mois dépasse {MIN_RAIN_BASE_MM:.0f} mm)"
            text += f" ; pas encore de donnée pour {' ni '.join(missing)} ce mois-ci." if missing else "."
        else:
            text = f"{_month_label(date)} : pas de donnée satellite pour ce mois."
        highlights = [Statement(text=text[0].upper() + text[1:], nature="observed",
                                source_ids=[f"ds:{IND2DS[i]}" for i in with_data])]
    return Dashboard(date=date, regions=summaries, highlights=highlights)


# ─────────── M20 · Agriculture ───────────
# Sud (maritime, plateaux) : deux saisons des pluies (avril–juillet, septembre–octobre) ;
# nord (centrale, kara, savanes) : une saison (mai–octobre). Mois de bascule → transition.
SEASONS = {
    "south": {"rainy": {4, 5, 6, 7, 9, 10}, "transition": {3, 8, 11}},
    "north": {"rainy": {5, 6, 7, 8, 9, 10}, "transition": {4, 11}},
}
_RAIN_STATE = {"below_normal": "plus faible que d'habitude", "above_normal": "plus forte que d'habitude",
               "normal": "proche de l'habitude"}
_VEG_STATE = {"below_normal": "moins verte que d'habitude", "above_normal": "plus verte que d'habitude",
              "normal": "proche de l'habitude"}


def season(region_id: str, month: int) -> Literal["dry", "rainy", "transition"]:
    zone = SEASONS["north" if region_id in NORTH else "south"]
    return "rainy" if month in zone["rainy"] else "transition" if month in zone["transition"] else "dry"


def _advice(seas: str, rain: IndicatorSnapshot, veg: IndicatorSnapshot) -> list[Statement]:
    """1 à 2 conseils `interpreted` (M20). Une donnée absente (trend unknown) ne produit AUCUN conseil
    fondé sur elle ; chaque conseil ne cite que l'indicateur sur lequel il s'appuie (pluie → ds pluie,
    végétation → ds NDVI) et son texte dit ce que montre la donnée. Aucune donnée connue pour le mois →
    aucun conseil. Un conseil fondé sur une valeur à faible couverture le dit."""
    rain_ok, veg_ok = rain.trend != "unknown", veg.trend != "unknown"
    rain_src, veg_src = [f"ds:{rain.dataset_id}"], [f"ds:{veg.dataset_id}"]
    out: list[Statement] = []
    if rain_ok and seas == "rainy" and rain.trend == "below_normal":
        out.append(Statement(text="Pluie plus faible que d'habitude en saison des pluies : surveillez l'humidité "
                                  "du sol avant de semer.", nature="interpreted", source_ids=rain_src))
    elif rain_ok and seas == "rainy" and rain.trend == "above_normal":
        out.append(Statement(text="Pluie plus forte que d'habitude : surveillez l'eau stagnante dans les champs "
                                  "bas et l'érosion des sols en pente.", nature="interpreted", source_ids=rain_src))
    elif rain_ok and seas == "transition":
        out.append(Statement(text=f"Mois de bascule entre saisons, pluie {_RAIN_STATE[rain.trend]} : suivez "
                                  "l'arrivée ou l'arrêt des pluies avant de planifier semis ou récoltes.",
                             nature="interpreted", source_ids=rain_src))
    if veg_ok and veg.trend == "below_normal":
        out.append(Statement(text="La végétation est moins verte que d'habitude : vérifiez l'état des cultures "
                                  "et des pâturages.", nature="interpreted", source_ids=veg_src))
    if not out and (rain_ok or veg_ok):
        src = (rain_src if rain_ok else []) + (veg_src if veg_ok else [])
        if rain_ok and veg_ok and rain.trend == veg.trend == "normal":
            facts = "pluie et végétation proches de l'habitude"
        else:
            facts = " et ".join(([f"pluie {_RAIN_STATE[rain.trend]}"] if rain_ok else []) +
                                ([f"végétation {_VEG_STATE[veg.trend]}"] if veg_ok else []))
        if seas == "dry":
            # Saison sèche : la phrase dit ce que montre la donnée, sans rien affirmer d'autre
            text = f"Saison sèche, {facts} : l'arrosage et la conservation de l'eau restent prioritaires."
        else:
            text = f"{facts[0].upper()}{facts[1:]} pour la saison : pas de signal particulier."
        out.append(Statement(text=text, nature="interpreted", source_ids=src))
    by_src = {rain_src[0]: rain, veg_src[0]: veg}
    for st in out:
        if any(by_src[i].low_coverage for i in st.source_ids):
            st.text += " Attention : valeur satellite peu fiable ce mois-ci (nuages), à confirmer sur le terrain."
    return out[:2]


def _same_month(region_id: str, snap: IndicatorSnapshot, month: str) -> IndicatorSnapshot:
    """Le snapshot du mois `month` exactement (sans repli sur un mois antérieur)."""
    return snap if snap.date == month else snapshot(region_id, snap.indicator, month, "public", fallback=False)


def agriculture(region_id: str, date: Optional[str] = None) -> AgriInsight:
    """Repères agricoles (M20).

    Règle des dates : le mois traité est `RegionSummary.date` (dernier mois des données toutes séries
    confondues si `date` est absente). La saison ET les statuts pluie / végétation portent sur CE mois :
    un indicateur sans valeur pour ce mois (ex. pluie IMERG pas encore publiée) a le statut unknown, sa
    phrase observée dit « pas de donnée pour <mois> (dernière donnée : …) » et aucun conseil ne s'appuie
    sur lui. On ne mélange jamais la saison d'un mois avec la pluie d'un autre mois."""
    s = summary(region_id, date)
    by = {i.indicator: i for i in s.indicators}
    rain, veg = (_same_month(region_id, by[k], s.date) for k in ("precipitation", "ndvi"))
    seas = season(region_id, int(s.date[5:7]))
    observed = [Statement(text=x.plain_summary, nature="observed", source_ids=[f"ds:{x.dataset_id}"])
                for x in (rain, veg)]
    return AgriInsight(region_id=region_id, date=s.date, season=seas,
                       rainfall_status=rain.trend, vegetation_status=veg.trend,
                       statements=observed + _advice(seas, rain, veg), disclaimer=DISCLAIMER)
