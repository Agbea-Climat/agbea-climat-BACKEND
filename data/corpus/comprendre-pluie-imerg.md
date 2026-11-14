# Comprendre la pluie vue par satellite (GPM IMERG)

Source : https://disc.gsfc.nasa.gov/datasets/GPM_3IMERGM_07/summary

## Ce que mesure l'indicateur

L'indicateur « Pluie du mois » donne la quantité de pluie tombée sur une région pendant un mois. Il est exprimé en millimètres (mm).

1 mm de pluie, c'est 1 litre d'eau tombé sur 1 mètre carré. 100 mm sur un mois, c'est donc 100 litres d'eau par mètre carré sur ce mois.

La donnée vient du produit NASA GPM IMERG. Des satellites observent les nuages et la pluie depuis l'espace. Le produit utilisé (« Final Run ») est ensuite corrigé avec des pluviomètres au sol, mois par mois.

## Comment lire une valeur

- La valeur est un **cumul sur tout le mois**. Elle ne dit pas s'il a plu un seul jour très fort ou un peu tous les jours.
- La valeur est une **moyenne sur toute la région**. Certaines parties de la région ont reçu plus, d'autres moins.
- Pour savoir si un mois a été sec ou humide, il faut le comparer à la **moyenne habituelle du même mois**. AGBÉA utilise la moyenne 2001-2020.
- L'**anomalie** est la différence avec cette moyenne. Une anomalie positive veut dire plus de pluie que d'habitude. Une anomalie négative veut dire moins.
- Pour la pluie, l'anomalie est aussi donnée en pourcentage. Par exemple, −20 % veut dire 20 % de pluie en moins que la moyenne du même mois.

## Exemples de lecture

- Comparer juillet 2024 à juillet 2023 a du sens. Comparer juillet à janvier n'en a pas : janvier est en saison sèche sur tout le pays.
- Au sud (Maritime, Plateaux), il y a en général deux saisons des pluies dans l'année. Au nord (Centrale, Kara, Savanes), il y en a une seule. Une courbe de pluie n'a donc pas la même forme au sud et au nord.
- Une saison complète se lit avec le cumul `mjjaso` (mai à octobre). Ce cumul n'est publié que si tous les mois sont disponibles.

## Pièges à éviter

**Satellite n'est pas pluviomètre.** IMERG est une estimation. Un pluviomètre mesure la pluie en un point précis. Le satellite estime la pluie moyenne sur une maille d'environ 11 km de côté. Les deux chiffres peuvent donc différer, même si les deux sont justes.

**Une zone, pas un champ.** Une valeur régionale ne dit pas ce qui s'est passé dans un champ ou un village précis. Un orage local peut être fort dans un village et faible dans le village voisin.

**Le retard des données.** Le produit Final Run est publié environ 3 mois (ou un peu plus) après le mois observé. Les derniers mois ne sont donc pas encore disponibles.

**Le cumul cache la répartition.** Un mois « normal » en cumul peut contenir une longue période sans pluie, puis de fortes pluies. Le cumul mensuel ne montre pas les poches de sécheresse au sein du mois.

**Pas une prévision.** Ces chiffres décrivent ce qui s'est passé. Ils ne disent pas ce qui va se passer. Pour la météo à venir, il faut suivre les bulletins officiels du service météorologique national.

**Tendance ou hasard ?** Une ou deux années sèches ne font pas une tendance. AGBÉA ne parle de tendance que si un test statistique (Mann-Kendall) la confirme sur au moins 10 années. Sinon, on dit « pas de tendance nette sur la période ».

## Ce qu'il faut retenir

- Pluie du mois = cumul en mm, moyenne sur la région.
- On compare toujours au même mois des autres années.
- C'est une estimation satellite corrigée par des pluviomètres, à environ 11 km.
- C'est une donnée du passé, pas une prévision.
