# Méthodologie de traitement

Ce document décrit chaque transformation entre la donnée NASA brute et les chiffres livrés au backend. Il sert de base à l'écran « Méthodologie » et au rôle « validation » de l'équipe.

## 1. Zones d'analyse

- **Pays, régions, préfectures** : limites officielles PRISE de geodata.gouv.tg (2026-10-23), avec les noms rattachés par le projet MAP TOGO (`data/reference/map_togo/`) : 5 régions, 39 préfectures, contour du pays = union des régions. La réutilisation publique est à confirmer (CGU). En repli : COD-AB HDX via `boundaries.admin_source: hdx`.
- **Cantons** : COD-AB Togo (OCHA/HDX, v02 du 2021-01-07, CC BY-IGO), rattachés à la préfecture officielle qui les recouvre le plus.
- **Sites pilotes** : disque de 10 km de rayon autour du point du front, calculé en UTM 31N, puis **découpé par la frontière du Togo**. Lomé et Aného perdent ainsi la partie en mer ; Kpalimé, la partie au Ghana.

## 2. Grille commune

Chaque produit est ramené sur une grille régulière EPSG:4326 couvrant −0,3 → 2,0 °E et 6,0 → 11,3 °N :

| Produit | Grille | Méthode |
|---|---|---|
| IMERG | 0,1° (native) | aucune : les bords de l'emprise sont des multiples de 0,1° |
| MODIS NDVI (500 m sinusoïdal) | 0,005° | plus proche voisin, après masque qualité |
| MODIS LST (1 km sinusoïdal) | 0,01° | plus proche voisin, après masque qualité |
| NASADEM (30 m) | 0,000833° (~90 m) | moyenne |

Le géoréférencement a été contrôlé sur des repères connus : trait de côte de Lomé à ~6,13 °N, lac Togo en NDVI négatif.

## 3. Contrôle qualité par produit

**NDVI (MOD13A1 v061, Terra)** : on garde `pixel_reliability` 0 (bon) et 1 (marginal) ; on rejette −1 (vide), 2 (neige/glace) et 3 (nuage). On utilise Terra seul pour que la série soit homogène depuis 2000 (Aqua ne démarre qu'en 2002).

**LST (MOD11A2 v061, Terra)** : on garde QC bits 0-1 = 00 (bonne qualité), ou 01 si l'erreur LST estimée (bits 6-7) est ≤ 2 K. Conversion : `valeur × 0,02 − 273,15` en °C.

**IMERG (V07)** : valeurs négatives et `_FillValue` masquées. Le mensuel est un taux moyen en mm/h, converti en cumul : `taux × 24 × nombre de jours du mois`.

## 4. Agrégation mensuelle

- MODIS : un composite (16 j NDVI, 8 j LST) est rattaché au mois qui contient **son milieu**. La valeur mensuelle d'un pixel est la moyenne des composites valides.
- IMERG : le produit est déjà mensuel.

## 5. Statistiques par zone

Moyenne **pondérée par la fraction de chaque pixel couverte par la zone**. Les fractions sont calculées par sur-échantillonnage (×20 pour IMERG, ×5 LST, ×3 NDVI). C'est indispensable pour la pluie : un site de 10 km ne recouvre que quelques mailles de 11 km, et souvent en partie.

`valid_frac` = part de la surface de la zone couverte par des pixels valides. Un mois est publié à `null` si `valid_frac < 0,5` : la valeur ne représenterait pas la zone.

## 6. Référence et anomalies

- Période de référence : **2001-2020** (20 années complètes communes à MODIS Terra et IMERG). Ce n'est pas la normale OMM 1991-2020, que MODIS ne couvre pas.
- Anomalie mensuelle = valeur − moyenne du même mois sur 2001-2020. Pour la pluie, on donne aussi l'écart en %.

## 7. Agrégats annuels et saisonniers

| Saison | Mois | Usage |
|---|---|---|
| `annual` | 1-12 | vue générale |
| `jfm` | janvier-mars | saison sèche sur tout le pays, ciel clair : la meilleure fenêtre pour comparer la LST d'une année à l'autre |
| `mjjaso` | mai-octobre | saison des pluies (bimodale au sud, unimodale au nord) |

Pluie : cumul, uniquement si tous les mois sont présents. NDVI et LST : moyenne, avec au moins 10 mois sur 12 pour l'annuel. Une saison pas encore terminée n'est jamais publiée.

## 8. Tendances

- Test de **Mann-Kendall**, via le tau de Kendall avec correction des ex æquo, au seuil α = 0,05.
- Pente de **Theil-Sen**, robuste aux valeurs extrêmes, avec son intervalle de confiance à 95 %.
- Au moins 10 années valides.
- Appliqué aux agrégats annuels et saisonniers. Les séries mensuelles, trop saisonnières et autocorrélées, ne sont pas testées.

**Ce que le test ne dit pas** : il ne donne pas la cause d'une tendance. Il ne corrige pas non plus l'autocorrélation entre années successives, faible à ce pas de temps mais non nulle, ni la multiplicité des tests : sur 400 unités, ~5 % de « tendances significatives » apparaîtront par hasard. Pour la démo, on privilégie les sites pilotes et les régions plutôt que de chercher la tendance la plus spectaculaire parmi les cantons.

## 9. Limites à afficher

1. **IMERG** : estimation satellitaire, pas un pluviomètre. Maille de 11 km.
2. **NDVI** : en saison des pluies, les nuages réduisent la couverture, surtout sur la côte ; `valid_frac` le montre.
3. **LST** : c'est la température du sol et des toits, pas de l'air. Elle n'est mesurée que par ciel clair.
4. **Dérive orbitale de Terra** : depuis 2022, Terra passe plus tôt le matin. La LST de jour peut baisser artificiellement et le NDVI être légèrement affecté. Les tendances qui finissent après 2022 sont à lire avec prudence. Piste de correction : comparer avec Aqua (MYD) ou s'arrêter à 2021 pour la LST.
5. **MERRA-2** (air 2 m) : réanalyse de ~55 km. Une valeur représente toute une zone, pas une ville.
6. **NASADEM** : altitude de la surface en 2000, canopée et bâtiments compris.
