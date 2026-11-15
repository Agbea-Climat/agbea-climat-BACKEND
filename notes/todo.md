# TODO — volet données

## Bloquant

- [x] ~~Compte NASA Earthdata + jeton~~ : fait le 14/11, jeton dans `.env`, **expire le 2027-01-13** (à renouveler avant la démo si elle a lieu après).
- [x] ~~Docker~~ : image + compose (D14).
- [ ] Choix de l'**indicateur principal** du MVP, avec le responsable produit (proposition : pluie IMERG, NDVI en secondaire).
- [ ] Connaître la **techno du nouveau backend** et le **dépôt Git** commun : montage de `data/api` ou HTTP via `data-server` (voir `docs/docker.md`).
- [ ] DNS du réseau local : `files.pythonhosted.org` n'est pas résolu, ce qui casse `docker build`. Régler le DNS de Docker Desktop, ou le réseau (voir `docs/docker.md`).

## Intégration avec le backend (14/11)

- [ ] Les `CLAUDE.md` restent dans l'**historique** Git (commits jusqu'à `b20dcab`). Pas de secret dedans. Réécrire l'historique seulement si l'équipe l'exige (force push, tout le monde reclone).

- [x] ~~Fusionner le pipeline~~ : poussé sur `main` le 14/11 (`b20dcab`, puis nettoyage `977d716`).
- [x] ~~Dossier `agbea-climat-BACKEND/` imbriqué~~ (ancienne copie du mock) : supprimé le 14/11. Ses PDF étaient identiques à `docs/`.
- [x] ~~`backend/services/catalog.py`~~ : fiches corrigées (MOD13A1 500 m, NASADEM, IMERG V07 dès 1998-01) le 14/11.
- [ ] Les tests `real_data` sont maintenant **actifs** (monthly.parquet présent). 3 échouent tant que les mocks ne sont pas remplacés : M07 (`test_geojson_real_boundaries`), M14, M16. C'est le comportement prévu par `MISSIONS.md`. Bilan Docker du 14/11 : 40 passed, 8 failed (dont 5 préexistants), 3 skipped.
- [ ] L'API doit afficher un avertissement quand `low_coverage = true` (cf. D22).
- [ ] Diffusion de `data/api/` (non versionné, ~110 Mo) pour les coéquipiers sans jeton Earthdata : release GitHub ou stockage partagé ?

- [x] ~~Corpus RAG (P3)~~ : `data/corpus/` (10 documents + `sources.json`), le 15/11 (D29). Test `p3` vert.
- [x] ~~Mois en cours exporté~~ (2026-11 partiel dans `monthly.parquet`) : mois incomplets écartés le 15/11 (D28).
- [ ] **Pluie récente** : IMERG Final s'arrête en 2025-09 ; décider avec le produit et le backend si on ajoute IMERG Late (mensuel agrégé, jeu de données distinct « provisoire ») ou si on assume le trou.

- [x] ~~**LST de jour récente faussée**~~ (réglé par D30 : publiée jusqu'en 2022-12 ; VIIRS à étudier) (tests du 15/11, `notes/2026-11-15_tests-api.md`, D1) : écart Terra − Aqua −0,75 °C en 2023, −1,15 en 2024, −1,56 en 2025 ; les anomalies `lst_day` récentes de l'API (jusqu'à −3,7 °C) sont des artefacts de dérive d'orbite. Décider : couper `lst_day` du livrable P2 après 2022, publier les valeurs sans anomalie après 2022 (drapeau, contrat à changer), ou passer à VIIRS (orbite maintenue, depuis 2012).
- [x] ~~Rapport de tests de l'API~~ : points corrigés le 15/11 (à relire par l'équipe backend avant fusion).

- [x] ~~Exploiter les fiches de zone dans le chatbot~~ (15/11, `docs/chatbot-corpus.md` §5).
- [ ] Équipe : trancher l'usage des chiffres du corpus (règle 5) ; vider `EMBEDDING_MODEL` sur Dokploy.
- [ ] Corpus : ajouter des résumés sourcés (CDN 2021, PNACC, 4e Communication nationale, WACA).

## Prochaines étapes

- [ ] Tendances de pluie de signe opposé : IMERG ne montre aucune tendance (2001-2024), alors que MERRA-2 PRECTOTCORR affiche +100 à +200 mm/décennie\* sur plusieurs sites. Probablement des artefacts de la réanalyse (changements dans les observations assimilées). Ne jamais présenter la tendance MERRA-2 ; le garder comme contrôle des niveaux seulement (accord ±22 %).
- [ ] Valider quelques valeurs contre une source indépendante : normales ANAMET publiées si disponibles, ou CHIRPS (non NASA, en contrôle seulement).
- [x] ~~**LST de nuit**~~ : hausse confirmée par Aqua sur 2003-2020, mêmes mois (85 % des unités, les 5 régions, ~+0,5 °C/décennie). Tendances LST arrêtées à 2020 (D27). Pour le pitch : citer la fourchette Terra/Aqua 2003-2020, jamais les anciennes pentes 2001-2025.
- [ ] Tests multiples sur les cantons : appliquer un FDR (Benjamini-Hochberg) aux tendances, ou ne présenter que régions et sites.
- [ ] NDVI : la dérive de Terra peut aussi le toucher (non contrôlé). Contrôle possible avec MYD13A1 (Aqua).
- [x] ~~Pluie de Lomé~~ : IMERG 1 010 mm/an (2001-2020) contre **830,3 mm** (normales OMM 1991-2020, source primaire NOAA/NCEI) → +22 % ; Aného ×1,18. Surtout en mois peu pluvieux ; cycle saisonnier juste. Voir `notes/2026-11-14_validation-pluie-lome.md`.
- [ ] Supprimer le cache HDF4 `data/raw/modis_hdf/` (2,1 Go) si on n'a pas besoin de retraiter 2025.
- [ ] Couches pour le front : PNG colorés (ou tuiles via titiler) à partir de `layers/*.tif`, avec des palettes cohérentes avec le front.
- [ ] Taille de `data/api/` : décider ce qui est versionné. `layers/elevation/elevation.tif` et `monthly.csv` sont lourds ; options : Git LFS, stockage objet, ou ne versionner que les fiches et tables Parquet.
- [ ] Automatiser la mise à jour (tâche planifiée hebdomadaire : ndvi/lst de l'année courante + imerg-daily + analyse + export).

## Plus tard (phase 2 du pitch)

- [ ] Érosion côtière : extraction du trait de côte Landsat C2 L2 par NDWI, composites annuels, transects tous les 100 m (méthode type DSAS) sur Lomé → Aného.
- [ ] Indicateur sécheresse documenté (ex. SPI à partir d'IMERG) pour remplacer le `droughtIndex` fictif du front.
- [ ] Zones basses / stagnation : réutiliser HAND de `CARTO TOGO/3dMaps/scripts/hydro.py` avec NASADEM au lieu de TessaDEM.
- [ ] Extension à d'autres pays : le code est paramétré par `bbox` et les COD-AB ; prévoir un dossier de config par pays.
