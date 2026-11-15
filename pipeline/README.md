# pipeline/ — données NASA pour AGBÉA CLIMAT (prérequis P2)

Transforme les données d'observation de la Terre de la NASA en fichiers prêts pour l'API (`backend/`).

| Indicateur | Source NASA | Accès |
|---|---|---|
| Pluie (mensuelle, 30 derniers jours) | GPM IMERG V07 | compte NASA Earthdata (gratuit) |
| Végétation (NDVI) | MODIS Terra MOD13A1 v061 | libre (+ LP DAAC avec jeton pour les trous) |
| Température de surface jour/nuit | MODIS Terra MOD11A2 v061 | idem |
| Température de l'air à 2 m | NASA POWER (MERRA-2) | libre |
| Altitude | NASADEM (SRTM) | libre |

Zones : pays, 5 régions et 39 préfectures (limites officielles geodata.gouv.tg, via MAP TOGO), 373 cantons (COD-AB OCHA), 7 sites pilotes.

## Sorties

| Fichier | Pour qui | Versionné |
|---|---|---|
| `data/regions.geojson`, `data/processed/monthly.parquet`, `data/processed/static.json` | **API** (P2, format de `MISSIONS.md`) | oui |
| `data/api/` : fiches par unité, tables complètes, couches GeoTIFF, catalogue, contrôles | notebooks d'exploration, futures missions, scientifique | non (régénérable) |

Format détaillé : [docs/data/contrat-donnees.md](../docs/data/contrat-donnees.md).

## Commandes

```powershell
docker compose run --rm pipeline all                   # tout
docker compose run --rm pipeline export-backend        # seulement le livrable P2
docker compose --profile test run --rm pipeline-tests
```

Détails : [docs/data/pipeline.md](../docs/data/pipeline.md) · méthode : [docs/data/methodologie.md](../docs/data/methodologie.md) · accès aux sources : [docs/data/acces-donnees.md](../docs/data/acces-donnees.md) · Docker : [docs/docker.md](../docs/docker.md).

## Règles

- Toute valeur publiée vient d'une source NASA citée dans `data/api/catalog.json`, avec unité, résolution, période et limites.
- Le pipeline produit de l'**observé** et du **dérivé**, jamais d'interprétation ni de prévision.
- « Tendance » seulement si le test de Mann-Kendall est significatif (`trends.significant`).
