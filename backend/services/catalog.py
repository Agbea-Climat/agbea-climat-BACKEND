"""Catalogue statique : méta, profils, datasets, indicateurs, couches de carte."""
from backend.core.constants import APP_VERSION
from backend.core.exceptions import NotFound
from backend.schemas import (AppMeta, Dataset, Feature, Indicator, LegendStop, MapLayer, Mode,
                             Profile)

from .regions import REGIONS

# ─────────── Datasets ───────────
# Faits alignés sur pipeline/settings/datasets.yaml (produits réellement utilisés par le pipeline P2).
# Les ids ne changent pas : ce sont les dataset_id de data/processed/.
DATASETS: dict[str, Dataset] = {
    "gpm_imerg": Dataset(
        id="gpm_imerg", name="NASA GPM IMERG Final Run V07 (mensuel, GPM_3IMERGM)", provider="NASA GES DISC",
        variable="precipitation", indicator="precipitation", units="mm",
        spatial_resolution="0.1° (~11 km)", temporal_resolution="mensuel",
        coverage="Global", period_start="1998-01-01",
        limitations=["Estimation satellite, pas une mesure de pluviomètre",
                     "Maille de ~11 km : une valeur représente une zone, pas un point précis",
                     "Final Run publié 3 à 4 mois après le mois observé, parfois plus : les derniers mois peuvent manquer",
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
        coverage="Global", period_start="2000-02-18",
        limitations=["Température de la surface du sol (toits, routes, champs), pas de l'air",
                     "Mesurée seulement par ciel clair : en saison des pluies, valeurs rares et biaisées vers les jours secs",
                     "Dérive d'orbite de Terra après 2020 : les tendances LST s'arrêtent à 2020 ; la hausse nocturne est confirmée par MODIS Aqua sur 2003-2020"],
        source_url="https://lpdaac.usgs.gov/products/mod11a2v061/",
        citation="doi:10.5067/MODIS/MOD11A2.061"),
    "srtm": Dataset(
        id="srtm", name="NASADEM (SRTM retraité) v001", provider="NASA JPL / LP DAAC",
        variable="elevation", indicator="elevation", units="m",
        spatial_resolution="30 m (1 seconde d'arc)", temporal_resolution="statique (mission SRTM, 2000)",
        coverage="56°S–60°N", period_start="2000-02-11", period_end="2000-02-21",
        limitations=["Relief mesuré en 2000 : ne montre pas les changements récents",
                     "Altitude du sommet de la végétation et des bâtiments, pas toujours du sol",
                     "Statistiques par région calculées sur une grille ré-échantillonnée à ~90 m"],
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
        raise NotFound("dataset_not_found", dataset_id)
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
              description_scientific="Précipitations GPM IMERG Final Run V07, cumul mensuel, grille 0.1°.", has_timeseries=True),
    Indicator(id="ndvi", label="Verdure de la végétation", units="", dataset_id="modis_ndvi", layer_id="ndvi",
              description_public="Plus la valeur est haute, plus la terre est verte.",
              description_scientific="NDVI MODIS MOD13A1 v061, composites 16 jours à 500 m agrégés au mois.", has_timeseries=True),
    Indicator(id="lst_day", label="Température du sol", units="°C", dataset_id="modis_lst",
              description_public="Chaleur de la surface du sol en journée.",
              description_scientific="LST diurne MODIS MOD11A2 v061, composites 8 jours à 1 km agrégés au mois.", has_timeseries=True),
    Indicator(id="elevation", label="Altitude", units="m", dataset_id="srtm",
              description_public="Hauteur du terrain : zones basses et pentes.",
              description_scientific="MNT NASADEM (SRTM retraité), 30 m.", has_timeseries=False),
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
        raise NotFound("layer_not_found", layer_id)
    return layer
