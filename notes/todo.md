# TODO — volet données

## Bloquant

- [x] ~~Compte NASA Earthdata + jeton~~ : fait le 14/11, jeton dans `.env`, **expire le 2027-01-13** (à renouveler avant la démo si elle a lieu après).
- [x] ~~Docker~~ : image + compose (D14).
- [ ] Choix de l'**indicateur principal** du MVP, avec le responsable produit (proposition : pluie IMERG, NDVI en secondaire).
- [ ] Connaître la **techno du nouveau backend** et le **dépôt Git** commun : montage de `data/api` ou HTTP via `data-server` (voir `docs/docker.md`).
- [ ] DNS du réseau local : `files.pythonhosted.org` n'est pas résolu, ce qui casse `docker build`. Régler le DNS de Docker Desktop, ou le réseau (voir `docs/docker.md`).

- [ ] **Conditions de réutilisation geodata.gouv.tg** pour les limites officielles (D19) : contrepartie financière éventuelle pour une diffusion publique ? À vérifier avant la mise en ligne, sinon `admin_source: hdx`.

## Intégration avec le backend (14/11)

- [ ] Les `CLAUDE.md` restent dans l'**historique** Git (commits jusqu'à `b20dcab`). Pas de secret dedans. Réécrire l'historique seulement si l'équipe l'exige (force push, tout le monde reclone).
- [ ] Le dépôt est-il **public** ? Si oui, `data/reference/map_togo/` et `data/regions.geojson` (limites geodata.gouv.tg) sont déjà diffusés : voir la question des CGU ci-dessus.

- [x] ~~Fusionner le pipeline~~ : poussé sur `main` le 14/11 (`b20dcab`, puis nettoyage `977d716`).
- [x] ~~Dossier `agbea-climat-BACKEND/` imbriqué~~ (ancienne copie du mock) : supprimé le 14/11. Ses PDF étaient identiques à `docs/`.
- [x] ~~`backend/services/catalog.py`~~ : fiches corrigées (MOD13A1 500 m, NASADEM, IMERG V07 dès 1998-01) le 14/11.
- [ ] Les tests `real_data` sont maintenant **actifs** (monthly.parquet présent). 3 échouent tant que les mocks ne sont pas remplacés : M07 (`test_geojson_real_boundaries`), M14, M16. C'est le comportement prévu par `MISSIONS.md`. Bilan Docker du 14/11 : 40 passed, 8 failed (dont 5 préexistants), 3 skipped.
- [ ] L'API doit afficher un avertissement quand `low_coverage = true` (cf. D22).
- [ ] Diffusion de `data/api/` (non versionné, ~110 Mo) pour les coéquipiers sans jeton Earthdata : release GitHub ou stockage partagé ?

## Prochaines étapes

- [ ] Tendances de pluie de signe opposé : IMERG ne montre aucune tendance (2001-2024), alors que MERRA-2 PRECTOTCORR affiche +100 à +200 mm/décennie\* sur plusieurs sites. Probablement des artefacts de la réanalyse (changements dans les observations assimilées). Ne jamais présenter la tendance MERRA-2 ; le garder comme contrôle des niveaux seulement (accord ±22 %).
- [ ] Valider quelques valeurs contre une source indépendante : normales ANAMET publiées si disponibles, ou CHIRPS (non NASA, en contrôle seulement).
- [ ] **LST de nuit** : +0,6 à +0,8 °C/décennie partout, même sur 2001-2019. À confirmer avec Aqua (MYD11A2, 2003-2025) avant tout usage dans le pitch. Décider si les tendances LST s'arrêtent à 2021 (dérive de Terra). Voir `notes/2026-11-14_resultats-premiere-analyse.md`.
- [ ] Pluie de Lomé (~1 000 mm/an selon IMERG) : comparer aux normales ANAMET publiées (~800-900 mm ?).
- [ ] Supprimer le cache HDF4 `data/raw/modis_hdf/` (2,1 Go) si on n'a pas besoin de retraiter 2025.
- [ ] Couches pour le front : PNG colorés (ou tuiles via titiler) à partir de `layers/*.tif`, avec des palettes cohérentes avec le front.
- [ ] Taille de `data/api/` : décider ce qui est versionné. `layers/elevation/elevation.tif` et `monthly.csv` sont lourds ; options : Git LFS, stockage objet, ou ne versionner que les fiches et tables Parquet.
- [ ] Automatiser la mise à jour (tâche planifiée hebdomadaire : ndvi/lst de l'année courante + imerg-daily + analyse + export).

## Plus tard (phase 2 du pitch)

- [ ] Érosion côtière : extraction du trait de côte Landsat C2 L2 par NDWI, composites annuels, transects tous les 100 m (méthode type DSAS) sur Lomé → Aného.
- [ ] Indicateur sécheresse documenté (ex. SPI à partir d'IMERG) pour remplacer le `droughtIndex` fictif du front.
- [ ] Zones basses / stagnation : réutiliser HAND de `CARTO TOGO/3dMaps/scripts/hydro.py` avec NASADEM au lieu de TessaDEM.
- [ ] Extension à d'autres pays : le code est paramétré par `bbox` et les COD-AB ; prévoir un dossier de config par pays.
