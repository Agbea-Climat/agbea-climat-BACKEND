# Fiche jeu de données : altitude NASADEM (srtm)

Source : NASA JPL / LP DAAC, NASADEM Merged DEM Global 1 arc second V001 (NASADEM_HGT),
doi:10.5067/MEaSUREs/NASADEM/NASADEM_HGT.001 — https://lpdaac.usgs.gov/products/nasadem_hgtv001/

## Ce que c'est

NASADEM est le modèle numérique de terrain issu de la mission radar SRTM (Shuttle Radar Topography Mission),
menée par la navette spatiale du 11 au 21 février 2000, puis retraité par le JPL de la NASA.
Il donne l'altitude du terrain tous les 30 mètres environ (1 seconde d'arc), entre 56° S et 60° N.

## Dans AGBÉA CLIMAT

- Indicateur : `elevation` (altitude), en mètres. C'est une donnée **fixe** : il n'y a pas de série dans le temps.
- Pour chaque région : altitude moyenne, minimale, maximale, médiane, 10e et 90e centiles,
  et part du territoire située à moins de 10 m d'altitude (zones basses, exposées à la mer et aux inondations).
- Les statistiques régionales sont calculées sur une grille ré-échantillonnée à environ 90 m.

## Limites à rappeler à l'utilisateur

- Le relief a été mesuré en 2000 : il ne montre pas les changements récents (carrières, remblais, érosion côtière).
- Le radar ne traverse pas entièrement la végétation ni les bâtiments : en forêt ou en ville, l'altitude peut inclure
  une partie de la hauteur des arbres ou des bâtiments.
