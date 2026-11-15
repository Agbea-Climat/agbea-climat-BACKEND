# Notebooks d'exploration des données

Ils remplacent l'ancien front de test (`tests/front/`, supprimé le 14/11/2026). Ils servent à l'équipe données et au backend pour **voir, contrôler et interroger** tout ce que le pipeline publie. Ce n'est pas le front de l'application. Ils lisent seulement `data/`, en lecture seule, et ne recalculent aucune donnée.

## Lancer (Docker)

```powershell
docker compose --profile notebooks up -d notebooks      # http://localhost:8888 (JupyterLab)
docker compose --profile notebooks down                 # arrêter
```

`data/` est monté en lecture seule. `tests/notebooks/` est monté en écriture : les notebooks modifiés dans JupyterLab sont enregistrés dans le dépôt. **Avant un commit**, effacer les sorties (*Edit → Clear Outputs of All Cells*) : les figures plotly pèsent plusieurs Mo.

Le port n'est publié que sur `127.0.0.1` (JupyterLab sans jeton) : il n'est pas joignable depuis le réseau.

## Contenu

| Notebook | Ce qu'on y voit |
|---|---|
| `01_carte_thematique.ipynb` | carte par région, préfecture ou canton : moyenne de référence, dernière année complète, écart à la référence, tendance (grisée si non significative) ; pluie, NDVI, LST jour/nuit, altitude ; sites pilotes ; tableau trié |
| `02_fiche_unite.ipynb` | fiche d'une unité : dernières observations (source, nature, part visible), série annuelle ou saisonnière avec référence et droite de Theil-Sen, 24 derniers mois contre la normale (mois à couverture < 50 % signalés), toutes les tendances, fiche JSON brute |
| `03_couches_raster.ipynb` | couches GeoTIFF de `data/api/layers` pixel par pixel (années, référence, écarts, altitude) avec contours et sites, statistiques et métadonnées |
| `04_catalogue_controles.ipynb` | jeux de données (DOI, résolution, licence, limites), indicateurs et couverture, règles, `validation.json`, fichiers publiés, **livrable P2** du backend (périodes, faible couverture), contrôle LST Terra / Aqua |

`agbea_nb.py` regroupe la lecture des fichiers et les petites fonctions communes.

## Vérifier

```powershell
docker compose --profile notebooks run --rm notebooks python verifier.py
```

`verifier.py` exécute les cellules de chaque notebook, puis appelle chaque fonction d'affichage avec un échantillon de toutes les combinaisons des menus. `jupyter nbconvert --execute` ne suffit pas : une erreur levée dans un widget ne le fait pas échouer.

## Prérequis

`data/api/` doit exister (`docker compose run --rm pipeline export`). Le contrôle Terra / Aqua du notebook 4 demande `lst-aqua` puis `control-lst`.
