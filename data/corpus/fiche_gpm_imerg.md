# Fiche jeu de données : pluie GPM IMERG (gpm_imerg)

Source : NASA GES DISC, GPM IMERG Final Precipitation L3 1 month 0.1° V07 (GPM_3IMERGM),
doi:10.5067/GPM/IMERG/3B-MONTH/07 — https://disc.gsfc.nasa.gov/datasets/GPM_3IMERGM_07/summary

## Ce que c'est

IMERG (Integrated Multi-satellitE Retrievals for GPM) estime la pluie tombée en combinant les mesures
de la constellation de satellites du programme GPM (Global Precipitation Measurement) de la NASA et de la JAXA.
Les capteurs micro-ondes des satellites sont la source principale ; les images infrarouges des satellites
géostationnaires comblent les intervalles entre deux passages. Dans la version « Final Run », les estimations
satellites sont recalées chaque mois sur les pluviomètres au sol (analyse GPCC).

## Dans AGBÉA CLIMAT

- Indicateur : `precipitation` (pluie du mois), en millimètres (cumul mensuel).
- Grille : 0,1° (environ 11 km). Chaque valeur régionale est la moyenne pondérée des mailles qui couvrent la région.
- Période des séries : à partir de janvier 2001. Les normales sont calculées sur 2001-2020.
- Le produit couvre le globe depuis janvier 1998.
- Le Final Run est publié en temps normal 3 à 4 mois après le mois observé : les derniers mois peuvent manquer.
  Actuellement, la série s'arrête en septembre 2025.

## Limites à rappeler à l'utilisateur

- C'est une **estimation satellite**, pas une mesure de pluviomètre.
- Une maille de 11 km représente une zone, pas un point précis (un village, un champ).
- Sur la côte (Lomé, Aného), IMERG donne environ 20 % de pluie de plus que les pluviomètres
  (voir le document « Limites des données AGBÉA CLIMAT »).
- Les écarts à la normale en pourcentage sont plus fiables que les totaux en millimètres.
