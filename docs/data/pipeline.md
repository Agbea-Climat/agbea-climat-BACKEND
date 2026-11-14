# Pipeline de données : installation, exécution, architecture

Le pipeline (`pipeline/`) est le **prérequis P2** du backend (voir `MISSIONS.md`). Il remplace l'export Google Earth Engine prévu au départ (`scripts/export_gee.py`) et lit les données directement à la NASA (GES DISC, LP DAAC) ou via ses copies (Planetary Computer), puis écrit dans `data/`.

## Avec Docker (méthode de l'équipe)

```powershell
copy .env.example .env                                # mettre EARTHDATA_TOKEN (voir acces-donnees.md)
docker compose build pipeline
docker compose run --rm pipeline all                  # tout, dans l'ordre (≈ 1 h la première fois)
docker compose run --rm pipeline <étape> [--start AAAA --end AAAA] [--force]
docker compose --profile test run --rm pipeline-tests # tests hors réseau
```

Voir `docs/docker.md` pour l'ensemble des services, et le contournement DNS si `docker build` échoue sur PyPI.

## Sans Docker (développement)

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt     # API + pipeline
# ou seulement le pipeline, versions exactes : -r requirements/pipeline.lock
.venv\Scripts\python -m pipeline <étape>
.venv\Scripts\python -m pytest pipeline/tests
```

`requirements/pipeline.txt` donne les dépendances directes avec leurs bornes ; `requirements/pipeline.lock` donne les versions exactes testées, et c'est lui que Docker utilise. Après une mise à jour volontaire des dépendances, régénérer le lock avec `pip freeze`, en ne gardant que les paquets du pipeline.

## Étapes

| Étape | Rôle | Durée constatée | Reprise |
|---|---|---|---|
| `boundaries [--map-togo-dir DIR] [--hdx-dir DIR]` | limites versionnées (`data/reference/map_togo/` pour le pays, les régions et les préfectures ; `data/reference/hdx/` pour les cantons) → `data/interim/work/units.gpkg` (425 unités). Les options remplacent les fichiers de référence | 5 s | refait tout |
| `power` | NASA POWER par site → `data/raw/power/` | 10 s | saute les sites déjà présents |
| `dem` | NASADEM → `data/interim/static/elevation.tif` | ~2 min | saute si présent |
| `ndvi` | MOD13A1 → `data/interim/cubes/ndvi/AAAA-MM.tif` (trous comblés depuis LP DAAC) | ~75 s / an | saute les mois présents, sauf les 2 derniers |
| `lst` | MOD11A2 → `cubes/lst_day/`, `cubes/lst_night/` | ~2-3 min / an | idem |
| `imerg` | IMERG mensuel → `data/raw/imerg_monthly/` puis `cubes/rainfall/` | quelques minutes | saute les mois présents |
| `imerg-daily` | IMERG Late, 45 derniers jours → `data/raw/imerg_daily_late/` | < 1 min | fenêtre glissante |
| `analyse` | zonal + tables → `data/interim/work/tables/*.parquet` | ~1 min | refait tout |
| `export` | `data/api/` : livrable complet (voir contrat-donnees.md) | ~1 min | refait tout |
| `export-backend` | **livrable P2** : `data/regions.geojson`, `data/processed/monthly.parquet`, `data/processed/static.json` | 3 s | refait tout |

Mise à jour régulière (ex. hebdomadaire) : `ndvi --start <année courante>`, `lst --start <année courante>`, `imerg`, `imerg-daily`, `analyse`, `export`, `export-backend`.

## Architecture

```
pipeline/
  settings/             settings.yaml (paramètres), sites.yaml (sites pilotes), datasets.yaml (provenance)
  config.py             chemins + chargement YAML
  grid.py               grilles EPSG:4326 communes, écriture GeoTIFF atomique
  boundaries.py         unités d'analyse (MAP TOGO / HDX + disques des sites)
  zonal.py              poids de couverture des pixels (cache .npz), moyenne pondérée
  sources/
    http.py             reprises HTTP, session Earthdata (jeton limité aux hôtes NASA)
    imerg.py            OPeNDAP GES DISC : sous-ensemble Togo, lecture h5py
    modis.py            STAC Planetary Computer : lecture fenêtrée, QA, reprojection, mois
    modis_lpdaac.py     comblement des trous : CMR → HDF4 LP DAAC → pyhdf
    nasadem.py          mosaïque d'altitude
    power.py            API NASA POWER
  analysis.py           mensuel → saisons, climatologie, anomalies, Mann-Kendall / Sen
  export.py             data/api/ : tables, fiches JSON, GeoJSON, couches, catalogue
  backend_export.py     livrable P2 au format attendu par backend/
  validate.py           contrôles automatiques → data/api/validation.json
  __main__.py           CLI : python -m pipeline <étape>
  tests/                tests hors réseau (pytest pipeline/tests)
data/
  reference/            limites administratives (versionné)
  regions.geojson       ┐
  processed/            ┘ livrable P2 (versionné)
  raw/                  téléchargements bruts (non versionné)
  interim/cubes/        un GeoTIFF par indicateur et par mois (non versionné)
  interim/work/         unités, poids, tables de travail (non versionné)
  api/                  livrable complet : fiches, tables, couches (non versionné, régénérable)
```

### Principes

- **Idempotent et reprenable** : chaque fichier est écrit de façon atomique (`.tmp` puis renommage). Une étape interrompue reprend là où elle s'est arrêtée.
- **Pas de magie** : une seule grille par indicateur, une seule règle de complétude, toutes dans `pipeline/settings/settings.yaml`.
- **Traçabilité** : chaque GeoTIFF porte en tags sa source, son année, son mois et son nombre de composites. `catalog.json` reprend `datasets.yaml`.
- **Séparation observé / dérivé** : le champ `nature` suit chaque valeur jusqu'au backend.
