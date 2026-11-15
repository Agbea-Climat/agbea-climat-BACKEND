# Contrat de données : ce que le pipeline livre au backend

Le pipeline publie deux livrables, tous deux **régénérés en entier** à chaque exécution. Le backend ne doit rien y écrire.

1. **Livrable P2**, lu par l'API actuelle (`backend/`) au format de `MISSIONS.md` : `data/regions.geojson`, `data/processed/monthly.parquet`, `data/processed/static.json` (étape `export-backend`, versionné).
2. **Livrable complet** `data/api/` (étape `export`, non versionné) : toutes les unités (régions, préfectures, cantons, sites), tous les indicateurs, tendances, fiches, couches raster. Il sert au front de test et aux missions futures.

## Livrable P2 (API actuelle)

### `data/regions.geojson`

FeatureCollection de 5 polygones (limites officielles geodata.gouv.tg via MAP TOGO, simplifiées à ~50 m), du sud au nord. Chaque `properties` contient :

| Champ | Exemple | Note |
|---|---|---|
| `id` | `maritime` | `maritime, plateaux, centrale, kara, savanes` |
| `name`, `capital` | `Maritime`, `Lomé` | |
| `centroid` | `[1.27867, 6.50428]` | `[lon, lat]`, calculé en UTM 31N |
| `bbox` | `[0.7157, 6.11177, 1.80841, 6.91027]` | `[minLon, minLat, maxLon, maxLat]` |
| `area_km2` | `6372.9` | UTM 31N |
| `unit_id`, `hdx_pcode` | `TG-A`, `TG03` | traçabilité (hors schéma `Region`) |

### `data/processed/monthly.parquet`

| Colonne | Type | Description |
|---|---|---|
| `region_id` | str | `maritime` … `savanes` |
| `indicator` | str | `precipitation` (IMERG, mm/mois), `ndvi`, `lst_day` (°C) |
| `date` | str `YYYY-MM` | 2001-01 → dernier mois **complet** (pluie : IMERG Final, 3 à 4 mois de latence en temps normal ; série arrêtée en 2025-09 le 15/11). Le mois en cours n'est jamais publié ; le mois précédent ne l'est que si tous ses composites MODIS sont parus (D28) |
| `value` | float \| null | moyenne pondérée des pixels **visibles** de la région, arrondie (pluie 1 déc., NDVI 3, LST 1). `null` seulement si aucun pixel n'est visible |
| `valid_frac` | float 0–1 | part de la région couverte par des pixels valides (les nuages font baisser NDVI et LST) |
| `low_coverage` | bool | `valid_frac < 0,5` : valeur peu représentative, **à signaler à l'utilisateur** |
| `dataset_id` | str | `gpm_imerg`, `modis_ndvi`, `modis_lst` (ids de `backend/services/catalog.py`) |

Différence avec `data/api/tables/monthly` : là-bas, `value` est mise à `null` dès que `valid_frac < 0,5`. Dans P2, la valeur est gardée avec `low_coverage`, parce que l'API doit répondre chaque mois (ex. Kara, août 2024 : 14 % visible).

### `data/processed/static.json`

```json
{"generated_at": "…", "dataset_id": "srtm", "units": "m",
 "regions": {"maritime": {"elevation": {"mean": 63.8, "min": -13.7, "max": 176.0, "p10": 11.8, "median": 62.8, "p90": 117.2, "pct_below_10m": 8.89}}, "…": {}}}
```

`min` peut être négatif sur la côte (bruit du MNT sur les lagunes) : préférer `p10` pour un « point bas ».

## Livrable complet `data/api/`

Version du contrat : **0.2** (pipeline 0.1.0). Tout changement de nom de champ ou de fichier est noté dans `changelogs/`.

> **0.2 (14/11/2026)** : les régions et préfectures viennent des limites officielles MAP TOGO / geodata.gouv.tg (39 préfectures). Leurs identifiants deviennent `TG-A`, `TG-A01`… Une colonne `hdx_pcode` donne l'équivalent OCHA (anciens identifiants `TG03`, `TG0303`…).

## Vue d'ensemble

```
data/api/
├── catalog.json                 provenance : jeux de données, indicateurs, période de référence, couverture réelle
├── validation.json              contrôles automatiques (plages physiques, couverture, cohérences) : pass / warn / fail
├── units/
│   ├── country.geojson          1 polygone   (Togo)
│   ├── region.geojson           5 polygones  (TG-A…TG-E, limites officielles MAP TOGO)
│   ├── prefecture.geojson       39 polygones (TG-A01…)
│   ├── canton.geojson           373 polygones (P-codes HDX TG010101…)
│   └── site.geojson             7 sites pilotes (disque de 10 km découpé par la frontière)
├── tables/                      même contenu en .parquet (typé) et .csv (UTF-8)
│   ├── monthly                  1 ligne = unité × indicateur × mois
│   ├── seasonal                 1 ligne = unité × indicateur × saison × année
│   ├── climatology              1 ligne = unité × indicateur × mois calendaire (référence)
│   ├── trends                   1 ligne = unité × indicateur × saison
│   ├── elevation                1 ligne = unité
│   └── rainfall_30d             1 ligne = unité (présent seulement avec un compte Earthdata)
├── summaries/
│   ├── index.json               liste des fiches
│   └── <unit_id>.json           fiche prête à afficher (pays, régions, préfectures, sites)
└── layers/<indicateur>/         GeoTIFF EPSG:4326
    ├── <année>.tif              agrégat annuel par pixel
    ├── baseline.tif             moyenne de la période de référence
    └── anomaly_<année>.tif      dernière année complète − référence
```

## Identifiants

| Niveau | `unit_id` | Exemple | `hdx_pcode` | Source |
|---|---|---|---|---|
| country | `TG` | `TG` | `TG` | MAP TOGO (union des régions) |
| region | `TG-` + code MAP TOGO | `TG-A` (Maritime) | `TG03` | MAP TOGO / geodata.gouv.tg |
| prefecture | `TG-` + code MAP TOGO | `TG-A04` (Golfe) | `TG0303` | MAP TOGO / geodata.gouv.tg |
| canton | P-code adm3 | `TG030501` | identique | COD-AB HDX |
| site | slug | `lome`, `aneho`, `kpalime`, `sokode`, `kara`, `dapaong`, `mango-oti` | — | `pipeline/settings/sites.yaml` |

Codes des régions : A = Maritime, B = Plateaux, C = Centrale, D = Kara, E = Savanes.

Les slugs des sites sont **les mêmes que dans l'ancien front** (`agbea-climat.vercel.app`) : la jointure se fait sans table de correspondance.

`parent_id` relie chaque unité à son niveau supérieur. Un site pointe vers la préfecture qui contient son centre ; un canton HDX pointe vers la préfecture officielle qui le recouvre le plus, car les deux découpages ne s'emboîtent pas exactement.

`hdx_pcode` est l'équivalent OCHA, obtenu par recouvrement maximal. Il sert à croiser avec des jeux de données humanitaires indexés par P-code. Remarque : HDX compte 40 préfectures (« Lomé Commune » à part), contre 39 dans le découpage officiel, où elle fait partie de Golfe.

La source des limites se règle dans `pipeline/settings/settings.yaml → boundaries.admin_source` (`map_togo` par défaut, `hdx` en repli).

## Indicateurs

| `indicator` | Libellé | Unité | Pas | Source | `nature` |
|---|---|---|---|---|---|
| `rainfall` | Pluie | mm (cumul) | mois | GPM IMERG Final V07 | observed |
| `rainfall_30d` | Pluie des 30 derniers jours | mm | glissant | GPM IMERG Late V07 | observed |
| `ndvi` | Indice de végétation | sans unité (−1 à 1) | mois | MODIS MOD13A1 v061 | observed |
| `lst_day` | Température de surface, jour (~10 h 30) | °C | mois | MODIS MOD11A2 v061 | observed |
| `lst_night` | Température de surface, nuit (~22 h 30) | °C | mois | MODIS MOD11A2 v061 | observed |
| `air_temp` | Température de l'air à 2 m | °C | mois | NASA POWER / MERRA-2 | derived |
| `rainfall_merra2` | Pluie (réanalyse, contrôle) | mm | mois | NASA POWER / MERRA-2 | derived |
| `elevation` | Altitude | m | statique | NASADEM | observed |

`air_temp` et `rainfall_merra2` n'existent **que pour les 7 sites** (API POWER par point).

Le catalogue (`catalog.json → indicators`) liste aussi `lst_day_aqua` et `lst_night_aqua` avec `control: true` : ce sont des indicateurs de **contrôle** (MODIS Aqua, étape `control-lst`), absents des tables, fiches et couches. Le backend doit ignorer tout indicateur `control: true`.

`nature` reprend la règle du pitch (slide 10) : **observed** = mesure satellite ; **derived** = calcul ou réanalyse. Le pipeline ne produit **jamais** d'`interpreted` ni de `predicted` : ces deux catégories relèvent du backend et de l'IA, et doivent rester séparées à l'affichage.

## Tables

### `monthly`

| Colonne | Type | Description |
|---|---|---|
| `unit_id` | str | voir Identifiants |
| `indicator` | str | voir Indicateurs |
| `date` | str `AAAA-MM` | mois |
| `year`, `month` | int | |
| `value` | float \| null | moyenne pondérée sur l'unité (cumul pour la pluie). **null** si `valid_frac` < 0,5 |
| `valid_frac` | float 0–1 | part de la surface de l'unité couverte par des pixels valides (nuages, qualité) |
| `clim_mean` | float | moyenne du même mois sur la période de référence 2001-2020 |
| `anomaly` | float | `value − clim_mean` (unité de l'indicateur) |
| `anomaly_pct` | float \| null | pluie seulement : `(value / clim_mean − 1) × 100` |

### `seasonal`

| Colonne | Description |
|---|---|
| `season` | `annual` (12 mois), `jfm` (janv.-mars, saison sèche), `mjjaso` (mai-oct., saison des pluies) |
| `year` | année |
| `value` | cumul (pluie) ou moyenne (autres). **null** si la saison est incomplète ou pas encore terminée |
| `n_months`, `n_months_expected` | mois valides / attendus |
| `baseline_mean`, `anomaly`, `anomaly_pct` | idem `monthly`, au niveau de la saison |

Règles de complétude (`pipeline/settings/settings.yaml`) : pluie = tous les mois ; NDVI/LST annuels = au moins 10 mois sur 12 ; saisons de plus de 3 mois = au plus 1 mois manquant ; l'année en cours n'est jamais agrégée.

### `climatology`

`unit_id, indicator, month, clim_mean, clim_std, n, baseline`. C'est la courbe « moyenne historique » des graphiques (slides 6 et 10).

### `trends`

| Colonne | Description |
|---|---|
| `season` | saison testée |
| `n_years`, `first_year`, `last_year` | années utilisées (au moins 10) |
| `period_mean` | moyenne de la saison sur ces années |
| `sen_slope_per_decade` | pente de Theil-Sen, unité de l'indicateur par décennie |
| `sen_ci95_low_per_decade`, `sen_ci95_high_per_decade` | intervalle de confiance à 95 % de la pente |
| `sen_slope_pct_per_decade` | pluie seulement : pente en % de la moyenne |
| `kendall_tau`, `p_value` | test de Mann-Kendall |
| `significant` | `p_value < 0.05` |
| `direction` | `hausse` / `baisse` / `pas de tendance significative` |

**LST** (`lst_day`, `lst_night`) : les tendances s'arrêtent à **2020** (`last_year = 2020`), à cause de la dérive d'orbite de Terra (D27). Les séries mensuelles et annuelles, elles, vont jusqu'au dernier mois disponible.

**Règle d'affichage** : ne parler de « tendance » que si `significant = true`. Sinon, dire « pas de tendance nette sur la période ». C'est l'exigence n° 7 du guide d'équipe.

### `elevation`

`unit_id, mean, min, p10, median, p90, max, pct_below_5m, pct_below_10m`, en mètres et en %. Seuls les pixels dont le centre tombe dans l'unité sont comptés.

`min` peut être négatif sur la côte (jusqu'à −14 m dans la région Maritime). C'est du bruit du MNT sur les lagunes et zones humides, et non une altitude réelle. Pour un « point bas », afficher `p10`.

### `rainfall_30d`

`unit_id, value, valid_frac, normal_mm, anomaly_pct, start, end`. La normale est la climatologie mensuelle IMERG Final ramenée au jour, puis sommée sur les 30 jours.

## Fiches `summaries/<unit_id>.json`

Une fiche contient tout ce qu'un écran « lieu » affiche, sans requête supplémentaire :

```jsonc
{
  "unit": {"id": "lome", "level": "site", "name": "Grand Lomé & Lagune", "parent_id": "TG-A04",
           "area_km2": 139.59, "centroid": [1.21, 6.17]},
  "elevation_m": {"mean": 18.2, "min": 0.0, "max": 45.0, "pct_below_10m": 21.3, ...},
  "latest": {                                    // dernière valeur disponible par indicateur
    "ndvi":   {"date": "2026-10", "value": 0.41, "clim_mean": 0.44, "anomaly": -0.03,
               "valid_frac": 0.93, "unit": "sans unité (-1 à 1)", "dataset": "modis_ndvi", "nature": "observed"},
    "rainfall_30d": {"start": "2026-10-14", "end": "2026-11-12", "value": 85.0, "normal": 92.1, ...}
  },
  "annual":  {"ndvi": [{"year": 2001, "value": 0.45, "anomaly": 0.01, "anomaly_pct": null, "n_months": 12}, ...]},
  "trends":  {"ndvi": {"annual": {"sen_slope_per_decade": 0.012, "p_value": 0.03, "significant": true, ...}}},
  "recent_monthly": {"ndvi": [{"date": "2024-11", "value": 0.42, "clim_mean": 0.43, ...}, ...]}  // 24 derniers mois
}
```

(Les valeurs ci-dessus illustrent la forme, ce ne sont pas des résultats.)

`dataset` renvoie à une clé de `catalog.json → datasets` : le backend y trouve titre, DOI, résolution, période et limites à afficher (slide 10 : SOURCE · DATES · RÉSOLUTION · UNITÉS · LIMITES).

### Correspondance avec l'ancien front

Le front et le backend sont en cours de réécriture (décision D13) : cette table sert de référence pour retrouver les équivalents. Les slugs de sites sont conservés.

L'ancien front déployé attendait `latestObservations` et une série annuelle (`vI`). Correspondance :

| Champ du front | Source dans la fiche | Remarque |
|---|---|---|
| `rainfall30dMm` | `latest.rainfall_30d.value` | nécessite IMERG journalier (compte Earthdata) |
| `rainfallAnomalyPct` | `latest.rainfall_30d.anomaly_pct` | |
| `lstSurfaceCelsius` | `latest.lst_day.value` | moyenne mensuelle, pas un instantané |
| `airTemp2mCelsius` | `latest.air_temp.value` | sites seulement ; réanalyse |
| `ndviCurrent` | `latest.ndvi.value` | |
| `ndviHistoricalMean` | `latest.ndvi.clim_mean` | même mois, 2001-2020 |
| `elevationM` | `elevation_m.mean` | |
| `floodRiskScore`, `droughtIndex` | **aucune** | scores composites sans méthode documentée : à retirer ou à définir (voir notes/) |
| `coastalRetreatRateMPerYr`, `coastalShorelineDisplacementM` | **aucune** pour l'instant | demande une extraction du trait de côte Landsat, pas encore faite |
| série `vI[].rainfallMm` | `annual.rainfall[].value` | |
| série `vI[].rainfallAnomalyPct` | `annual.rainfall[].anomaly_pct` | |
| série `vI[].lstCelsius` | `annual.lst_day[].value` | ou saison `jfm` (ciel clair) via `tables/seasonal` |
| série `vI[].airTempCelsius` | `annual.air_temp[].value` | |
| série `vI[].ndvi` | `annual.ndvi[].value` | |

## Couches raster `layers/`

- GeoTIFF tuilés, compression deflate, `nodata = NaN`, EPSG:4326, emprise −0,3 → 2,0 °E, 6,0 → 11,3 °N.
- Résolutions : pluie 0,1°, NDVI 0,005°, LST 0,01°, altitude 0,000833° (~90 m).
- Hors du Togo, les pixels **ne sont pas** masqués (contexte régional) ; découper avec `units/country.geojson` si besoin.
- Le backend peut les servir tels quels (titiler, rio-tiler) ou les convertir en PNG colorés pour le front.

## Exemples côté backend

Python / FastAPI :

```python
import json, pandas as pd
monthly = pd.read_parquet("data/api/tables/monthly.parquet")
lome_ndvi = monthly.query("unit_id == 'lome' and indicator == 'ndvi'")
fiche = json.load(open("data/api/summaries/lome.json", encoding="utf-8"))
```

Node : lire les `.csv` ou les fiches JSON ; pour PostgreSQL, `COPY monthly FROM 'monthly.csv' CSV HEADER`.
