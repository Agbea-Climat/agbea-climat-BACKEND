# Comprendre la température de surface (LST)

Source : https://lpdaac.usgs.gov/products/mod11a2v061/

## Ce que mesure l'indicateur

L'indicateur « Température du sol » donne la chaleur de la surface du sol en journée, en degrés Celsius (°C).

En anglais, on dit LST, pour « Land Surface Temperature ». La donnée vient du capteur MODIS, à bord du satellite Terra de la NASA (produit MOD11A2). Le satellite mesure la chaleur émise par la surface : sol, champs, toits, routes, arbres.

Le satellite passe le matin, vers 10 h 30. Les pixels font 1 km. Le produit NASA fait une moyenne sur 8 jours des observations par ciel clair. AGBÉA calcule ensuite une moyenne par mois et par région.

## Surface n'est pas air

C'est le piège principal.

- La **température de l'air** est mesurée par les stations météo, à l'ombre, à environ 2 mètres du sol.
- La **température de surface** est celle du sol lui-même. Au soleil, un sol nu, une route ou un toit de tôle peuvent être bien plus chauds que l'air.

Les deux chiffres ne sont donc pas les mêmes. À partir de la température de surface, il ne faut pas dire « il a fait tant de degrés ». Il faut dire « la surface du sol était à tant de degrés en moyenne, au passage du satellite ».

## Comment lire une valeur

- La valeur est une **moyenne du mois** au passage du matin. Ce n'est pas la température d'un jour précis, ni la plus forte chaleur de l'après-midi.
- La valeur est une **moyenne sur la région**. Une ville, un sol nu ou une zone brûlée sont plus chauds qu'une forêt.
- Il faut comparer au **même mois** des autres années. AGBÉA donne l'anomalie par rapport à la moyenne 2001-2020.
- La végétation et l'humidité du sol rafraîchissent la surface. Un sol sec et nu chauffe plus vite.

## Pièges à éviter

**Les nuages.** Le satellite ne mesure la surface que par ciel clair. En saison des pluies, il y a peu de jours sans nuages. Les valeurs sont alors rares et viennent surtout des jours secs. Elles peuvent donc paraître plus chaudes que la réalité du mois. AGBÉA indique la part de la région visible (`valid_frac`) et signale les mois où moins de la moitié était visible (`low_coverage`).

**La meilleure période pour comparer.** De janvier à mars, c'est la saison sèche sur tout le Togo. Le ciel est souvent clair. C'est la meilleure fenêtre pour comparer la température de surface d'une année à l'autre.

**Le satellite vieillit.** Depuis 2022, le satellite Terra passe plus tôt le matin. Le sol a eu moins de temps pour chauffer. La température de surface peut donc baisser artificiellement dans les années récentes. Une baisse récente n'est pas forcément un vrai refroidissement.

**Pas une prévision.** Ces chiffres décrivent le passé. Pour savoir s'il va faire chaud demain, il faut suivre les bulletins du service météorologique national.

## À quoi cela sert

- Repérer les zones qui chauffent le plus, par exemple les villes ou les sols nus.
- Suivre, avec la pluie et le NDVI, l'état des terres en saison sèche.
- Sensibiliser à la chaleur en ville, en précisant bien qu'il s'agit de la surface.

## Ce qu'il faut retenir

- LST = chaleur de la surface du sol, le matin, en °C.
- Ce n'est pas la température de l'air.
- Mesurée seulement par ciel clair : prudence en saison des pluies.
- Comparer de préférence les mois de janvier à mars.
- Les années depuis 2022 sont à lire avec prudence.
