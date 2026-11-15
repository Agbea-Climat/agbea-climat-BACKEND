# Fiche jeu de données : végétation MODIS NDVI (modis_ndvi)

Source : NASA LP DAAC, MODIS/Terra Vegetation Indices 16-Day L3 Global 500m SIN Grid V061 (MOD13A1),
doi:10.5067/MODIS/MOD13A1.061 — https://lpdaac.usgs.gov/products/mod13a1v061/

## Ce que c'est

Le capteur MODIS, à bord du satellite Terra de la NASA, observe toute la surface de la Terre tous les 1 à 2 jours.
Le produit MOD13A1 calcule l'indice de végétation NDVI à 500 m de résolution. Pour chaque période de 16 jours,
il retient pour chaque pixel la meilleure observation sans nuage.

## Dans AGBÉA CLIMAT

- Indicateur : `ndvi` (verdure de la végétation), sans unité, entre -1 et +1.
- Les composites de 16 jours sont regroupés par mois, puis moyennés sur chaque région.
- Période des séries : à partir de janvier 2001 (le produit existe depuis février 2000). Normales 2001-2020.
- Seuls les pixels de qualité bonne ou marginale, sans nuage, sont gardés. La part de la région réellement visible
  est indiquée pour chaque mois (`valid_frac`).

## Limites à rappeler à l'utilisateur

- En saison des pluies, les nuages cachent souvent le sol, surtout sur la côte entre juin et septembre :
  certains mois, une grande partie de la région n'est pas visible. Ces mois sont marqués « faible couverture ».
- Le NDVI mesure la verdeur des plantes, pas la quantité de récolte ni le type de culture.
- Le NDVI suit fortement les saisons : il faut comparer un mois au même mois des autres années (à la normale),
  pas au mois précédent.
