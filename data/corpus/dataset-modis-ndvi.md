# Fiche dataset : végétation MODIS Terra MOD13A1 v061 (NDVI)

Source : https://lpdaac.usgs.gov/products/mod13a1v061/

## Identité du produit

- Nom : MODIS Terra MOD13A1, version 061 (indices de végétation, 16 jours, 500 m).
- Fournisseur : NASA LP DAAC.
- Citation : doi:10.5067/MODIS/MOD13A1.061.
- Variable utilisée : `500m_16_days_NDVI`.
- Indicateur AGBÉA : `ndvi` (verdure de la végétation), sans unité.
- Identifiant dans l'API : `modis_ndvi`.

## Ce que contient le produit

Le capteur MODIS est à bord du satellite Terra de la NASA. MOD13A1 donne deux indices de végétation par pixel : le NDVI et l'EVI. AGBÉA utilise le NDVI.

Chaque image est un « composite » de 16 jours. Pour chaque pixel, le traitement NASA choisit la meilleure observation de la période : peu de nuages, angle de visée faible, valeur d'indice élevée.

- Résolution spatiale : 500 m.
- Pas de temps : composite 16 jours, agrégé au mois par AGBÉA.
- Couverture : globale.
- Début des données : 18 février 2000.
- Le produit inclut une couche de fiabilité du pixel (`pixel_reliability`), notée de 0 à 3, avec −1 pour « vide ».

## Ce que fait le pipeline AGBÉA

1. **Contrôle qualité** : on garde `pixel_reliability` 0 (bon) et 1 (marginal). On rejette −1 (vide), 2 (neige ou glace) et 3 (nuage).
2. **Satellite unique** : seul Terra est utilisé, pour avoir une série homogène depuis 2000. Le satellite Aqua ne démarre qu'en 2002.
3. **Grille** : reprojection sur une grille régulière de 0,005° (plus proche voisin), après le masque qualité.
4. **Mois** : chaque composite de 16 jours est rattaché au mois qui contient son milieu. La valeur mensuelle d'un pixel est la moyenne de ses composites valides.
5. **Moyenne par région** : moyenne pondérée par la part de chaque pixel couverte par la région (sur-échantillonnage ×3).
6. **Arrondi** : 3 décimales.

Le géoréférencement a été contrôlé sur des repères connus, par exemple le lac Togo, qui apparaît en NDVI négatif.

## Champs livrés pour chaque région et chaque mois

- `value` : NDVI moyen des pixels visibles de la région. Il vaut `null` seulement si aucun pixel n'est visible.
- `valid_frac` : part de la région couverte par des pixels valides. Les nuages la font baisser.
- `low_coverage` : vrai si `valid_frac` est inférieur à 0,5. La valeur est alors peu représentative et doit être signalée à l'utilisateur.

Exemple réel cité par l'équipe : en août 2024, seulement 14 % de la région Kara était visible. L'API répond quand même, mais avec `low_coverage` à vrai.

## Normales, saisons et tendances

- Période de référence : 2001-2020.
- Anomalie = valeur du mois − moyenne du même mois sur 2001-2020.
- Moyenne annuelle publiée seulement s'il y a au moins 10 mois valides sur 12.
- Tendances : test de Mann-Kendall et pente de Theil-Sen, sur au moins 10 années. Une tendance n'est annoncée que si elle est significative.

## Limites à rappeler

- En saison des pluies, les nuages font des trous fréquents, surtout sur la côte (juin-septembre). Il faut regarder `valid_frac`.
- Le NDVI mesure la verdeur. Il ne mesure ni la biomasse, ni le type de culture, ni le rendement.
- La saisonnalité est forte. Il faut comparer les mêmes mois d'une année à l'autre.
- Depuis 2022, l'orbite de Terra dérive : il passe plus tôt le matin. Le NDVI peut en être légèrement affecté. Les tendances qui finissent après 2022 sont à lire avec prudence.
- Ces données décrivent le passé. Elles ne sont pas une prévision.
