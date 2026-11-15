# Validation de la pluie IMERG à Lomé (14/11/2026)

## Question

IMERG Final V07 donne ~1 000 mm/an à Lomé. Est-ce cohérent avec les mesures au sol ?

## Référence au sol

**Normales OMM 1991-2020, station Lomé (OMM 65387)**, source primaire NOAA/NCEI (accession 0253808) :
<https://www.nodc.noaa.gov/archive/arc0216/0253808/3.3/data/0-data/Region-1-WMO-Normals-9120/Togo/CSV/LOME_65387.csv>.
Valeur annuelle : **830,3 mm** ; 30 années pour chaque mois. Les 12 valeurs mensuelles ci-dessous sont identiques au fichier (vérifié le 14/11 par la relecture critique).

Les sites grand public donnent de 750 à 1 110 mm selon la station et la période. Ils ne sont pas retenus.

## Comparaison (normales mensuelles, mm)

IMERG = maille 0,1° qui contient la station (6°10'28" N, 1°15'11" E, soit 6,174 °N, 1,253 °E ; maille 1,2-1,3 °E × 6,1-6,2 °N), moyenne 2001-2020. Le site « lome » (disque de 10 km) donne presque la même chose (1 008 mm/an).

| Mois | IMERG 2001-2020 | OMM 1991-2020 | Rapport |
|---|---|---|---|
| Jan | 12,7 | 13,3 | 0,95 |
| Fév | 32,5 | 16,4 | 1,98 |
| Mar | 73,3 | 67,3 | 1,09 |
| Avr | 106,7 | 97,3 | 1,10 |
| Mai | 163,9 | 148,8 | 1,10 |
| Juin | 195,3 | 180,5 | 1,08 |
| Juil | 90,6 | 74,4 | 1,22 |
| Août | 47,2 | 30,1 | 1,57 |
| Sep | 110,8 | 72,3 | 1,53 |
| Oct | 124,6 | 101,9 | 1,22 |
| Nov | 38,9 | 20,4 | 1,91 |
| Déc | 13,5 | 7,6 | 1,78 |
| **Année** | **1 010** | **830** | **1,22** |

Région Maritime entière (IMERG) : 1 065 mm/an. La pluie augmente quand on s'éloigne de la côte.

Deuxième station côtière (fichier NOAA voisin `ANEHO_65445.csv`, même dossier) : Aného, **909,3 mm**/an (26 à 29 années selon le mois). La maille IMERG correspondante donne 1 071 mm, soit **×1,18**. Réserve : la longitude de la station (1,600°) tombe sur un bord de maille.

## Constat

- **Le cycle saisonnier est juste** : pic en juin, petite saison sèche en août, seconde saison en septembre-octobre. C'est le régime bimodal du sud du Togo.
- **La grande saison des pluies (mars-juin) est à +8-10 %** : bon accord.
- **IMERG surestime de ~22 % le total annuel.** L'écart vient surtout des mois peu pluvieux : petite saison sèche (août-septembre, +55 %) et transitions (février, novembre-décembre, ×1,8 à ×2).

## Explications possibles

1. **Petites pluies surestimées** (le plus défendable) : sur la forêt humide du Ghana, IMERG produit des fausses alarmes de faible intensité (plus d'un cinquième de la pluie totale), surestime les faibles convections et se dégrade pendant la petite saison sèche (juillet-août). Maranan et al. 2020, *J. Hydrometeorol.* 21, 729-749, doi:10.1175/JHM-D-19-0257.1. Cela colle avec les rapports ×1,5 à ×2 hors des grandes saisons. Étude faite à l'intérieur des terres, pas sur la côte.
2. Calage pluviométrique du Final Run (GPCC) à 1° seulement : il ne corrige pas un gradient local côte-intérieur. Plausible, non vérifié.
3. Périodes différentes : 1991-2020 contre 2001-2020. Effet non chiffré.
4. Point contre maille : explication **faible** ici. La maille ne dépasse 6,2 °N que de ~3 km au nord de la station ; elle contient sans doute une bande de mer (non mesuré). Le même biais à Aného (×1,18) va dans le même sens.

## Conséquences pour AGBÉA

- Les **anomalies en %** et les comparaisons « cette année vs normale » en % sont calculées contre la climatologie IMERG elle-même : un biais **multiplicatif** s'y annule. Ce sont elles qu'il faut mettre en avant.
- Les **anomalies en mm** restent gonflées dans la même proportion (~20 %) que les totaux.
- Les **totaux en mm** gardent la mention « estimation satellite ». Pour la côte, on peut ajouter : « environ 20 % au-dessus des pluviomètres de Lomé et d'Aného (normales OMM 1991-2020) ».
- Ne pas présenter IMERG comme la pluie « mesurée » à Lomé.
