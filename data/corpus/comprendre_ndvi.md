# Comprendre le NDVI (verdure de la végétation)

Source : NASA Earth Observatory, « Measuring Vegetation (NDVI & EVI) » —
https://science.nasa.gov/earth/earth-observatory/measuring-vegetation-ndvi-evi

## Le principe

La chlorophylle des feuilles absorbe fortement la lumière visible (dont le rouge, utilisé par MODIS), tandis que la structure des feuilles
renvoie fortement le proche infrarouge. Le satellite mesure ces deux lumières et calcule :

NDVI = (proche infrarouge - visible) / (proche infrarouge + visible)

Le résultat est toujours compris entre -1 et +1. D'après la NASA :
- 0,1 et moins : sol nu, roche, sable (aucune feuille verte : valeur proche de zéro) ;
- 0,2 à 0,3 : arbustes et prairies ;
- 0,6 à 0,8 : forêts denses humides, tropicales et tempérées ;
- 0,8 à 0,9 : densité maximale de feuilles vertes.

## Lire le NDVI au Togo

- Le NDVI monte pendant la saison des pluies, quand les cultures et les herbes poussent,
  et baisse en saison sèche (feuilles sèches, champs récoltés).
- Il faut donc comparer un mois à sa **normale** (même mois, 2001-2020) : un NDVI plus bas que la normale
  en pleine saison des pluies peut signaler un manque de pluie, un semis tardif ou une végétation stressée.
- Un NDVI élevé ne veut pas dire une bonne récolte : il mesure la verdeur, pas le rendement.

## Précautions

- Les nuages empêchent de voir le sol. Quand moins de la moitié de la région est visible dans le mois,
  la valeur est marquée « faible couverture » et doit être lue avec prudence.
- La résolution (500 m) mélange champs, arbres, villages et routes dans un même pixel.
