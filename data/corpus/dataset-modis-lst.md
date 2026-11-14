# Fiche dataset : température de surface MODIS Terra MOD11A2 v061 (LST)

Source : https://lpdaac.usgs.gov/products/mod11a2v061/

## Identité du produit

- Nom : MODIS Terra MOD11A2, version 061 (température de surface et émissivité, 8 jours, 1 km).
- Fournisseur : NASA LP DAAC.
- Citation : doi:10.5067/MODIS/MOD11A2.061.
- Variable utilisée : `LST_Day_1km` (température de surface de jour).
- Indicateur AGBÉA : `lst_day` (température du sol), en °C.
- Identifiant dans l'API : `modis_lst`.

## Ce que contient le produit

LST veut dire « Land Surface Temperature » : température de la surface terrestre. Le capteur MODIS, à bord du satellite Terra, mesure le rayonnement infrarouge émis par le sol.

Chaque pixel de MOD11A2 est la moyenne simple des observations journalières (produit MOD11A1) par ciel clair sur 8 jours. Le produit contient aussi des couches de contrôle qualité, d'heure d'observation et d'angle de visée.

- Résolution spatiale : 1 km.
- Pas de temps : composite 8 jours, agrégé au mois par AGBÉA.
- Couverture : globale.
- Données disponibles depuis 2000.
- Le passage de jour de Terra a lieu vers 10 h 30 (heure solaire locale). La nuit (vers 22 h 30) existe aussi, mais l'API P2 livre seulement le jour.

## Ce que fait le pipeline AGBÉA

1. **Contrôle qualité** : on garde les pixels dont les bits QC 0-1 valent 00 (bonne qualité). On garde aussi 01 si l'erreur estimée de LST (bits 6-7) est inférieure ou égale à 2 K.
2. **Conversion** : valeur brute × 0,02 − 273,15, en °C.
3. **Grille** : reprojection sur une grille de 0,01° (plus proche voisin), après le masque qualité.
4. **Mois** : chaque composite de 8 jours est rattaché au mois qui contient son milieu. La valeur mensuelle d'un pixel est la moyenne de ses composites valides.
5. **Moyenne par région** : moyenne pondérée par la part de chaque pixel couverte par la région (sur-échantillonnage ×5).
6. **Arrondi** : 1 décimale.

## Champs livrés pour chaque région et chaque mois

- `value` : température de surface moyenne de jour des pixels visibles, en °C.
- `valid_frac` : part de la région couverte par des pixels valides. Les nuages la font baisser.
- `low_coverage` : vrai si `valid_frac` est inférieur à 0,5. La valeur doit alors être signalée comme peu représentative.

## Normales, saisons et tendances

- Période de référence : 2001-2020.
- Anomalie = valeur du mois − moyenne du même mois sur 2001-2020.
- La saison `jfm` (janvier-mars) est la saison sèche sur tout le pays. Le ciel y est clair. C'est la meilleure fenêtre pour comparer la LST d'une année à l'autre.
- Moyenne annuelle publiée seulement s'il y a au moins 10 mois valides sur 12.
- Tendances : test de Mann-Kendall et pente de Theil-Sen, sur au moins 10 années, annoncées seulement si significatives.

## Limites à rappeler

- C'est la température de la surface (sol, toits, routes, champs). Ce n'est pas la température de l'air mesurée sous abri par la météo.
- Elle n'est mesurée que par ciel clair. En saison des pluies, les valeurs sont rares et biaisées vers les jours secs.
- Depuis 2022, l'orbite de Terra dérive : il passe plus tôt le matin. La LST de jour peut baisser artificiellement. Les tendances récentes de LST de jour sont à lire avec prudence.
- Une valeur mensuelle est une moyenne. Ce n'est pas un instantané d'une journée chaude.
- Ces données décrivent le passé. Elles ne sont pas une prévision.
