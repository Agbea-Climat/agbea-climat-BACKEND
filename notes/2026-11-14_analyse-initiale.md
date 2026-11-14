# Analyse initiale — 14/11/2026

Point de départ du volet « données » (rôles 2 et 3 du guide d'équipe : science des données + géospatial/ingénierie).

## Ce qui a été analysé

| Élément | Où | Statut |
|---|---|---|
| Pitch EN, 14 slides | `AGBEA_CLIMAT_NASA_Space_Apps_2026_EN.pdf` (fourni dans la conversation) | lu |
| Guide d'équipe FR (rôles, MVP, calendrier, intégrité scientifique) | `../AGBEA_CLIMAT_FR.docx` / `.pdf` | lu |
| Front déployé | <https://agbea-climat.vercel.app> (bundle Vite/React) | audité (voir plus bas) |
| Conversation claude.ai d'origine | lien `claude.ai/chat/…` | **inaccessible depuis Claude Code** : à recopier dans `notes/` si elle contient des décisions |
| Projets locaux réutilisables | projets locaux MAP TOGO et CARTO TOGO / 3dMaps (hors dépôt) | inventoriés |

## Ce que dit le guide d'équipe (l'essentiel pour nous)

- Défi visé : **n° 2, « Become a Detective of Earth System Trends »**. Il faut analyser de **vraies variables mesurées dans le temps** : où ça change, de combien, et si la tendance est significative.
- MVP : un lieu pilote (Lomé, avec Kara en comparaison), **un indicateur principal** et un indicateur secondaire facultatif. Pour chaque chiffre : carte, graphique, source, unités, résolution et période.
- « Une carte avec une tendance réelle et bien expliquée vaut mieux que cinq indicateurs inachevés. »
- Intégrité (§7) : ne jamais faire passer des valeurs fictives pour des observations NASA. Séparer observation et interprétation. Ne dire « significatif » qu'avec une méthode adaptée.
- Mise à disposition (§8) : « un CSV/GeoJSON traité ou une petite API suffit ». FastAPI et PostGIS sont facultatifs.

## Audit du front déployé : données fictives présentées comme réelles

Le bundle `index-*.js` ne fait **aucun appel réseau de données**. Tout est codé en dur. Plusieurs valeurs sont présentées comme des mesures alors qu'aucune chaîne de traitement n'existait :

| Affiché | Problème |
|---|---|
| « marge d'incertitude de ±12 % validée sur les stations synoptiques ANAMET » | aucune validation n'a été faite |
| « +8,4 °C ICU Lomé », « +0,16 °C/décennie » | chiffres sans calcul derrière |
| « Pic pluviométrique 2026 », série annuelle jusqu'en **2026** | l'année 2026 n'est pas terminée ; IMERG Final s'arrête en 2025-09 |
| « normale climatologique trentenaire ANAMET » | pas de données ANAMET dans le projet |
| Recul du trait de côte « ±4,8 m », `coastalShorelineDisplacementM` jusqu'à −52,8 m | aucune extraction Landsat faite |
| `floodRiskScore`, `droughtIndex` (« DSI Multi-Sensor ») | scores composites sans méthode |
| Capteurs cités : Sentinel-2, ECOSTRESS 70 m | hors des sources NASA retenues par le pitch ; non traités |
| 7 sites avec `latestObservations` (pluie 30 j, LST, NDVI…) | valeurs inventées |

C'est contraire au guide (§7) et aux slides 9-10 du pitch (« status shown honestly », « every piece of information needs a source »). Un jury qui ouvre la méthodologie le verra.

**Recommandation** : brancher le front sur `data/api/` (voir `docs/contrat-donnees.md`, qui donne la correspondance champ par champ). Retirer ce qui n'a pas de source ou l'étiqueter « exemple ». Ce que nous ne pouvons pas encore fournir : scores composites, trait de côte, données ANAMET.

## Cohérence du pitch avec les données réelles

- Slide 10 : IMERG « Period June 2000 – present ». En **V07**, la série commence en **janvier 1998**, car l'ère TRMM a été retraitée. À corriger, ou à garder si l'on veut parler de la période utilisée (nous partons de 2001).
- Slide 4 : « SRTM 30 m ». Nous utilisons **NASADEM**, version retraitée de SRTM par la NASA (2020). Formulation possible : « SRTM (NASADEM) ».
- Slide 6 : la courbe « Monthly precipitation, current vs historical average » correspond exactement à `recent_monthly` + `climatology`. On peut la remplacer par la vraie dès qu'IMERG est chargé.
- Slide 3 : le site d'Aného a pour risque principal l'érosion côtière, qu'aucun produit n'alimente encore (voir Questions).

## Ressources locales réutilisées

- **MAP TOGO** : limites PRISE (geodata.gouv.tg) **et** COD-AB HDX. On reprend **HDX** (licence CC BY-IGO). Le README de MAP TOGO rappelle que la réutilisation publique des données geodata.gouv.tg « peut être soumise à une contrepartie financière ».
- **CARTO TOGO / 3dMaps** : MNT TessaDEM et analyse hydrologique (HAND, drainage) pour la région Maritime. C'est une piste pour une couche « zones basses / stagnation » plus tard ; pas utilisé pour l'instant, car ce n'est pas une source NASA.

## Questions ouvertes pour l'équipe

1. **Backend** : quelle technologie (FastAPI ? Node ? Supabase ?) et quel dépôt Git ? Le contrat de données est volontairement neutre : Parquet, CSV, JSON et GeoTIFF.
2. **Indicateur principal du MVP** : le guide demande d'en choisir un. NDVI et LST sont disponibles dès maintenant ; la pluie IMERG l'est dès qu'un compte Earthdata existe. Proposition : **pluie (IMERG)** en indicateur principal, puisque c'est la donnée phare du pitch, et **NDVI** en secondaire.
3. **Compte NASA Earthdata** : qui le crée ? (5 min, gratuit, voir `docs/acces-donnees.md`.)
4. **Érosion côtière** : à faire maintenant (extraction du trait de côte Landsat par NDWI, plusieurs jours de travail fiable) ou en phase 2 ? En attendant, le front ne doit pas afficher de chiffres de recul.
5. **Sites** : rayon de 10 km pour tous ? Pour « Grand Lomé », le contour de la commune ou de la préfecture du Golfe serait peut-être plus parlant. Les fiches des préfectures existent déjà.
6. **Conversation claude.ai d'origine** : à coller dans `notes/` si elle contient des décisions qui ne sont pas ici.
