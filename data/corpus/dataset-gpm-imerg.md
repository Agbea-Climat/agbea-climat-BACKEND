# Fiche dataset : pluie NASA GPM IMERG (Final Run V07, mensuel)

Source : https://disc.gsfc.nasa.gov/datasets/GPM_3IMERGM_07/summary

## Identité du produit

- Nom : NASA GPM IMERG Final Run V07, produit mensuel GPM_3IMERGM.
- Fournisseur : NASA GES DISC.
- Citation : doi:10.5067/GPM/IMERG/3B-MONTH/07.
- Indicateur AGBÉA : `precipitation` (pluie du mois), en millimètres.
- Identifiant dans l'API : `gpm_imerg`.

## Ce que contient le produit

IMERG estime la pluie à partir de satellites. Il combine les mesures micro-ondes des satellites de la constellation GPM et les images infrarouges des satellites géostationnaires.

La version « Final Run » est ajustée sur des analyses mensuelles de pluviomètres au sol. C'est donc un produit « satellite + pluviomètres ». Il reste une estimation.

- Résolution spatiale : 0,1° × 0,1°, soit une maille d'environ 11 km.
- Pas de temps : mensuel.
- Couverture : globale, complète entre 60° N et 60° S. Le Togo est entièrement couvert.
- Début des données NASA : janvier 1998.
- Délai de publication : le Final Run sort environ 3 à 4 mois après le mois observé. Le dernier mois disponible a donc toujours plusieurs mois de retard.

## Ce que fait le pipeline AGBÉA

1. **Grille** : la grille native de 0,1° est gardée telle quelle. L'emprise de travail va de −0,3 à 2,0 °E et de 6,0 à 11,3 °N.
2. **Nettoyage** : les valeurs négatives et les valeurs manquantes (`_FillValue`) sont masquées.
3. **Conversion** : le produit mensuel donne un taux moyen en mm/h. Le pipeline le convertit en cumul du mois : taux × 24 × nombre de jours du mois.
4. **Moyenne par région** : pour chaque région (maritime, plateaux, centrale, kara, savanes), la valeur est une moyenne pondérée par la part de chaque maille couverte par la région. Ces parts sont calculées par sur-échantillonnage (×20). C'est important pour la pluie, car une maille de 11 km déborde souvent sur deux zones.
5. **Arrondi** : la pluie est livrée avec 1 décimale.

## Champs livrés pour chaque région et chaque mois

- `value` : cumul de pluie du mois, en mm.
- `valid_frac` : part de la surface de la région couverte par des mailles valides (de 0 à 1). Pour la pluie, elle est en général proche de 1.
- `low_coverage` : vrai si `valid_frac` est inférieur à 0,5. La valeur est alors peu représentative et doit être signalée.

Les séries AGBÉA commencent en janvier 2001.

## Normales et anomalies

- La période de référence est **2001-2020**. Ce n'est pas la normale officielle OMM 1991-2020, car MODIS ne couvre pas cette période et AGBÉA utilise la même référence pour tous les indicateurs.
- Anomalie du mois = valeur du mois − moyenne du même mois sur 2001-2020.
- Pour la pluie, l'écart est aussi donné en % : (valeur / moyenne − 1) × 100.

## Saisons et tendances

- Agrégats : `annual` (12 mois), `jfm` (janvier-mars, saison sèche), `mjjaso` (mai-octobre, saison des pluies).
- La pluie d'une saison est un cumul. Il n'est calculé que si tous les mois sont présents. Une saison pas encore terminée n'est jamais publiée.
- Les tendances utilisent le test de Mann-Kendall (seuil 0,05) et la pente de Theil-Sen, sur au moins 10 années.
- On ne parle de « tendance » que si le test est significatif. Sinon, on dit « pas de tendance nette sur la période ».
- Le test ne donne pas la cause d'une tendance.

## Limites à rappeler

- C'est une estimation satellite, pas une mesure de pluviomètre.
- Une maille d'environ 11 km représente une zone, pas un champ ou un village précis.
- Le Final Run est publié avec environ 3 mois de retard ou plus.
- Les séries AGBÉA partent de 2001-01 (normales 2001-2020).
- Ces données décrivent le passé. Elles ne sont pas une prévision météo.
