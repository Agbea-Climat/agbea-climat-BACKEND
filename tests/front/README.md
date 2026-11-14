# Front de test — explorateur des données

Page statique, sans étape de build, pour **voir et vérifier tout ce que le pipeline publie** dans `data/api/`. Ce n'est pas le front de l'application : il sert à l'équipe données et au backend pour contrôler les valeurs, la provenance et les couches.

## Lancer (Docker)

```powershell
docker compose --profile front up -d front-test     # http://localhost:8089
docker compose --profile front down                 # arrêter
```

nginx sert `tests/front/` à la racine, `data/api/` sous `/api/` et `data/reference/` sous `/reference/`, en lecture seule. Après un `export`, il suffit de recharger la page.

## Ce qu'on y voit

| Onglet | Contenu |
|---|---|
| Explorateur | Carte : contours MAP TOGO (pays, 5 régions, 39 préfectures) et 7 sites. **Carte thématique** par région ou préfecture (moyenne de référence, dernière année, anomalie, tendance ; tendances non significatives délavées). **Couches raster** NASA pixel par pixel (pluie, NDVI, LST jour/nuit par année, référence ou anomalie ; altitude). **Fiche** de l'unité cliquée : dernières observations avec source et nature (observé/dérivé), séries annuelles ou saisonnières avec la moyenne de référence et la pente de Sen, 24 derniers mois comparés à la normale, tableau des tendances, JSON brut |
| Catalogue & provenance | jeux de données (DOI, résolution, couverture, licence, limites), indicateurs, couverture réelle, règles |
| Contrôles | `validation.json` (pass / warn / fail) |
| Fichiers | liste des fichiers publiés, avec liens de téléchargement |

## Détails techniques

- Bibliothèques par CDN, versions figées : MapLibre GL 4.7.1, Chart.js 4.4.1, geotiff.js 2.1.3.
- Les GeoTIFF sont lus dans le navigateur. Leurs lignes sont reprojetées de EPSG:4326 vers Web Mercator avant affichage, pour que les pixels tombent au bon endroit. L'altitude (~6 000 lignes) est sous-échantillonnée à 1 400 lignes à l'affichage seulement.
- Couleurs de la carte thématique : `feature-state` numérique (`v` ∈ [0,1], −1 = pas de donnée) et expression `interpolate`. Ne **jamais** utiliser `removeFeatureState` sur une entité sans état : MapLibre 4.7 plante alors silencieusement au rendu.
- Fonds de carte : OpenStreetMap (usage de test) et Esri World Imagery.
