"""Catalogue statique : méta, profils, datasets, indicateurs, couches de carte."""
from backend.core.constants import APP_VERSION
from backend.core.exceptions import NotFound
from backend.schemas import (AppMeta, Dataset, Feature, Indicator, LegendStop, MapLayer, Mode,
                             Profile)

from .regions import REGIONS

# ─────────── Datasets ───────────
DATASETS: dict[str, Dataset] = {
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


def list_datasets() -> list[Dataset]:
    return list(DATASETS.values())


def get_dataset(dataset_id: str) -> Dataset:
    if dataset_id not in DATASETS:
        raise NotFound("dataset_not_found", f"Dataset introuvable : {dataset_id}")
    return DATASETS[dataset_id]


def dataset_for(indicator: str) -> Dataset:
    return DATASETS[IND2DS[indicator]]


# ─────────── Méta ───────────
def get_meta() -> AppMeta:
    # TODO M02 (après P2) : data_last_updated = dernier mois de monthly.parquet
    return AppMeta(version=APP_VERSION, regions_count=len(REGIONS), data_last_updated="2026-10-31", features=[
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


def list_indicators() -> list[Indicator]:
    return INDICATORS


# ─────────── Couches de carte ───────────
# TODO M13 : vérifier les identifiants exacts dans le catalogue GIBS (worldview.earthdata.nasa.gov)
GIBS = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/{layer}/default/{date}/GoogleMapsCompatible_Level9/{z}/{y}/{x}.png"
LAYERS: list[MapLayer] = [
    MapLayer(id="ndvi", indicator="ndvi", dataset_id="modis_ndvi", title="Verdure de la végétation",
             type="wmts", url_template=GIBS.replace("{layer}", "MODIS_Terra_NDVI_16Day"),
             available_dates=["2026-09-14"], default_date="2026-09-14",
             legend=[LegendStop(value=0, color="#d8c48f", label="Sol nu"),
                     LegendStop(value=0.8, color="#1a7f37", label="Très vert")]),
    MapLayer(id="precipitation", indicator="precipitation", dataset_id="gpm_imerg", title="Pluie",
             type="wmts", url_template=GIBS.replace("{layer}", "IMERG_Precipitation_Rate"),
             available_dates=["2026-09-30"], default_date="2026-09-30",
             legend=[LegendStop(value=0, color="#e0f3ff"), LegendStop(value=300, color="#08306b")]),
]


def list_layers(mode: Mode = "public") -> list[MapLayer]:
    return [l for l in LAYERS if mode in l.modes]


def get_layer(layer_id: str) -> MapLayer:
    layer = next((l for l in LAYERS if l.id == layer_id), None)
    if not layer:
        raise NotFound("layer_not_found", f"Couche introuvable : {layer_id}")
    return layer
