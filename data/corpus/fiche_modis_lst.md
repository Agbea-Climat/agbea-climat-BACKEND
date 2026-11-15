# Fiche jeu de données : température du sol MODIS LST (modis_lst)

Source : NASA LP DAAC, MODIS/Terra Land Surface Temperature/Emissivity 8-Day L3 Global 1km SIN Grid V061 (MOD11A2),
doi:10.5067/MODIS/MOD11A2.061 — https://lpdaac.usgs.gov/products/mod11a2v061/

## Ce que c'est

Le capteur MODIS du satellite Terra mesure le rayonnement infrarouge thermique émis par la surface.
Le produit MOD11A2 en déduit la température de surface (LST, Land Surface Temperature) à 1 km,
en moyenne sur 8 jours, de jour (passage nominal vers 10 h 30 heure locale, plus tôt depuis la dérive de 2020) et de nuit.

## Dans AGBÉA CLIMAT

- Indicateur : `lst_day` (température du sol en journée), en degrés Celsius.
- Les composites de 8 jours sont regroupés par mois, puis moyennés sur chaque région.
- Période des séries : de janvier 2001 à **décembre 2022** (le produit existe depuis février 2000). Normales 2001-2020.
- La part de la région visible sans nuage est indiquée pour chaque mois (`valid_frac`).
- Le mois en cours n'est jamais publié tant qu'il n'est pas terminé.

## Limites à rappeler à l'utilisateur

- C'est la température de la **surface** (toits, routes, champs, feuillage), pas celle de l'air donnée
  par la météo. Un sol nu en plein soleil peut être bien plus chaud que l'air.
- Le satellite ne voit le sol que par ciel clair : en saison des pluies, les valeurs sont rares
  et représentent surtout les jours secs.
- Le satellite Terra dérive lentement sur son orbite depuis 2020 et passe de plus en plus tôt le matin, quand le sol
  est plus frais. À partir de 2023, l'écart avec le satellite Aqua dépasse 0,7 °C. AGBÉA CLIMAT ne publie donc pas
  de température du sol après décembre 2022, et ne calcule pas de tendance après 2020.
