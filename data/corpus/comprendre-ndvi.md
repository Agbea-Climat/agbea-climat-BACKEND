# Comprendre le NDVI, l'indice de verdure de la végétation

Source : https://lpdaac.usgs.gov/products/mod13a1v061/

## Ce que mesure l'indicateur

Le NDVI est un indice de végétation. Il dit à quel point une surface est verte, vue depuis l'espace.

Les plantes vertes renvoient beaucoup de lumière proche infrarouge, invisible pour nos yeux. Elles absorbent une grande partie de la lumière rouge. Le satellite compare ces deux lumières. Il en tire un chiffre : le NDVI.

AGBÉA utilise le NDVI du capteur MODIS, à bord du satellite Terra de la NASA (produit MOD13A1). Les pixels font 500 m. Une image est produite tous les 16 jours, puis AGBÉA calcule une moyenne par mois et par région.

## Comment lire une valeur

Le NDVI n'a pas d'unité. Il va de −1 à 1.

- **Valeur négative** : eau. Par exemple, le lac Togo apparaît en NDVI négatif.
- **Valeur proche de 0** : sol nu, sable, routes, toits.
- **Valeur moyenne** : végétation clairsemée, herbe sèche, cultures jeunes.
- **Valeur haute** (vers 0,8) : végétation dense et très verte, comme une forêt ou une culture bien développée.

Plus la valeur est haute, plus la terre est verte.

## Bien comparer

- Le NDVI change beaucoup selon la saison. La végétation verdit avec les pluies et jaunit en saison sèche.
- Il faut donc comparer **le même mois** d'une année à l'autre. Comparer août à février ne dit rien d'utile.
- AGBÉA donne l'**anomalie** : la différence entre la valeur du mois et la moyenne du même mois sur 2001-2020. Une anomalie négative veut dire une végétation moins verte que d'habitude pour ce mois.
- Le NDVI réagit souvent avec un peu de retard à la pluie : les plantes ont besoin de temps pour pousser.

## Pièges à éviter

**Les nuages.** Le satellite ne voit pas à travers les nuages. En saison des pluies, beaucoup de pixels sont cachés, surtout sur la côte entre juin et septembre. AGBÉA indique la part de la région réellement visible (`valid_frac`). Si moins de la moitié de la région est visible, la valeur est marquée « couverture faible » (`low_coverage`). Il faut alors la lire avec prudence. Par exemple, en août 2024, seulement 14 % de la région Kara était visible.

**Verdure n'est pas récolte.** Le NDVI mesure la verdeur. Il ne mesure pas la quantité de grains, le type de culture ou le rendement. Une mauvaise herbe verte et un champ de maïs vert peuvent avoir le même NDVI.

**Une moyenne régionale.** La valeur mélange forêts, champs, villages, villes et plans d'eau. Une région avec beaucoup de ville ou d'eau aura un NDVI plus bas, sans que les cultures aillent mal.

**Le satellite vieillit.** Depuis 2022, le satellite Terra passe un peu plus tôt le matin. Cela peut légèrement modifier le NDVI. Les tendances récentes sont à lire avec prudence.

**Pas une prévision.** Le NDVI décrit l'état passé de la végétation. Il ne prédit pas la récolte à venir.

## Questions fréquentes

**Mon champ est vert, mais le NDVI de ma région est bas. Pourquoi ?**
La valeur est une moyenne sur toute la région. Votre champ ne pèse presque rien dans cette moyenne. Des nuages ont aussi pu cacher une partie de la région.

**Un NDVI plus bas que d'habitude veut-il dire sécheresse ?**
Pas forcément. Cela peut venir d'un manque de pluie, mais aussi d'un retard des semis, de feux, de récoltes déjà faites ou de nuages. Il faut croiser avec la pluie et avec ce qu'on observe sur le terrain.

## Ce qu'il faut retenir

- NDVI = verdeur, de −1 (eau) à 1 (très vert).
- On compare toujours le même mois d'une année à l'autre.
- Vérifier la part visible : les nuages faussent les mois de pluie.
- Verdeur n'est pas rendement.
