# Accès aux sources de données

| Source | Produits | Compte | Comment le pipeline y accède |
|---|---|---|---|
| NASA GES DISC | GPM IMERG V07 (mensuel Final, journalier Late) | **NASA Earthdata (gratuit)** | OPeNDAP : seule la fenêtre du Togo est téléchargée (~5 Ko par fichier) |
| Microsoft Planetary Computer | MODIS MOD13A1 / MOD11A2 v061, NASADEM | aucun | STAC + lecture fenêtrée des COG (jetons SAS anonymes) |
| NASA POWER | MERRA-2 : T2M, PRECTOTCORR | aucun | API REST mensuelle par point |
| OCHA HDX | COD-AB Togo | aucun | copie locale depuis le projet `MAP TOGO` |

Les données MODIS et NASADEM de Planetary Computer sont des copies à l'identique des fichiers NASA LP DAAC (mêmes DOI). Le pipeline cite donc le produit NASA, pas Microsoft.

### Trous de la copie Planetary Computer → NASA LP DAAC

La copie Planetary Computer est incomplète. Le 14/11/2026, elle n'avait **aucun composite MODIS de fin juin à mi-novembre 2025**, Terra comme Aqua, alors que le catalogue NASA (CMR) les a tous.

Pour chaque année, le pipeline compare donc les dates de composite du CMR à celles de Planetary Computer. Les manquantes sont téléchargées depuis **LP DAAC** (`data.lpdaac.earthdatacloud.nasa.gov`, même jeton Earthdata) au format HDF4 d'origine, lues avec `pyhdf` puis géoréférencées avec les coins de tuile de `StructMetadata.0`.

- Il faut télécharger la tuile complète, car aucun sous-ensemble n'est proposé : ~69 Mo par tuile NDVI, ~2,5 Mo par tuile LST. Le trou 2025 représentait ~1,9 Go (NDVI) et ~0,3 Go (LST). Débit constaté : ~0,2 Mo/s par connexion.
- Les HDF sont gardés en cache dans `data/raw/modis_hdf/` ; on peut les supprimer une fois les cubes écrits.
- Le tag `source` de chaque cube mensuel indique `Planetary Computer`, `LP DAAC` ou les deux.
- Sans jeton Earthdata, ce contrôle est sauté et les mois concernés restent absents.

## Créer l'accès NASA Earthdata (IMERG)

1. Créer un compte sur <https://urs.earthdata.nasa.gov/users/new>.
2. Dans le profil, menu **Applications → Authorized Apps → Approve More Applications**, autoriser **NASA GESDISC DATA ARCHIVE**. Sans cette étape, les téléchargements sont refusés même avec un bon mot de passe.
3. Menu **Generate Token** : générer un jeton (valable 60 jours).
4. À la racine du projet, copier `.env.example` en `.env` et y coller :
   ```
   EARTHDATA_TOKEN=eyJ0eXAiOiJKV1Qi...
   ```
   Le fichier `.env` n'est jamais versionné. Autres possibilités : `EARTHDATA_USERNAME` + `EARTHDATA_PASSWORD` dans `.env`, ou un `~/_netrc` (Windows) / `~/.netrc` avec `machine urs.earthdata.nasa.gov login … password …`.
5. Lancer :
   ```
   .venv\Scripts\python -m pipeline imerg          # mensuel 2001 → dernier mois Final (~300 petits fichiers)
   .venv\Scripts\python -m pipeline imerg-daily    # 45 derniers jours (Late Run)
   .venv\Scripts\python -m pipeline analyse
   .venv\Scripts\python -m pipeline export
   ```

Le jeton n'est envoyé qu'aux hôtes NASA (`*.earthdata.nasa.gov`, `*.eosdis.nasa.gov`), y compris après une redirection.

## Latences constatées (le 2026-11-14)

| Produit | Dernière donnée disponible |
|---|---|
| IMERG mensuel Final V07B | 2025-09 |
| IMERG journalier Late V07C | 2026-11-12 |
| MODIS MOD13A1 / MOD11A2 | quelques jours à 2 semaines |
| NASA POWER mensuel | année précédente complète (l'API mensuelle refuse l'année en cours) |

Conséquence : la **tendance pluie** s'arrête à 2024, dernière année complète en Final. La **pluie récente** vient du Late Run, signalé comme moins fiable.
