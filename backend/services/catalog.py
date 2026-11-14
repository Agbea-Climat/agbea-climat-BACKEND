"""Catalogue statique : méta, profils, datasets, indicateurs, couches de carte."""
import calendar
from datetime import date, timedelta

from backend.core.constants import APP_VERSION
from backend.core.exceptions import NotFound
from backend.repositories import store
from backend.schemas import (AppMeta, Dataset, Feature, Indicator, LegendStop, MapLayer, Mode,
                             Profile)

from .regions import REGION_IDS

# ─────────── Datasets ───────────
# Faits alignés sur pipeline/settings/datasets.yaml (produits réellement utilisés par le pipeline P2).
# Les ids ne changent pas : ce sont les dataset_id de data/processed/.
DATASETS: dict[str, Dataset] = {
    "gpm_imerg": Dataset(
        id="gpm_imerg", name="NASA GPM IMERG Final Run V07 (mensuel, GPM_3IMERGM)", provider="NASA GES DISC",
        variable="precipitation", indicator="precipitation", units="mm",
        spatial_resolution="0.1° (~11 km)", temporal_resolution="mensuel",
        coverage="Global (complet entre 60°N et 60°S)", period_start="1998-01-01",
        limitations=["Estimation satellite, pas une mesure de pluviomètre",
                     "Maille de ~11 km : une valeur représente une zone, pas un point précis",
                     "Final Run publié avec ~3 mois de retard",
                     "Séries AGBÉA à partir de 2001-01 (normales 2001-2020)"],
        source_url="https://disc.gsfc.nasa.gov/datasets/GPM_3IMERGM_07/summary",
        citation="doi:10.5067/GPM/IMERG/3B-MONTH/07"),
    "modis_ndvi": Dataset(
        id="modis_ndvi", name="MODIS Terra MOD13A1 v061", provider="NASA LP DAAC",
        variable="500m_16_days_NDVI", indicator="ndvi", units="",
        spatial_resolution="500 m", temporal_resolution="composite 16 jours, agrégé au mois",
        coverage="Global", period_start="2000-02-18",
        limitations=["Nuages de saison des pluies : trous fréquents, surtout sur la côte (juin-septembre)",
                     "Le NDVI mesure la verdeur, pas la biomasse ni le type de culture",
                     "Forte saisonnalité : comparer les mêmes mois d'une année à l'autre"],
        source_url="https://lpdaac.usgs.gov/products/mod13a1v061/",
        citation="doi:10.5067/MODIS/MOD13A1.061"),
    "modis_lst": Dataset(
        id="modis_lst", name="MODIS Terra MOD11A2 v061", provider="NASA LP DAAC",
        variable="LST_Day_1km", indicator="lst_day", units="°C",
        spatial_resolution="1 km", temporal_resolution="composite 8 jours, agrégé au mois",
        coverage="Global", period_start="2000-03-05",
        limitations=["Température de la surface du sol (toits, routes, champs), pas de l'air",
                     "Mesurée seulement par ciel clair : en saison des pluies, valeurs rares et biaisées vers les jours secs",
                     "Dérive orbitale de Terra depuis 2022 : tendances récentes de LST de jour à lire avec prudence"],
        source_url="https://lpdaac.usgs.gov/products/mod11a2v061/",
        citation="doi:10.5067/MODIS/MOD11A2.061"),
    "srtm": Dataset(
        id="srtm", name="NASADEM (SRTM retraité) v001", provider="NASA JPL / LP DAAC",
        variable="elevation", indicator="elevation", units="m",
        spatial_resolution="30 m (1 seconde d'arc)", temporal_resolution="statique (mission SRTM, 2000)",
        coverage="56°S–60°N", period_start="2000-02-11", period_end="2000-02-22",
        limitations=["Relief mesuré en 2000 : ne montre pas les changements récents",
                     "Altitude du sommet de la végétation et des bâtiments, pas toujours du sol"],
        source_url="https://lpdaac.usgs.gov/products/nasadem_hgtv001/",
        citation="doi:10.5067/MEaSUREs/NASADEM/NASADEM_HGT.001"),
}
IND2DS = {d.indicator: d.id for d in DATASETS.values()}
LABELS = {"precipitation": "Pluie du mois", "ndvi": "Verdure (NDVI)",
          "lst_day": "Température du sol", "elevation": "Altitude"}


def list_datasets() -> list[Dataset]:
    return list(DATASETS.values())


def get_dataset(dataset_id: str) -> Dataset:
    if dataset_id not in DATASETS:
        raise NotFound("dataset_not_found", f"Dataset introuvable : {dataset_id}")
    return DATASETS[dataset_id]


def dataset_for(indicator: str) -> Dataset:
    return DATASETS[IND2DS[indicator]]


# ─────────── Méta ───────────
def data_last_updated() -> str:
    """Dernier jour du dernier mois présent dans monthly.parquet (YYYY-MM-DD)."""
    last = store.last_date()
    if last is None:
        raise store.DataUnavailable("data_unavailable", "monthly.parquet ne contient aucune valeur")
    y, m = map(int, last.split("-"))
    return f"{y:04d}-{m:02d}-{calendar.monthrange(y, m)[1]:02d}"


def get_meta() -> AppMeta:
    return AppMeta(version=APP_VERSION, regions_count=len(REGION_IDS), data_last_updated=data_last_updated(), features=[
        Feature(id="map", title="Carte interactive du Togo", status="prototype"),
        Feature(id="chat", title="Assistant IA (texte)", status="prototype"),
        Feature(id="voice", title="AGBÉA Voice", status="in_development"),
        Feature(id="ewe", title="Langue éwé", status="planned"),
    ])


# ─────────── Types d'utilisateurs ───────────
PROFILES: list[Profile] = [
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


def list_profiles() -> list[Profile]:
    return PROFILES


# ─────────── Indicateurs ───────────
INDICATORS: list[Indicator] = [
    Indicator(id="precipitation", label="Pluie", units="mm", dataset_id="gpm_imerg", layer_id="precipitation",
              description_public="Quantité de pluie tombée, vue par satellite.",
              description_scientific="Précipitations GPM IMERG Final Run V07, cumul mensuel, grille 0.1°.", has_timeseries=True),
    Indicator(id="ndvi", label="Verdure de la végétation", units="", dataset_id="modis_ndvi", layer_id="ndvi",
              description_public="Plus la valeur est haute, plus la terre est verte.",
              description_scientific="NDVI MODIS MOD13A1 v061, composites 16 jours à 500 m agrégés au mois.", has_timeseries=True),
    Indicator(id="lst_day", label="Température du sol", units="°C", dataset_id="modis_lst", layer_id="lst_day",
              description_public="Chaleur de la surface du sol en journée.",
              description_scientific="LST diurne MODIS MOD11A2 v061, composites 8 jours à 1 km agrégés au mois.", has_timeseries=True),
    Indicator(id="elevation", label="Altitude", units="m", dataset_id="srtm",
              description_public="Hauteur du terrain : zones basses et pentes.",
              description_scientific="MNT NASADEM (SRTM retraité), 30 m.", has_timeseries=False),
]


def list_indicators() -> list[Indicator]:
    return INDICATORS


# ─────────── Couches de carte (M13) ───────────
# Tuiles NASA GIBS, WMTS EPSG:3857. Identifiants, TileMatrixSet et dates vérifiés le 2026-11-14 sur
# https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/1.0.0/WMTSCapabilities.xml (tuiles HTTP 200 sur le Togo).
# Le TileMatrixSet dépend de la couche : au-delà de max_zoom, GIBS répond 400. Une date sans image
# dans une plage renvoie la période précédente ; une date après la fin de plage renvoie 404.
# Palettes : https://gibs.earthdata.nasa.gov/colormaps/v1.3/<colormap>.xml
GIBS = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/{layer}/default/{date}/{tms}/{z}/{y}/{x}.png"


def _gibs(layer: str, tms: str) -> str:
    return GIBS.replace("{layer}", layer).replace("{tms}", tms)


def _periodic(first_year: int, last: str, step_days: int) -> list[str]:
    """Dates de composites GIBS : chaque année repart du 1er janvier, pas de `step_days` jours."""
    end = date.fromisoformat(last)
    out = []
    for year in range(first_year, end.year + 1):
        d = date(year, 1, 1)
        while d.year == year and d <= end:
            out.append(d.isoformat())
            d += timedelta(days=step_days)
    return out


def _daily(last: str, days: int) -> list[str]:
    end = date.fromisoformat(last)
    return [(end - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]


NDVI_LAST, LST_LAST, IMERG_LAST = "2026-10-16", "2026-11-01", "2026-11-13"

LAYERS: list[MapLayer] = [
    # MODIS Terra MOD13Q1 (250 m), composite 16 jours ; série de l'API : MOD13A1 (500 m), même indice
    MapLayer(id="ndvi", indicator="ndvi", dataset_id="modis_ndvi",
             title="Verdure de la végétation (NDVI, MODIS Terra, 16 jours)",
             type="wmts", url_template=_gibs("MODIS_Terra_L3_NDVI_16Day", "GoogleMapsCompatible_Level9"),
             available_dates=_periodic(2016, NDVI_LAST, 16), default_date=NDVI_LAST, max_zoom=9,
             legend=[LegendStop(value=0.05, color="#e1d9d5", label="Sol nu"),
                     LegendStop(value=0.2, color="#b09b8a"),
                     LegendStop(value=0.4, color="#8fb716"),
                     LegendStop(value=0.6, color="#3e8a01"),
                     LegendStop(value=0.8, color="#086701", label="Très vert")]),
    # GPM IMERG, intensité de pluie journalière (mm/h) — la série de l'API est un cumul mensuel (mm)
    MapLayer(id="precipitation", indicator="precipitation", dataset_id="gpm_imerg",
             title="Intensité de pluie (IMERG, journalier, mm/h)",
             type="wmts", url_template=_gibs("IMERG_Precipitation_Rate", "GoogleMapsCompatible_Level6"),
             available_dates=_daily(IMERG_LAST, 90), default_date=IMERG_LAST, max_zoom=6,
             legend=[LegendStop(value=0.1, color="#00764e", label="0,1 mm/h"),
                     LegendStop(value=1, color="#c3e400", label="1 mm/h"),
                     LegendStop(value=2, color="#ffb006", label="2 mm/h"),
                     LegendStop(value=5, color="#ff4730", label="5 mm/h"),
                     LegendStop(value=10, color="#e70000", label="10 mm/h et plus")]),
    # MODIS Terra MOD11A2, température de surface de jour, composite 8 jours (palette en K, légende en °C)
    MapLayer(id="lst_day", indicator="lst_day", dataset_id="modis_lst",
             title="Température du sol en journée (MODIS Terra, 8 jours)",
             type="wmts", url_template=_gibs("MODIS_Terra_L3_Land_Surface_Temp_8Day_Day", "GoogleMapsCompatible_Level7"),
             available_dates=_periodic(2024, LST_LAST, 8), default_date=LST_LAST, max_zoom=7,
             legend=[LegendStop(value=0, color="#57ff34", label="0 °C"),
                     LegendStop(value=15, color="#b3ff00", label="15 °C"),
                     LegendStop(value=25, color="#f4ff00", label="25 °C"),
                     LegendStop(value=35, color="#ffd600", label="35 °C"),
                     LegendStop(value=45, color="#ffa600", label="45 °C et plus")]),
]


def list_layers(mode: Mode = "public") -> list[MapLayer]:
    return [l for l in LAYERS if mode in l.modes]


def get_layer(layer_id: str) -> MapLayer:
    layer = next((l for l in LAYERS if l.id == layer_id), None)
    if not layer:
        raise NotFound("layer_not_found", f"Couche introuvable : {layer_id}")
    return layer
