# Glossaire et questions fréquentes AGBÉA CLIMAT

Source : AGBÉA CLIMAT, règles de calcul de l'application et méthodologie des données
(docs/data/methodologie.md, docs/data/contrat-donnees.md).

## Glossaire

- **Normale** : moyenne du même mois sur 2001-2020, dans la même zone et pour le même indicateur.
  Exemple : la normale de juillet est la moyenne des vingt mois de juillet de 2001 à 2020.
- **Écart à la normale (anomalie)** : différence entre la valeur du mois et sa normale. Pour la pluie et la
  végétation, il est donné en pourcentage ; pour la température du sol, en degrés.
- **Au-dessus / en dessous de la normale** : règle AGBÉA CLIMAT. Pluie et végétation : écart supérieur à +10 %
  ou inférieur à -10 %. Température du sol : écart supérieur à +1,5 °C ou inférieur à -1,5 °C. Entre les deux,
  le mois est « proche de la normale ».
- **Tendance** : évolution sur plusieurs années, testée avec le test de Mann-Kendall au seuil de 5 % et mesurée
  par la pente de Sen (par décennie). AGBÉA CLIMAT ne parle de tendance que si le test est significatif.
- **Faible couverture** : moins de la moitié de la zone était visible ce mois-là (nuages). La valeur repose sur
  une petite partie de la zone et doit être lue avec prudence.
- **NDVI (indice de végétation)** : mesure de la verdeur des plantes, de -1 à +1. Plus la valeur est haute,
  plus la végétation est verte et dense. Ce n'est ni la quantité de récolte ni le type de culture.
- **Température du sol (LST)** : température de la surface vue par satellite (sol, champs, toits, routes,
  feuillage). Ce n'est pas la température de l'air donnée par la météo.
- **IMERG** : estimation de la pluie par satellites de la NASA. La version « Final », recalée sur les pluviomètres,
  est utilisée pour les séries.
- **Région, préfecture, site pilote** : le Togo compte 5 régions (Maritime, Plateaux, Centrale, Kara, Savanes)
  et 39 préfectures. Les 7 sites pilotes d'AGBÉA CLIMAT sont : Grand Lomé et Lagune ; Aného et Littoral de Kpémé ;
  Kpalimé et Mont Agou ; Sokodé et Corridor Fazao ; Kara et Massif de Défalé ; Dapaong et Confins Sahéliens ;
  Mango et Bassin fluvial de l'Oti.

## Questions fréquentes

**AGBÉA CLIMAT peut-il dire s'il va pleuvoir demain ?**
Non. AGBÉA CLIMAT montre ce que les satellites ont déjà observé. Il ne fait aucune prévision. Pour la météo
à venir et les alertes, consultez l'Agence nationale de la météorologie du Togo (ANAMET) et les services officiels.

**Pourquoi la pluie s'arrête-t-elle en 2025 ?**
La version fiable d'IMERG (Final) est publiée par la NASA plusieurs mois après le mois observé. AGBÉA CLIMAT
attend cette version plutôt que de montrer une estimation provisoire. Le dernier mois disponible est indiqué
avec chaque valeur.

**Pourquoi la température du sol s'arrête-t-elle en décembre 2022 ?**
Le satellite Terra, qui porte le capteur utilisé, dérive sur son orbite depuis 2020 et passe de plus en plus tôt
le matin, quand le sol est plus frais. À partir de 2023, cette dérive fausse les mesures. AGBÉA CLIMAT ne publie
donc pas de température du sol après décembre 2022, et calcule les tendances de température jusqu'en 2020.

**Pourquoi une valeur est-elle marquée « peu fiable » ?**
Parce que les nuages cachaient plus de la moitié de la zone ce mois-là. C'est fréquent en saison des pluies,
surtout dans la région Maritime.

**La pluie affichée est-elle celle de mon village ?**
Non. C'est une moyenne sur toute la zone choisie (région, préfecture ou site), estimée sur une grille d'environ
11 km. Sur la côte, la pluie satellite est un peu plus forte que celle des pluviomètres : les écarts à la normale
en pourcentage sont plus fiables que les millimètres.

**Quelle est la différence entre la température du sol et la température de l'air ?**
La température du sol est celle de la surface vue par le satellite ; un sol nu au soleil peut être bien plus chaud
que l'air. La météo donne la température de l'air, mesurée sous abri. Les deux ne sont pas directement comparables.

**Un NDVI bas veut-il dire une mauvaise récolte ?**
Pas forcément. Un NDVI plus bas que la normale en pleine saison des pluies peut signaler un manque de pluie,
des semis tardifs ou une végétation stressée, mais il ne mesure pas le rendement. Il faut le confirmer sur le terrain.

**D'où viennent les données ?**
De la NASA : GPM IMERG (pluie), MODIS Terra (végétation et température du sol), NASADEM (altitude). Les limites
administratives viennent de la Plateforme Géodata du Togo (geodata.gouv.tg), via le projet MAP TOGO.
