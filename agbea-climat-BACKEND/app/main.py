"""AGBÉA CLIMAT — squelette FastAPI avec MOCKS.
Objectif J1 matin : le front branche tout de suite sur ces routes.
Remplacer les mocks par les vraies données au fur et à mesure (même contrat).

Lancer :  uvicorn app.main:app --reload --port 8000
Docs   :  http://localhost:8000/docs
"""
import asyncio
import json
import random
import uuid
from typing import Optional

from fastapi import APIRouter, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .schemas import *  # noqa: F403

app = FastAPI(title="AGBÉA CLIMAT API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
api = APIRouter(prefix="/api/v1")


from fastapi.exceptions import RequestValidationError  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from starlette.exceptions import HTTPException as StarletteHTTPException  # noqa: E402


@app.exception_handler(StarletteHTTPException)
async def http_error(_, exc: StarletteHTTPException):
    d = exc.detail if isinstance(exc.detail, dict) else {"code": str(exc.status_code), "message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content={"error": d})


@app.exception_handler(RequestValidationError)
async def validation_error(_, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"error": {
        "code": "validation_error", "message": "Paramètres invalides", "details": exc.errors()}})

DISCLAIMER = ("AGBÉA CLIMAT aide à comprendre l'environnement. Il ne remplace pas "
              "les prévisions officielles ni les systèmes d'alerte.")

# ─────────── Données mock ───────────
REGIONS = {
    r.id: r for r in [
        Region(id="maritime", name="Maritime", capital="Lomé", centroid=(1.35, 6.35), bbox=(0.9, 6.1, 1.8, 6.7)),
        Region(id="plateaux", name="Plateaux", capital="Atakpamé", centroid=(1.0, 7.4), bbox=(0.5, 6.6, 1.7, 8.3)),
        Region(id="centrale", name="Centrale", capital="Sokodé", centroid=(1.1, 8.7), bbox=(0.4, 8.2, 1.7, 9.3)),
        Region(id="kara", name="Kara", capital="Kara", centroid=(1.0, 9.7), bbox=(0.3, 9.2, 1.6, 10.2)),
        Region(id="savanes", name="Savanes", capital="Dapaong", centroid=(0.4, 10.6), bbox=(-0.2, 10.1, 1.0, 11.2)),
    ]
}

DATASETS = {
    "gpm_imerg": Dataset(
        id="gpm_imerg", name="NASA GPM IMERG (Final)", provider="NASA GES DISC",
        variable="Precipitation", indicator="precipitation", units="mm",
        spatial_resolution="0.1° (~10 km)", temporal_resolution="monthly",
        coverage="60°N–60°S", period_start="2000-06-01",
        limitations=["Estimation satellite, pas une mesure de pluviomètre"],
        source_url="https://gpm.nasa.gov/data/imerg"),
    "modis_ndvi": Dataset(
        id="modis_ndvi", name="MODIS Terra MOD13Q1", provider="NASA LP DAAC",
        variable="NDVI", indicator="ndvi", units="",
        spatial_resolution="250 m", temporal_resolution="16 jours",
        coverage="Global", period_start="2000-02-18",
        limitations=["Nuages possibles en saison des pluies"],
        source_url="https://lpdaac.usgs.gov/products/mod13q1v061/"),
    "modis_lst": Dataset(
        id="modis_lst", name="MODIS Terra MOD11A2", provider="NASA LP DAAC",
        variable="Land Surface Temperature (jour)", indicator="lst_day", units="°C",
        spatial_resolution="1 km", temporal_resolution="8 jours",
        coverage="Global", period_start="2000-03-05",
        limitations=["Température de la surface du sol, pas de l'air"],
        source_url="https://lpdaac.usgs.gov/products/mod11a2v061/"),
    "srtm": Dataset(
        id="srtm", name="SRTM GL1", provider="NASA / USGS",
        variable="Elevation", indicator="elevation", units="m",
        spatial_resolution="30 m", temporal_resolution="statique (2000)",
        coverage="56°S–60°N", period_start="2000-02-11", period_end="2000-02-22",
        limitations=["Relief mesuré en 2000 : ne montre pas les changements récents"],
        source_url="https://lpdaac.usgs.gov/products/srtmgl1v003/"),
}
IND2DS = {d.indicator: d.id for d in DATASETS.values()}
LABELS = {"precipitation": "Pluie du mois", "ndvi": "Verdure (NDVI)",
          "lst_day": "Température du sol", "elevation": "Altitude"}


def _region(region_id: str) -> Region:
    if region_id not in REGIONS:
        raise HTTPException(404, detail={"code": "region_not_found", "message": region_id})
    return REGIONS[region_id]


def _mock_value(ind: str, month: int) -> float:
    rainy = 1 if 4 <= month <= 10 else 0
    return {"precipitation": 20 + rainy * 140, "ndvi": 0.35 + rainy * 0.3,
            "lst_day": 38 - rainy * 6, "elevation": 300}[ind] * random.uniform(0.8, 1.2)


# ─────────── Méta ───────────
@api.get("/health")
def health():
    return {"status": "ok"}


@api.get("/meta", response_model=AppMeta)
def meta():
    return AppMeta(version="0.1.0", regions_count=len(REGIONS), data_last_updated="2026-10-31", features=[
        Feature(id="map", title="Carte interactive du Togo", status="prototype"),
        Feature(id="chat", title="Assistant IA (texte)", status="prototype"),
        Feature(id="voice", title="AGBÉA Voice", status="in_development"),
        Feature(id="ewe", title="Langue éwé", status="planned"),
    ])


# ─────────── Types d'utilisateurs ───────────
PROFILES = [
    Profile(id="farmer", title="Agriculteurs", audience="Agriculteurs, coopératives", icon="sprout",
            benefit="Comprendre la pluie et la végétation pour mieux planifier les cultures.",
            default_mode="public", landing_screen="agriculture", featured_indicators=["precipitation", "ndvi"],
            ai_tone="Phrases courtes, conseils pratiques, pas de jargon"),
    Profile(id="community", title="Communautés", audience="Citoyens, associations", icon="users",
            benefit="Accéder à des explications environnementales en langage simple.",
            default_mode="public", landing_screen="dashboard", featured_indicators=["precipitation", "lst_day"],
            ai_tone="Langage simple, exemples du quotidien"),
    Profile(id="researcher", title="Chercheurs et étudiants", audience="Chercheurs, étudiants, professionnels", icon="graduation-cap",
            benefit="Explorer les indicateurs environnementaux historiques.",
            default_mode="scientific", landing_screen="scientific",
            featured_indicators=["precipitation", "ndvi", "lst_day", "elevation"],
            ai_tone="Précis, unités, résolutions et limites des données"),
    Profile(id="decision_maker", title="Décideurs locaux", audience="Collectivités, services techniques", icon="landmark",
            benefit="Utiliser les observations pour la planification et la sensibilisation.",
            default_mode="public", landing_screen="dashboard", featured_indicators=["precipitation", "ndvi", "lst_day"],
            ai_tone="Synthèse, comparaisons entre régions, chiffres clés"),
]


@api.get("/profiles", response_model=list[Profile])
def list_profiles():
    return PROFILES


# ─────────── Sessions anonymes (mock en mémoire → table SQLite/Postgres) ───────────
from datetime import datetime, timezone  # noqa: E402

SESSIONS: dict[str, Session] = {}


@api.post("/sessions", response_model=Session, status_code=201)
def create_session():
    now = datetime.now(timezone.utc).isoformat()
    s = Session(session_id=str(uuid.uuid4()), preferences=Preferences(), threads=[], created_at=now, last_seen_at=now)
    SESSIONS[s.session_id] = s
    return s


def _session(session_id: str) -> Session:
    if session_id not in SESSIONS:
        raise HTTPException(404, detail={"code": "session_not_found", "message": session_id})
    return SESSIONS[session_id]


@api.get("/sessions/{session_id}", response_model=Session)
def get_session(session_id: str):
    s = _session(session_id)
    s.last_seen_at = datetime.now(timezone.utc).isoformat()
    s.threads.sort(key=lambda t: t.updated_at, reverse=True)
    return s


@api.patch("/sessions/{session_id}/preferences", response_model=Preferences)
def update_preferences(session_id: str, prefs: Preferences):
    s = _session(session_id)
    if prefs.region_id is not None:
        _region(prefs.region_id)
    s.preferences = s.preferences.model_copy(update=prefs.model_dump(exclude_unset=True))
    return s.preferences


# ─────────── Géo & provenance ───────────
@api.get("/regions", response_model=list[Region])
def list_regions():
    return list(REGIONS.values())


@api.get("/regions/geojson")
def regions_geojson():
    # TODO : servir le vrai fichier (GADM / geoBoundaries ADM1 Togo) depuis data/regions.geojson
    feats = []
    for r in REGIONS.values():
        x0, y0, x1, y1 = r.bbox
        feats.append({"type": "Feature", "properties": r.model_dump(),
                      "geometry": {"type": "Polygon", "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}})
    return {"type": "FeatureCollection", "features": feats}


@api.get("/regions/{region_id}", response_model=Region)
def get_region(region_id: str):
    return _region(region_id)


@api.get("/locate", response_model=Region)
def locate(lon: float, lat: float):
    for r in REGIONS.values():
        x0, y0, x1, y1 = r.bbox
        if x0 <= lon <= x1 and y0 <= lat <= y1:
            return r
    raise HTTPException(404, detail={"code": "outside_togo", "message": "Point hors du Togo"})


@api.get("/datasets", response_model=list[Dataset])
def list_datasets():
    return list(DATASETS.values())


@api.get("/datasets/{dataset_id}", response_model=Dataset)
def get_dataset(dataset_id: str):
    if dataset_id not in DATASETS:
        raise HTTPException(404, detail={"code": "dataset_not_found", "message": dataset_id})
    return DATASETS[dataset_id]


@api.get("/layers", response_model=list[MapLayer])
def list_layers(mode: Mode = "public"):
    # TODO : vérifier les identifiants exacts dans le catalogue GIBS (worldview.earthdata.nasa.gov)
    gibs = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/{layer}/default/{date}/GoogleMapsCompatible_Level9/{z}/{y}/{x}.png"
    layers = [
        MapLayer(id="ndvi", indicator="ndvi", dataset_id="modis_ndvi", title="Verdure de la végétation",
                 type="wmts", url_template=gibs.replace("{layer}", "MODIS_Terra_NDVI_16Day"),
                 available_dates=["2026-09-14"], default_date="2026-09-14",
                 legend=[LegendStop(value=0, color="#d8c48f", label="Sol nu"),
                         LegendStop(value=0.8, color="#1a7f37", label="Très vert")]),
        MapLayer(id="precipitation", indicator="precipitation", dataset_id="gpm_imerg", title="Pluie",
                 type="wmts", url_template=gibs.replace("{layer}", "IMERG_Precipitation_Rate"),
                 available_dates=["2026-09-30"], default_date="2026-09-30",
                 legend=[LegendStop(value=0, color="#e0f3ff"), LegendStop(value=300, color="#08306b")]),
    ]
    return [l for l in layers if mode in l.modes]


# ─────────── Indicateurs ───────────
@api.get("/regions/{region_id}/timeseries", response_model=TimeSeries)
def timeseries(region_id: str, indicator: IndicatorId,
               start: str = Query("2020-01"), end: str = Query("2026-10"),
               granularity: Granularity = "month"):
    _region(region_id)
    pts = []
    y, m = map(int, start.split("-")[:2])
    ye, me = map(int, end.split("-")[:2])
    while (y, m) <= (ye, me):
        v, b = _mock_value(indicator, m), _mock_value(indicator, m)
        pts.append(TimePoint(date=f"{y}-{m:02d}", value=round(v, 2), baseline=round(b, 2),
                             anomaly_pct=round((v - b) / b * 100, 1)))
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return TimeSeries(region_id=region_id, indicator=indicator, units=DATASETS[IND2DS[indicator]].units,
                      granularity=granularity, points=pts, dataset_id=IND2DS[indicator])


@api.get("/regions/{region_id}/summary", response_model=RegionSummary)
def summary(region_id: str, date: str = "2026-09", mode: Mode = "public"):
    r = _region(region_id)
    snaps = []
    for ind in ("precipitation", "ndvi", "lst_day"):
        v, b = _mock_value(ind, int(date[5:7])), _mock_value(ind, int(date[5:7]))
        a = (v - b) / b * 100
        trend = "above_normal" if a > 10 else "below_normal" if a < -10 else "normal"
        snaps.append(IndicatorSnapshot(
            indicator=ind, label=LABELS[ind], value=round(v, 2), units=DATASETS[IND2DS[ind]].units,
            date=date, baseline=round(b, 2), anomaly_pct=round(a, 1), trend=trend,
            plain_summary=f"{LABELS[ind]} : {'au-dessus' if a > 10 else 'en dessous' if a < -10 else 'proche'} de la normale.",
            dataset_id=IND2DS[ind]))
    return RegionSummary(region=r, date=date, indicators=snaps)


@api.get("/regions/{region_id}/compare", response_model=Comparison)
def compare(region_id: str, indicator: IndicatorId,
            a_start: str = "2001", a_end: str = "2010", b_start: str = "2016", b_end: str = "2025"):
    _region(region_id)
    ma, mb = _mock_value(indicator, 7), _mock_value(indicator, 7)
    return Comparison(
        region_id=region_id, indicator=indicator, units=DATASETS[IND2DS[indicator]].units,
        period_a=PeriodStats(label=f"{a_start}–{a_end}", start=a_start, end=a_end, mean=ma, min=ma * .7, max=ma * 1.3),
        period_b=PeriodStats(label=f"{b_start}–{b_end}", start=b_start, end=b_end, mean=mb, min=mb * .7, max=mb * 1.3),
        delta_abs=mb - ma, delta_pct=(mb - ma) / ma * 100, dataset_id=IND2DS[indicator])


# ─────────── Ajouts v0.2 ───────────
INDICATORS = [
    Indicator(id="precipitation", label="Pluie", units="mm", dataset_id="gpm_imerg", layer_id="precipitation",
              description_public="Quantité de pluie tombée, vue par satellite.",
              description_scientific="Précipitations GPM IMERG Final, cumul mensuel, grille 0.1°.", has_timeseries=True),
    Indicator(id="ndvi", label="Verdure de la végétation", units="", dataset_id="modis_ndvi", layer_id="ndvi",
              description_public="Plus la valeur est haute, plus la terre est verte.",
              description_scientific="NDVI MODIS MOD13Q1, composite 16 jours, 250 m.", has_timeseries=True),
    Indicator(id="lst_day", label="Température du sol", units="°C", dataset_id="modis_lst",
              description_public="Chaleur de la surface du sol en journée.",
              description_scientific="LST diurne MODIS MOD11A2, composite 8 jours, 1 km.", has_timeseries=True),
    Indicator(id="elevation", label="Altitude", units="m", dataset_id="srtm",
              description_public="Hauteur du terrain : zones basses et pentes.",
              description_scientific="MNT SRTM GL1, 30 m.", has_timeseries=False),
]


@api.get("/indicators", response_model=list[Indicator])
def list_indicators():
    return INDICATORS


@api.get("/dashboard", response_model=Dashboard)
def dashboard(date: str = "2026-09"):
    return Dashboard(date=date, regions=[summary(rid, date) for rid in REGIONS], highlights=[
        Statement(text="Pluie inférieure à la normale dans les Savanes en septembre.",
                  nature="observed", source_ids=["ds:gpm_imerg"])])


@api.get("/layers/{layer_id}/before-after", response_model=BeforeAfter)
def before_after(layer_id: str, before: str = "2016-09-14", after: str = "2026-09-14",
                 region_id: Optional[str] = None):
    layer = next((l for l in list_layers("public") + list_layers("scientific") if l.id == layer_id), None)
    if not layer:
        raise HTTPException(404, detail={"code": "layer_not_found", "message": layer_id})
    comp = compare(region_id, layer.indicator, before[:4], before[:4], after[:4], after[:4]) if region_id else None
    return BeforeAfter(layer_id=layer_id,
                       before=LayerAtDate(date=before, url_template=layer.url_template.replace("{date}", before)),
                       after=LayerAtDate(date=after, url_template=layer.url_template.replace("{date}", after)),
                       comparison=comp)


@api.get("/regions/{region_id}/agriculture", response_model=AgriInsight)
def agriculture(region_id: str, date: str = "2026-09"):
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


@api.get("/regions/{region_id}/timeseries/export")
def export_timeseries(region_id: str, indicator: IndicatorId, start: str = "2020-01",
                      end: str = "2026-10", format: Literal["csv", "json"] = "csv"):
    ts = timeseries(region_id, indicator, start, end)
    ds = DATASETS[ts.dataset_id]
    fname = f"agbea_{region_id}_{indicator}_{start}_{end}.{format}"
    headers = {"Content-Disposition": f'attachment; filename="{fname}"'}
    if format == "json":
        return StreamingResponse(iter([ts.model_dump_json(indent=2)]), media_type="application/json", headers=headers)
    lines = [f"# source: {ds.name} ({ds.source_url})", f"# units: {ds.units}",
             "date,value,baseline,anomaly_pct"]
    lines += [f"{p.date},{p.value},{p.baseline},{p.anomaly_pct}" for p in ts.points]
    return StreamingResponse(iter(["\n".join(lines)]), media_type="text/csv", headers=headers)


# ─────────── IA ───────────
@api.post("/explain", response_model=ExplainResponse)
def explain(req: ExplainRequest):
    _region(req.region_id)
    ds = DATASETS[IND2DS[req.indicator]]
    return ExplainResponse(
        title=f"{LABELS[req.indicator]} — {REGIONS[req.region_id].name}",
        statements=[
            Statement(text="Les satellites montrent moins de pluie que la normale ce mois-ci.",
                      nature="observed", source_ids=["computed:1"]),
            Statement(text="Cela peut expliquer une végétation moins verte que d'habitude.",
                      nature="interpreted", source_ids=["doc:1"]),
        ],
        sources=[Source(id="computed:1", kind="computed", title=f"Série {ds.name}", dataset_id=ds.id),
                 Source(id="doc:1", kind="document", title="Doc mock", snippet="…")],
        disclaimer=DISCLAIMER)


def _sse(ev: BaseModel) -> str:
    return f"data: {ev.model_dump_json()}\n\n"


@api.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    async def gen():
        tid = req.thread_id or str(uuid.uuid4())
        yield _sse(EvMeta(thread_id=tid))
        for step in ("routing", "fetching_data", "retrieving", "generating"):
            yield _sse(EvStatus(step=step))
            await asyncio.sleep(0.2)
        for w in "Dans votre région, les satellites observent une baisse de la verdure depuis août.".split():
            yield _sse(EvToken(content=w + " "))
            await asyncio.sleep(0.04)
        yield _sse(EvSources(sources=[Source(id="ds:modis_ndvi", kind="dataset", title="MODIS MOD13Q1", dataset_id="modis_ndvi")]))
        yield _sse(EvDone(statements=[Statement(text="Baisse de NDVI depuis août", nature="observed", source_ids=["ds:modis_ndvi"])]))
    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@api.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    return ChatResponse(thread_id=req.thread_id or str(uuid.uuid4()),
                        answer="Réponse mock.", statements=[], sources=[])


# ─────────── Admin RAG ───────────
@api.post("/admin/rag/ingest")
def rag_ingest():
    # TODO : charger data/corpus/*.pdf|md → chunk → embed → upsert vector store
    return {"ingested": 0}


@api.get("/admin/rag/documents")
def rag_documents():
    return {"documents": []}


# ─────────── Voix (en développement) ───────────
@api.post("/voice/transcribe", status_code=501)
def voice_transcribe():
    raise HTTPException(501, detail={"code": "in_development", "message": "AGBÉA Voice en développement"})


app.include_router(api)
