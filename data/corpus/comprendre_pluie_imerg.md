# Comprendre la pluie vue par satellite

Sources : NASA, page IMERG du programme GPM — https://gpm.nasa.gov/data/imerg ;
fiche GPM_3IMERGM V07 (NASA GES DISC) ; règles de calcul d'AGBÉA CLIMAT (normales et seuils).

## Comment un satellite « voit » la pluie

Aucun satellite ne recueille la pluie comme un pluviomètre. Les capteurs micro-ondes des satellites
de la constellation GPM fournissent l'estimation principale de la pluie à chaque passage. Entre deux passages,
les images infrarouges des satellites géostationnaires, qui observent en continu, servent à suivre les nuages.
L'algorithme IMERG combine toutes ces mesures et produit une estimation toutes les demi-heures.

IMERG existe en trois versions :
- **Early Run** : disponible environ 4 heures après l'observation ;
- **Late Run** : environ 12 à 14 heures après ;
- **Final Run** : recalé chaque mois sur les pluviomètres au sol, publié en temps normal 3 à 4 mois
  après le mois observé. C'est la version la plus fiable, celle qu'utilise AGBÉA CLIMAT pour les séries mensuelles.
  Actuellement, la série de pluie d'AGBÉA CLIMAT s'arrête en septembre 2025, dernier mois publié en Final Run.

## Lire une valeur de pluie dans AGBÉA CLIMAT

- La valeur est le **cumul du mois** en millimètres, moyenné sur la région. 1 mm de pluie = 1 litre d'eau par m².
- La **normale** est la moyenne du même mois sur 2001-2020, dans la même région.
- L'**écart à la normale** en % dit si le mois a été plus sec ou plus humide que d'habitude. Règle AGBÉA CLIMAT :
  au-delà de +10 %, le mois est « au-dessus de la normale » ; en dessous de -10 %, « en dessous de la normale ».
- Une moyenne régionale lisse les contrastes : une région peut être proche de la normale
  alors qu'une partie a manqué de pluie.

## Ce que la pluie satellite ne dit pas

- Elle ne remplace pas les prévisions ni les alertes de la météorologie nationale.
- Elle ne mesure pas l'humidité du sol ni le niveau des rivières.
- Sur la côte, elle donne plus de pluie que les pluviomètres, surtout les mois peu pluvieux
  (voir « Limites des données AGBÉA CLIMAT »).
