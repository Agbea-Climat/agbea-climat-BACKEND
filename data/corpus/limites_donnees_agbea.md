# Limites des données AGBÉA CLIMAT

Sources : méthodologie du pipeline AGBÉA CLIMAT — https://github.com/Agbea-Climat/agbea-climat-BACKEND/blob/main/docs/data/methodologie.md ;
normales climatiques OMM 1991-2020 des stations de Lomé (65387) et d'Aného (65445), archive NOAA/NCEI
(accession 0253808) —
https://www.nodc.noaa.gov/archive/arc0216/0253808/3.3/data/0-data/Region-1-WMO-Normals-9120/Togo/CSV/LOME_65387.csv et
https://www.nodc.noaa.gov/archive/arc0216/0253808/3.3/data/0-data/Region-1-WMO-Normals-9120/Togo/CSV/ANEHO_65445.csv ;
NASA, mission Terra (terra.nasa.gov).

## Données observées, pas des prévisions

AGBÉA CLIMAT montre ce que les satellites de la NASA ont **observé** dans le passé. Il ne prévoit pas la pluie
de demain et ne remplace ni les prévisions officielles ni les systèmes d'alerte.

## Moyenne régionale

Chaque valeur est une moyenne sur toute une région. Une région peut sembler proche de la normale alors qu'une
de ses parties a eu trop ou pas assez de pluie.

## Nuages et « faible couverture »

La végétation (NDVI) et la température du sol ne se mesurent que par ciel clair. Pour chaque mois, AGBÉA CLIMAT
indique la part de la région réellement visible. Quand moins de 50 % de la région est visible, la valeur porte
la mention « faible couverture » : elle repose sur une petite partie de la région et doit être lue avec prudence.
C'est fréquent en saison des pluies, surtout dans la région Maritime, de juillet à septembre.

## Pluie surestimée sur la côte

Comparaison entre la pluie IMERG (moyenne 2001-2020 de la maille de 11 km qui contient la station) et les normales
officielles des pluviomètres (OMM 1991-2020) :
- Lomé : environ 1 010 mm/an pour IMERG contre **830,3 mm** au pluviomètre ;
- Aného : environ 1 071 mm/an pour IMERG contre **909,3 mm**.

IMERG donne donc environ 20 % de pluie de plus que les pluviomètres sur la côte. L'écart vient surtout des mois
peu pluvieux ; la forme de l'année (mois secs et mois pluvieux) est juste. Conséquences :
- les **écarts à la normale en %** sont beaucoup moins touchés, car la normale vient du même produit
  (tant que le biais reste proportionnel) ;
- les **totaux et les écarts en millimètres** restent gonflés d'environ 20 % : ce sont des estimations satellite.

## Température du sol et dérive du satellite Terra

Le satellite Terra, qui porte le capteur MODIS utilisé ici, ne corrige plus l'heure de passage de son orbite
depuis sa dernière manœuvre d'inclinaison, le 27 février 2020, et passe de plus en plus tôt le matin.
Cela fausse les tendances de température après 2020, puis les valeurs elles-mêmes : à partir de 2023, l'écart avec
le satellite Aqua dépasse 0,7 °C (et 1,5 °C en 2025). AGBÉA CLIMAT arrête donc les tendances de température en 2020
et ne publie plus de température du sol après décembre 2022. Sur 2003-2020, la hausse de la température de surface la nuit a été vérifiée
avec un second satellite (Aqua).

## Mois récents

- Le mois en cours n'est jamais affiché : il n'est pas terminé.
- La température du sol s'arrête en décembre 2022 (dérive du satellite Terra, voir plus haut).
- La pluie IMERG Final arrive en temps normal 3 à 4 mois après le mois observé ; actuellement, la série de pluie
  s'arrête en septembre 2025, alors que la végétation va jusqu'en octobre 2026.
