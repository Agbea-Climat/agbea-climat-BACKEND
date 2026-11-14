# pipeline/ — règles pour les agents (volet données)

Pipeline Python qui produit `data/` pour l'API. C'est le prérequis **P2** de `MISSIONS.md`. Les règles générales du projet (contrat API, format d'erreurs, « aucun chiffre inventé ») sont dans `MISSIONS.md` et `README.md`.

## Conventions de l'équipe données

- Langue : **français** pour la doc, les notes, les commentaires et les messages.
- À chaque session : `changelogs/AAAA-MM-JJ.md` (surtout tout changement du livrable), `notes/` (constats, `notes/decisions.md` numérotées Dn, `notes/todo.md`), et `docs/data/` à jour (`contrat-donnees.md` fait foi).
- Ne jamais versionner `.env`, `data/raw`, `data/interim`, `data/api`, `logs/`.

## Intégrité scientifique (non négociable)

- Aucune valeur fictive. Pas de score composite sans méthode écrite dans `docs/data/methodologie.md`.
- Chaque indicateur porte `dataset` (clé de `pipeline/settings/datasets.yaml`) et `nature` (`observed` / `derived`).
- Parler de « tendance » seulement si `significant = true` (Mann-Kendall, α = 0,05).

## Livrable P2 (`backend_export.py`) — ne pas casser

- `data/regions.geojson` : 5 features, `properties.id` ∈ `maritime, plateaux, centrale, kara, savanes`.
- `data/processed/monthly.parquet` : `region_id, indicator, date (YYYY-MM), value` + `valid_frac, low_coverage, dataset_id`. Indicateurs `precipitation, ndvi, lst_day` (notre `rainfall` = `precipitation`).
- `value` = moyenne des pixels visibles quelle que soit la couverture ; `low_coverage = valid_frac < 0,5` doit être signalé par l'interface.
- Vérifier avec `docker compose --profile test run --rm api-tests` (marker `p2`).

## Commandes

```powershell
docker compose run --rm pipeline <boundaries|power|dem|ndvi|lst|imerg|imerg-daily|analyse|export|export-backend|all>
docker compose --profile test run --rm pipeline-tests
python -m pipeline <étape>            # hors Docker
python -m pytest pipeline/tests
```

## Points d'attention

- IMERG et le comblement LP DAAC demandent `EARTHDATA_TOKEN` dans `.env` ; sans jeton, ces étapes sont sautées proprement.
- Les noms de fichiers IMERG changent de sous-version (V07B, V07C…) : toujours les découvrir par le listing.
- MODIS via Planetary Computer : lecture fenêtrée, Terra seul (`MOD*`). Les trous (ex. juillet-novembre 2025) sont comblés automatiquement depuis LP DAAC.
- Limites : pays, régions et préfectures = MAP TOGO / geodata.gouv.tg (`TG-A`, `TG-A01`) ; cantons = HDX. Réglage `boundaries.admin_source` dans `pipeline/settings/settings.yaml`.
- Front de test (`tests/front/`) : ne jamais appeler `removeFeatureState` sur une entité sans état (MapLibre 4.7 plante silencieusement au rendu).
- La console Windows est en cp1252 : la CLI force l'UTF-8.
