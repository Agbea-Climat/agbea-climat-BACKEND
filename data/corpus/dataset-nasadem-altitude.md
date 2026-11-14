# Fiche dataset et explication : altitude NASADEM (SRTM retraité)

Source : https://lpdaac.usgs.gov/products/nasadem_hgtv001/

## Identité du produit

- Nom : NASADEM (SRTM retraité), version 001, produit NASADEM_HGT.
- Fournisseur : NASA JPL / LP DAAC.
- Citation : doi:10.5067/MEaSUREs/NASADEM/NASADEM_HGT.001.
- Indicateur AGBÉA : `elevation` (altitude), en mètres.
- Identifiant dans l'API : `srtm`.

## D'où vient cette altitude

Le relief a été mesuré par radar pendant la mission SRTM. Cette mission a duré 11 jours, en février 2000, à bord de la navette spatiale Endeavour.

NASADEM est un retraitement de ces mesures. Selon la NASA, il apporte :

- une meilleure position géographique, grâce à des points de contrôle lidar du satellite ICESat ;
- un comblement des trous avec d'autres modèles de relief (ASTER GDEM v2, ALOS AW3D30) et par interpolation ;
- des altitudes rapportées au géoïde (proche du niveau moyen de la mer) ;
- une couche mise à jour des plans d'eau.

Caractéristiques :

- Résolution : 1 seconde d'arc, soit environ 30 m.
- Couverture : terres entre 60° N et 56° S. Le Togo est couvert.
- Donnée statique : une seule « photo » du relief, celle de 2000.

## Ce que fait le pipeline AGBÉA

1. **Grille** : le relief à 30 m est ramené sur une grille de 0,000833° (environ 90 m) par moyenne.
2. **Statistiques par région** : pour chaque région, le pipeline calcule `mean` (moyenne), `min`, `max`, `p10` (10 % des points sont plus bas), `median`, `p90` (90 % des points sont plus bas) et `pct_below_10m` (part de la région sous 10 m).
3. Ces chiffres sont livrés dans `data/processed/static.json`. Il n'y a pas de série dans le temps.

## Comment lire l'altitude (grand public)

- L'altitude dit à quelle hauteur se trouve le terrain, en mètres au-dessus du niveau de la mer.
- Une zone basse et plate reçoit l'eau qui descend des pentes. Elle peut être plus exposée aux inondations.
- Une zone en pente fait ruisseler l'eau. Le sol peut y être plus exposé à l'érosion.
- La médiane est souvent plus parlante que la moyenne : la moitié de la région est plus basse, l'autre moitié plus haute.
- `pct_below_10m` aide à repérer les régions qui ont beaucoup de terres très basses, surtout près de la côte et des lagunes.

L'altitude seule ne dit pas qu'un lieu va être inondé. Le risque dépend aussi de la pluie, des sols, des rivières et des aménagements.

## Pièges à connaître

- **Valeurs négatives** : `min` peut être négatif sur la côte, par exemple dans la région Maritime. C'est du bruit du modèle sur les lagunes et zones humides, pas une vraie altitude. Pour parler d'un « point bas », il vaut mieux utiliser `p10`.
- **Sommet des objets** : le radar voit le haut de la végétation et des bâtiments. L'altitude n'est donc pas toujours celle du sol.
- **Relief de 2000** : les changements récents (carrières, remblais, constructions, érosion côtière) ne sont pas visibles.
- **Résolution** : une valeur à 90 m ne montre pas les petits fossés ou les petites buttes d'un champ.
