# Premiers résultats sur données réelles — 14/11/2026

Exécution complète **dans Docker** (`analyse` + `export`), pipeline 0.1.0. Toutes les valeurs ci-dessous viennent de `data/api/` ; `*` = significatif (Mann-Kendall, p < 0,05). Pentes par décennie.

## Couverture

| Indicateur | Période | Remarques |
|---|---|---|
| Pluie IMERG Final | 2001-01 → 2025-09 (297 mois) | tendances sur 2001-2024 |
| Pluie IMERG Late (30 j) | 14/10 → 12/11/2026 | |
| NDVI MODIS Terra | 2001-01 → 2026-10 | trou Planetary Computer juillet-novembre 2025 comblé depuis LP DAAC |
| LST jour / nuit | 2001-01 → 2026-11 | idem |
| Air 2 m / pluie MERRA-2 | 2001 → 2025, 7 sites | |
| Altitude NASADEM | statique | |

Contrôles automatiques : **16/16 pass** (`data/api/validation.json`).

## Moyennes 2001-2020 (cohérence)

| Unité | Pluie IMERG (mm/an) | Pluie MERRA-2 | NDVI | LST jour (°C) | LST nuit | Air 2 m |
|---|---|---|---|---|---|---|
| Togo | 1 204 | – | 0,54 | 31,8 | 21,1 | – |
| Maritime | 1 064 | – | 0,59 | 30,9 | 21,3 | – |
| Savanes | 1 078 | – | 0,39 | 35,3 | 22,0 | – |
| Lomé | 1 008 | 1 098 | 0,33 | 34,8 | 23,2 | 26,9 |
| Kpalimé | 1 225 | 1 240 | 0,71 | 28,7 | 20,1 | 25,9 |
| Kara | 1 295 | 1 157 | 0,46 | 33,4 | 21,3 | 26,0 |
| Dapaong | 1 034 | 1 096 | 0,35 | 35,5 | 21,8 | 27,0 |

Le gradient sud-nord et les contrastes attendus sont retrouvés : forêt de Kpalimé verte et fraîche, savanes chaudes, îlot urbain de Lomé (NDVI 0,33, LST jour 34,8 °C contre 28,7 °C à Kpalimé). IMERG et MERRA-2 s'accordent à ±22 % au pire (Mango).

**À valider** (rôle 5) :
- La pluie de Lomé, ~1 000 mm/an, paraît élevée par rapport aux normales publiées pour la ville (~800-900 mm, « Dahomey Gap »). Hypothèse : la maille de 11 km mêle la ville et l'arrière-pays.
- Kpalimé (relief) pourrait être sous-estimé, ce que les satellites font souvent en orographie.
Il faut comparer à des normales ANAMET publiées.

## Tendances

| Indicateur / saison | Ce que montrent les données |
|---|---|
| **Pluie annuelle 2001-2024** | **aucune tendance significative**, ni pour le pays, ni pour une région, un site ou un canton (0 % des cantons). Pentes de −50 à +30 mm/décennie, non significatives |
| **NDVI annuel** | Togo +0,003 (ns). Significatif : Aného +0,029\*, Kpalimé +0,011\*, Dapaong +0,009\*. 33 % des cantons significatifs, dont 86 % en hausse (verdissement) |
| **NDVI saison sèche (JFM)** | même tableau, plus net : Savanes +0,004\*, Aného +0,036\*, Kpalimé +0,023\* |
| **LST jour** | rien de significatif à l'échelle du pays ou des régions ; Aného −0,57\* |
| **LST nuit** | **+0,6 à +0,8 °C/décennie partout, 100 % des cantons**. Voir plus bas avant tout usage |
| **Air 2 m (MERRA-2)** | Lomé +0,22\*, Aného +0,25\*, Kpalimé +0,33\* ; nord non significatif ; Mango −0,23\* |

### LST de nuit : résultat robuste mais à confirmer

- La hausse existe **avant** la dérive orbitale de Terra : 2001-2019, +0,61 °C/décennie, p < 0,001. Ce n'est donc pas seulement un artefact de la dérive.
- Mais son ampleur vaut environ 3 fois la hausse de l'air (+0,22 à Lomé), et la série saute après 2022 (21,1 → 22,2 → 22,7 °C), période de la dérive : passage de nuit plus tôt, donc plus chaud.
- **Avant de la montrer** : la comparer avec Aqua (MYD11A2, passage à 1 h 30, capteur indépendant) et à la LST de nuit de 2001-2021 seule. En attendant, ne pas la mettre en avant dans le pitch.

### NDVI annuel absent pour Lomé et la région Maritime

Sur la côte, la couverture nuageuse rend la plupart des mois de saison des pluies inexploitables (moins de 50 % de la zone valide). Il n'y a que 6 années NDVI annuelles valides pour Lomé et 8 pour la Maritime, sous le minimum de 10 pour un test. **Le NDVI de saison sèche (`jfm`) est l'indicateur à utiliser sur la côte.**

### Multiplicité des tests

1 741 des 4 887 séries testées sont significatives. Ce n'est pas « 36 % de vraies tendances » : la LST de nuit (100 % des cantons) gonfle le total, et des cantons voisins ne sont pas indépendants. Pour la démo, on s'en tient aux sites, aux régions et au pays.

## Pluie des 30 derniers jours (IMERG Late, 14/10 → 12/11/2026)

Déficit marqué au nord : Dapaong 3 mm contre une normale de 44 mm (−93 %), Kara −72 %, Savanes −82 %. Sud proche de la normale : Maritime −7 %. Cela peut traduire une fin de saison des pluies précoce au nord. **Prudence** : la valeur vient du Late Run, non calé sur les pluviomètres, alors que la normale vient du Final. Les deux produits ne sont pas strictement comparables.

## Ce qu'on peut raconter à la démo (proposition)

1. « Sur 24 ans, les satellites **ne montrent pas de tendance nette de la pluie annuelle** au Togo ; la variabilité d'une année à l'autre domine. » C'est un résultat honnête, qui illustre la méthode.
2. « La végétation de saison sèche **verdit** à Kpalimé, Aného et dans les Savanes (tendance significative). »
3. « L'air se réchauffe de ~0,2 à 0,3 °C par décennie sur la côte et à Kpalimé (MERRA-2). »
4. « Ces 30 derniers jours, il a beaucoup moins plu que d'habitude dans le nord (estimation quasi temps réel). »
