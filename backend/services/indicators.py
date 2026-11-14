"""Séries, résumés, comparaisons, avant/après, tableau de bord, agriculture.

TODO M14–M20 (après P2) : calculs sur le DataFrame de backend.repositories.store
(normale 2001–2020, anomalie, tendance, arrondis — voir MISSIONS.md, bloc 4).
D'ici là : valeurs mock.
"""
from typing import Literal, Optional

from backend.core.constants import DISCLAIMER
from backend.repositories.store import mock_value
from backend.schemas import (AgriInsight, BeforeAfter, Comparison, Dashboard, Granularity,
                             IndicatorId, IndicatorSnapshot, LayerAtDate, Mode, PeriodStats,
                             RegionSummary, Statement, TimePoint, TimeSeries)

from .catalog import IND2DS, LABELS, dataset_for, get_layer
from .regions import REGIONS, get_region


def timeseries(region_id: str, indicator: IndicatorId, start: str, end: str,
               granularity: Granularity = "month") -> TimeSeries:
    get_region(region_id)
    pts = []
    y, m = map(int, start.split("-")[:2])
    ye, me = map(int, end.split("-")[:2])
    while (y, m) <= (ye, me):
        v, b = mock_value(indicator, m), mock_value(indicator, m)
        pts.append(TimePoint(date=f"{y}-{m:02d}", value=round(v, 2), baseline=round(b, 2),
                             anomaly_pct=round((v - b) / b * 100, 1)))
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return TimeSeries(region_id=region_id, indicator=indicator, units=dataset_for(indicator).units,
                      granularity=granularity, points=pts, dataset_id=IND2DS[indicator])


def summary(region_id: str, date: str = "2026-09", mode: Mode = "public") -> RegionSummary:
    r = get_region(region_id)
    snaps = []
    for ind in ("precipitation", "ndvi", "lst_day"):
        v, b = mock_value(ind, int(date[5:7])), mock_value(ind, int(date[5:7]))
        a = (v - b) / b * 100
        trend = "above_normal" if a > 10 else "below_normal" if a < -10 else "normal"
        snaps.append(IndicatorSnapshot(
            indicator=ind, label=LABELS[ind], value=round(v, 2), units=dataset_for(ind).units,
            date=date, baseline=round(b, 2), anomaly_pct=round(a, 1), trend=trend,
            plain_summary=f"{LABELS[ind]} : {'au-dessus' if a > 10 else 'en dessous' if a < -10 else 'proche'} de la normale.",
            dataset_id=IND2DS[ind]))
    return RegionSummary(region=r, date=date, indicators=snaps)


def compare(region_id: str, indicator: IndicatorId, a_start: str, a_end: str,
            b_start: str, b_end: str) -> Comparison:
    get_region(region_id)
    ma, mb = mock_value(indicator, 7), mock_value(indicator, 7)
    return Comparison(
        region_id=region_id, indicator=indicator, units=dataset_for(indicator).units,
        period_a=PeriodStats(label=f"{a_start}–{a_end}", start=a_start, end=a_end, mean=ma, min=ma * .7, max=ma * 1.3),
        period_b=PeriodStats(label=f"{b_start}–{b_end}", start=b_start, end=b_end, mean=mb, min=mb * .7, max=mb * 1.3),
        delta_abs=mb - ma, delta_pct=(mb - ma) / ma * 100, dataset_id=IND2DS[indicator])


def export_timeseries(region_id: str, indicator: IndicatorId, start: str, end: str,
                      format: Literal["csv", "json"] = "csv") -> tuple[str, str, str]:
    """Renvoie (contenu, media_type, nom_de_fichier)."""
    ts = timeseries(region_id, indicator, start, end)
    ds = dataset_for(indicator)
    fname = f"agbea_{region_id}_{indicator}_{start}_{end}.{format}"
    if format == "json":
        return ts.model_dump_json(indent=2), "application/json", fname
    lines = [f"# source: {ds.name} ({ds.source_url})", f"# units: {ds.units}",
             "date,value,baseline,anomaly_pct"]
    lines += [f"{p.date},{p.value},{p.baseline},{p.anomaly_pct}" for p in ts.points]
    return "\n".join(lines), "text/csv", fname


def before_after(layer_id: str, before: str, after: str,
                 region_id: Optional[str] = None) -> BeforeAfter:
    layer = get_layer(layer_id)
    comp = compare(region_id, layer.indicator, before[:4], before[:4], after[:4], after[:4]) if region_id else None
    return BeforeAfter(layer_id=layer_id,
                       before=LayerAtDate(date=before, url_template=layer.url_template.replace("{date}", before)),
                       after=LayerAtDate(date=after, url_template=layer.url_template.replace("{date}", after)),
                       comparison=comp)


def dashboard(date: str = "2026-09") -> Dashboard:
    return Dashboard(date=date, regions=[summary(rid, date) for rid in REGIONS], highlights=[
        Statement(text="Pluie inférieure à la normale dans les Savanes en septembre.",
                  nature="observed", source_ids=["ds:gpm_imerg"])])


def agriculture(region_id: str, date: str = "2026-09") -> AgriInsight:
    s = summary(region_id, date)
    by = {i.indicator: i for i in s.indicators}
    m = int(date[5:7])
    return AgriInsight(
        region_id=region_id, date=date,
        season="rainy" if 5 <= m <= 9 else "transition" if m in (4, 10) else "dry",
        rainfall_status=by["precipitation"].trend, vegetation_status=by["ndvi"].trend,
        statements=[Statement(text=by["precipitation"].plain_summary, nature="observed", source_ids=["ds:gpm_imerg"]),
                    Statement(text="Surveillez l'humidité du sol avant de semer.", nature="interpreted", source_ids=[])],
        disclaimer=DISCLAIMER)
