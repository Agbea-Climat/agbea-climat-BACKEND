"""Catalogue statique : méta, profils, datasets, indicateurs, couches de carte."""
import calendar
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from typing import Optional

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
        coverage="Global", period_start="2000-02-18", period_end="2022-12-31",
        limitations=["Température de la surface du sol (toits, routes, champs), pas de l'air",
                     "Mesurée seulement par ciel clair : en saison des pluies, valeurs rares et biaisées vers les jours secs",
                     "Valeurs publiées jusqu'en décembre 2022 : ensuite, la dérive d'orbite de Terra (passage plus matinal) "
                     "fausse les mesures (écart avec MODIS Aqua de −0,75 °C en 2023 à −1,56 °C en 2025)",
                     "Tendances calculées jusqu'en 2020 ; la hausse nocturne est confirmée par MODIS Aqua sur 2003-2020"],
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


def _month_end(month: str) -> str:
    y, m = map(int, month.split("-"))
    return f"{y:04d}-{m:02d}-{calendar.monthrange(y, m)[1]:02d}"


def _with_series_end(ds: Dataset) -> Dataset:
    """Dataset à série (pluie, NDVI, température) : period_end = dernier jour du dernier mois présent
    dans monthly.parquet (store.last_dates()), pour que la fiche dise où la série de l'API s'arrête
    (pluie IMERG Final publiée avec retard, température arrêtée en 2022-12). Données absentes → fiche statique."""
    try:
        last = store.last_dates().get(ds.indicator)
    except store.DataUnavailable:
        return ds
    return ds.model_copy(update={"period_end": _month_end(last)}) if last else ds


def list_datasets() -> list[Dataset]:
    return [_with_series_end(d) for d in DATASETS.values()]


def get_dataset(dataset_id: str) -> Dataset:
    if dataset_id not in DATASETS:
        raise NotFound("dataset_not_found", f"Dataset introuvable : {dataset_id}")
    return _with_series_end(DATASETS[dataset_id])


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
    # data_last_updated : toutes séries confondues (M02) ; le détail par indicateur dit où chaque série
    # s'arrête (pluie IMERG Final publiée avec retard, température du sol arrêtée en 2022-12, D30)
    return AppMeta(version=APP_VERSION, regions_count=len(REGION_IDS), data_last_updated=data_last_updated(),
                   data_last_updated_by_indicator=store.last_dates(), features=[
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
# Tuiles NASA GIBS, WMTS EPSG:3857 (endpoint « best » : meilleure version disponible du produit).
# Le TileMatrixSet dépend de la couche : au-delà de max_zoom, GIBS répond 400. Une date sans image
# dans une plage renvoie la période précédente ; une date hors des plages renvoie 404.
# Palettes : https://gibs.earthdata.nasa.gov/colormaps/v1.3/<colormap>.xml
#
# Dates disponibles (aucun appel réseau pendant une requête) :
# - NDVI et LST : copie des plages <Dimension><Value> (début/fin/pas ISO 8601) de
#   https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/1.0.0/WMTSCapabilities.xml, relevées le
#   GIBS_CHECKED, jamais extrapolées : le calendrier des composites a des trous (ex. LST : pas d'image
#   le 2025-12-03 ni le 2026-01-01) et une date après la fin de plage renvoie 404. Mise à jour :
#   relever les <Value> dans le fichier ci-dessus, les recopier ici et changer GIBS_CHECKED.
# - Pluie IMERG (image quotidienne) : fenêtre glissante des IMERG_DAYS derniers jours, calculée à
#   chaque requête depuis la date UTC, jusqu'à J-IMERG_LATENCY_DAYS. Latence observée le 2026-11-15
#   à 10 h UTC : 13/11 servi (200), 14/11 pas encore (404). Les trous connus du relevé (IMERG_GAPS)
#   sont retirés ; un trou plus récent que le relevé n'est pas connu (GIBS renverrait 404).
GIBS = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/{layer}/default/{date}/{tms}/{z}/{y}/{x}.png"
GIBS_CHECKED = "2026-11-15"

NDVI_RANGES = ("2016-01-01/2016-12-18/P16D", "2017-01-01/2017-12-19/P16D", "2018-01-01/2018-12-19/P16D",
               "2019-01-01/2019-12-19/P16D", "2020-01-01/2020-12-18/P16D", "2021-01-01/2021-12-19/P16D",
               "2022-01-01/2022-12-19/P16D", "2023-01-01/2023-12-19/P16D", "2024-01-01/2024-12-18/P16D",
               "2025-01-01/2025-12-19/P16D", "2026-01-01/2026-10-16/P16D")
# Température du sol : arrêtée à 2022 comme les valeurs de l'API (dataset modis_lst, décision D30 :
# dérive d'orbite de Terra ensuite). GIBS sert des images plus récentes, volontairement non proposées.
LST_RANGES = ("2016-01-01/2016-12-26/P8D", "2017-01-01/2017-12-27/P8D", "2018-01-01/2018-12-27/P8D",
              "2019-01-01/2019-12-27/P8D", "2020-01-01/2020-12-26/P8D", "2021-01-01/2021-12-27/P8D",
              "2022-01-01/2022-12-27/P8D")
# Relevé IMERG (contrôle) : les jours absents entre ces plages sont des trous de GIBS
IMERG_RANGES = ("2025-10-30/2026-01-07/P1D", "2026-01-09/2026-02-02/P1D", "2026-02-04/2026-02-09/P1D",
                "2026-02-12/2026-05-24/P1D", "2026-05-27/2026-11-13/P1D")
IMERG_DAYS = 90          # derniers jours proposés
IMERG_LATENCY_DAYS = 2   # dernière image quotidienne publiée : J-2 (UTC)


def _gibs(layer: str, tms: str) -> str:
    return GIBS.replace("{layer}", layer).replace("{tms}", tms)


def _expand(ranges: tuple[str, ...], last: Optional[int] = None) -> list[str]:
    """Dates (YYYY-MM-DD) des plages GIBS « début/fin/PnD », dans l'ordre ; `last` = n dernières."""
    out = []
    for r in ranges:
        start, end, period = r.split("/")
        d, stop, step = date.fromisoformat(start), date.fromisoformat(end), timedelta(days=int(period[1:-1]))
        while d <= stop:
            out.append(d.isoformat())
            d += step
    return out[-last:] if last else out


NDVI_DATES, LST_DATES = _expand(NDVI_RANGES), _expand(LST_RANGES)
_IMERG_KNOWN = _expand(IMERG_RANGES)
# Jours du relevé sans image (ex. 2026-02-10, 2026-05-25)
IMERG_GAPS = frozenset(set(_expand((f"{_IMERG_KNOWN[0]}/{_IMERG_KNOWN[-1]}/P1D",))) - set(_IMERG_KNOWN))


def imerg_dates(today: date) -> list[str]:
    """Fenêtre glissante IMERG : IMERG_DAYS jours jusqu'à today − IMERG_LATENCY_DAYS, trous connus retirés."""
    last = today - timedelta(days=IMERG_LATENCY_DAYS)
    days = (last - timedelta(days=i) for i in range(IMERG_DAYS - 1, -1, -1))
    return [d.isoformat() for d in days if d.isoformat() not in IMERG_GAPS]


LAYERS: list[MapLayer] = [
    MapLayer(id="ndvi", indicator="ndvi", dataset_id="modis_ndvi",
             title="Verdure de la végétation (NDVI, MODIS Terra 250 m, 16 jours)",
             description="Tuiles NASA GIBS MODIS_Terra_L3_NDVI_16Day : produit MOD13Q1 v061 (MODIS Terra, 250 m, "
                         "composite 16 jours). Les chiffres et séries de l'API viennent de MOD13A1 v061 (même indice, "
                         "500 m, agrégé au mois) : la carte est plus détaillée que les valeurs par région.",
             type="wmts", url_template=_gibs("MODIS_Terra_L3_NDVI_16Day", "GoogleMapsCompatible_Level9"),
             available_dates=NDVI_DATES, default_date=NDVI_DATES[-1], max_zoom=9,
             legend=[LegendStop(value=0.05, color="#e1d9d5", label="Sol nu"),
                     LegendStop(value=0.2, color="#b09b8a"),
                     LegendStop(value=0.4, color="#8fb716"),
                     LegendStop(value=0.6, color="#3e8a01"),
                     LegendStop(value=0.8, color="#086701", label="Très vert")]),
    MapLayer(id="precipitation", indicator="precipitation", dataset_id="gpm_imerg",
             title="Intensité de pluie (IMERG demi-horaire, mm/h, 90 derniers jours)",
             description="Tuiles NASA GIBS IMERG_Precipitation_Rate : intensité de pluie en mm/h, une image par jour, "
                         "issue du produit demi-horaire GPM IMERG V07 (Early Run GPM_3IMERGHHE en quasi temps réel, "
                         "Final Run GPM_3IMERGHH quand il est publié). Ce n'est pas le cumul mensuel en mm des séries "
                         "de l'API (IMERG Final Run mensuel, GPM_3IMERGM).",
             type="wmts", url_template=_gibs("IMERG_Precipitation_Rate", "GoogleMapsCompatible_Level6"),
             available_dates=_IMERG_KNOWN[-IMERG_DAYS:], default_date=_IMERG_KNOWN[-1], max_zoom=6,  # remplacé par _layers()
             legend=[LegendStop(value=0.1, color="#00764e", label="0,1 mm/h"),
                     LegendStop(value=1, color="#c3e400", label="1 mm/h"),
                     LegendStop(value=2, color="#ffb006", label="2 mm/h"),
                     LegendStop(value=5, color="#ff4730", label="5 mm/h"),
                     LegendStop(value=10, color="#e70000", label="10 mm/h et plus")]),
    # Palette GIBS en K, légende convertie en °C
    MapLayer(id="lst_day", indicator="lst_day", dataset_id="modis_lst",
             title="Température du sol en journée (MODIS Terra 1 km, 8 jours, 2016-2022)",
             description="Tuiles NASA GIBS MODIS_Terra_L3_Land_Surface_Temp_8Day_Day : produit MOD11A2 v061 (MODIS "
                         "Terra, 1 km, composite 8 jours), le même que les séries de l'API. Dates limitées à 2016-2022 "
                         "comme les valeurs de l'API : ensuite, la dérive d'orbite de Terra fausse les températures de jour.",
             type="wmts", url_template=_gibs("MODIS_Terra_L3_Land_Surface_Temp_8Day_Day", "GoogleMapsCompatible_Level7"),
             available_dates=LST_DATES, default_date=LST_DATES[-1], max_zoom=7,
             legend=[LegendStop(value=0, color="#57ff34", label="0 °C"),
                     LegendStop(value=15, color="#b3ff00", label="15 °C"),
                     LegendStop(value=25, color="#f4ff00", label="25 °C"),
                     LegendStop(value=35, color="#ffd600", label="35 °C"),
                     LegendStop(value=45, color="#ffa600", label="45 °C et plus")]),
]


@lru_cache(maxsize=2)
def _layers_for(today: date) -> tuple[MapLayer, ...]:
    """Couches du jour : la pluie reçoit sa fenêtre glissante, les autres gardent le relevé figé."""
    def dated(l: MapLayer) -> MapLayer:
        if l.id != "precipitation":
            return l
        dates = imerg_dates(today)
        return l.model_copy(update={"available_dates": dates, "default_date": dates[-1]})
    return tuple(dated(l) for l in LAYERS)


def _layers() -> tuple[MapLayer, ...]:
    return _layers_for(datetime.now(timezone.utc).date())


def list_layers(mode: Mode = "public") -> list[MapLayer]:
    return [l for l in _layers() if mode in l.modes]


def get_layer(layer_id: str) -> MapLayer:
    layer = next((l for l in _layers() if l.id == layer_id), None)
    if not layer:
        raise NotFound("layer_not_found", f"Couche introuvable : {layer_id}")
    return layer
