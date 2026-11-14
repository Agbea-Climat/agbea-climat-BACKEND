# AGBÉA CLIMAT — Fiche technique des missions backend

Contrat API v0.4 · Base `/api/v1` · 3 prérequis (P1–P3) + 27 missions (M01–M27).

- **Définition de « terminé »** : `pytest -m mXX` passe, la route apparaît dans `/docs`,
  la réponse respecte `app/schemas.py`, et un `curl` d'exemple est fourni au testeur.
- **Tests humains** (API + front) : voir `docs/AGBEA_CLIMAT_missions_FR.pdf` / `_EN.pdf`.
- **Markers pytest** : `m01` … `m27`, `p1` … `p3`, `llm` (appelle le LLM), `real_data`
  (exige les vraies données de `data/processed/`).

## Ordre et parallélisation

| Vague | Missions | Dépend de |
|---|---|---|
| 0 | P1 (structure) | — |
| 1 (en parallèle) | M01, M02, M27, M03–M05 · M06, M08 · M10–M13 · M21 · P2 (données) · P3 (corpus) | P1 |
| 2 | M07, M09 (contours réels) · M14–M18 (vraies séries) | P2 |
| 3 | M19, M20 | M14 |
| 4 | M22, M23 → M24 → M25, M26 | P3, M14 |

Deux agents ne travaillent jamais sur le même fichier `services/*.py` en même temps.

---

## Prérequis

### P1 — Structure du projet
- **Fichiers** : `app/main.py`, `app/core/*`, `app/routers/*`, `app/services/*`, `.env.example`.
- **Implémentation** :
  - Découper l'actuel `app/main.py` (monolithe mock) selon l'architecture de `CLAUDE.md`,
    sans changer aucun chemin ni aucune réponse.
  - `core/config.py` : `Settings` avec `DATA_DIR=data`, `DB_PATH=agbea.sqlite`,
    `CHROMA_DIR=.chroma`, `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`, `EMBEDDING_MODEL`,
    `CORS_ORIGINS`.
  - `core/errors.py` : handlers `HTTPException` et `RequestValidationError` → format
    `{"error": {...}}` (déjà écrits dans le mock, à déplacer).
  - Tant que P2 n'est pas fait, `services/store.py` peut renvoyer les mocks actuels.
- **Test** : `pytest -m "p1"` et tous les tests qui passaient avant passent toujours.

### P2 — Pipeline de données (Google Earth Engine)
- **Fichiers** : `scripts/export_gee.py`, `data/regions.geojson`,
  `data/processed/monthly.parquet`, `data/processed/static.json`.
- **Implémentation** :
  - Contours : geoBoundaries `TGO` niveau `ADM1` (GeoJSON simplifié). Ajouter dans
    `properties` un `id` parmi `maritime, plateaux, centrale, kara, savanes`
    (correspondance depuis `shapeName`).
  - Script GEE : moyenne spatiale par région (`reduceRegions`, `ee.Reducer.mean()`) et par mois,
    de 2001-01 au dernier mois disponible :

    | indicator | Collection GEE | Bande | Conversion |
    |---|---|---|---|
    | `precipitation` | `NASA/GPM_L3/IMERG_MONTHLY_V07` | `precipitation` | mm/h × heures du mois → mm |
    | `ndvi` | `MODIS/061/MOD13Q1` | `NDVI` | × 0.0001, moyenne des images du mois |
    | `lst_day` | `MODIS/061/MOD11A2` | `LST_Day_1km` | × 0.02 − 273.15 → °C |
    | `elevation` | `USGS/SRTMGL1_003` | `elevation` | statique : mean/min/max par région → `static.json` |

    Vérifier les identifiants et facteurs d'échelle dans le catalogue GEE avant de lancer.
  - `monthly.parquet` : colonnes `region_id` (str), `indicator` (str), `date` (`YYYY-MM`),
    `value` (float). Une ligne par région × indicateur × mois.
- **Test** : `pytest -m p2` (fichiers présents, colonnes, 5 régions, plages de valeurs).

### P3 — Corpus RAG
- **Fichiers** : `data/corpus/*.md|pdf`, `data/corpus/sources.json`.
- **Contenu minimal** (5 à 15 documents) :
  - une fiche par dataset (générée depuis `/datasets`) ;
  - explication simple de chaque indicateur (NDVI, LST, IMERG) en français ;
  - calendrier agricole par région du Togo (saisons, cultures principales) ;
  - un ou deux rapports publics sur le climat au Togo.
- `sources.json` : pour chaque fichier, `{ "file", "title", "source_url", "region_ids"?, "indicators"? }`.
- **Test** : `pytest -m p3`.

---

## Bloc 1 — Socle, profils et sessions

### M01 · `GET /health`
- **Fichier** : `routers/meta.py`.
- **Réponse** : `{"status": "ok"}`, 200, sans dépendance (pas de lecture disque ni DB).

### M02 · `GET /meta` → `AppMeta`
- **Fichiers** : `routers/meta.py`, `services/catalog.py`.
- `data_last_updated` = date du dernier mois présent dans `monthly.parquet` (format
  `YYYY-MM-DD`, dernier jour du mois). Avant P2 : valeur fixe.
- `features` : `map`, `chat` en `prototype` ; `voice` en `in_development` ; `ewe` en `planned`.

### M27 · `GET /profiles` → `Profile[]`
- **Fichiers** : `routers/profiles.py`, `services/catalog.py`.
- 4 profils statiques (`farmer`, `community`, `researcher`, `decision_maker`) — reprendre
  les valeurs du mock. `featured_indicators` ne contient que des `IndicatorId` valides.

### M03 · `POST /sessions` → `Session` (201)
- **Fichiers** : `routers/sessions.py`, `services/sessions.py`.
- Table SQLite `sessions(id TEXT PK, preferences TEXT JSON, created_at TEXT, last_seen_at TEXT)`.
- `session_id` = `uuid4`. Dates en ISO 8601 UTC.

### M04 · `GET /sessions/{id}` → `Session`
- Table `threads(thread_id TEXT PK, session_id TEXT, title TEXT, updated_at TEXT)`.
- Met à jour `last_seen_at`. `threads` triés par `updated_at` décroissant.
- Les threads sont créés par M25/M26 quand la requête porte le header `X-Session-Id`
  (titre = 60 premiers caractères du premier message).
- Inconnu → 404 `session_not_found`.

### M05 · `PATCH /sessions/{id}/preferences` → `Preferences`
- Mise à jour partielle (`exclude_unset`). `region_id` inconnu → 404 `region_not_found` ;
  `profile`, `lang` ou `mode` invalides → 422 `validation_error` (géré par Pydantic).

## Bloc 2 — Géographie

### M06 · `GET /regions` → `Region[]`
- **Fichiers** : `routers/regions.py`, `services/regions.py`.
- Après P2 : `centroid`, `bbox` et `area_km2` calculés depuis `regions.geojson` (shapely,
  surface en projection UTM 31N `EPSG:32631`). Ordre : du sud au nord
  (maritime, plateaux, centrale, kara, savanes).

### M07 · `GET /regions/geojson`
- Sert `data/regions.geojson` (chargé une fois au démarrage). `properties` = l'objet `Region`.
- Polygones réels (pas des rectangles), coordonnées `[lon, lat]`.

### M08 · `GET /regions/{id}` → `Region`
- Inconnu → 404 `region_not_found`.

### M09 · `GET /locate?lon=&lat=` → `Region`
- Point dans polygone avec shapely (`prepared` geometries). Hors Togo → 404 `outside_togo`.

## Bloc 3 — Catalogue et sources

### M10 · `GET /indicators` → `Indicator[]`
- **Fichiers** : `routers/catalog.py`, `services/catalog.py`.
- 4 indicateurs ; `elevation.has_timeseries = false` ; chaque `dataset_id` existe dans `/datasets` ;
  chaque `layer_id` (si présent) existe dans `/layers`.

### M11 · `GET /datasets` → `Dataset[]`
- 4 fiches statiques. Tous les champs remplis, `limitations` non vide, `source_url` en https.

### M12 · `GET /datasets/{id}` → `Dataset`
- Inconnu → 404 `dataset_not_found`.

### M13 · `GET /layers?mode=` → `MapLayer[]`
- Tuiles NASA GIBS (WMTS, `EPSG:3857`). **Vérifier les identifiants de couche dans Worldview /
  le catalogue GIBS** et les dates disponibles avant de figer.
- `url_template` contient `{z}`, `{x}`, `{y}` et `{date}` (le front remplace `{date}`).
- `legend` ≥ 2 stops. `mode=scientific` peut renvoyer des couches en plus.

## Bloc 4 — Observations et historique (`real_data`)

Toute la logique dans `services/indicators.py`, sur le DataFrame chargé par `services/store.py`.

- **Normale** : moyenne 2001–2020 du même mois calendaire, même région, même indicateur.
- **Anomalie** : `(value − baseline) / baseline × 100`, arrondie à 0,1. `null` si baseline = 0 ou absente.
- **Tendance** : `> +10` → `above_normal` ; `< −10` → `below_normal` ; sinon `normal` ;
  valeur absente → `unknown`. (Pour la température, utiliser l'écart en °C : `> +1,5` / `< −1,5`.)
- **Arrondis** : pluie 1 décimale, NDVI 3 décimales, température 1 décimale.

### M14 · `GET /regions/{id}/summary?date=YYYY-MM&mode=` → `RegionSummary`
- Un `IndicatorSnapshot` par indicateur à série (precipitation, ndvi, lst_day).
- `date` absente → dernier mois disponible.
- `plain_summary` : phrase générée par gabarit (pas de LLM), ex.
  « Pluie du mois : 18 % en dessous de la normale. »
- Résultat **déterministe** : deux appels identiques → même réponse.

### M15 · `GET /regions/{id}/timeseries?indicator&start&end&granularity` → `TimeSeries`
- Mois contigus de `start` à `end` (mois sans donnée → `value: null`).
- `granularity=year` : cumul annuel pour la pluie, moyenne pour NDVI et température.
- `indicator=elevation` → 400 `no_timeseries`. `start > end` → 400 `invalid_period`.

### M16 · `GET /regions/{id}/compare?indicator&a_start&a_end&b_start&b_end` → `Comparison`
- Bornes en années (`YYYY`). Statistiques sur les valeurs **annuelles** (cumul pluie, moyenne sinon).
- `delta_abs = b.mean − a.mean` ; `delta_pct = delta_abs / a.mean × 100`.
- Période invalide (début > fin, hors données) → 400 `invalid_period`.

### M17 · `GET /regions/{id}/timeseries/export?indicator&start&end&format=csv|json`
- Réutilise M15. CSV : lignes `# source: <nom> (<url>)`, `# units: <unités>`, puis
  `date,value,baseline,anomaly_pct`. Header `Content-Disposition: attachment; filename="agbea_<region>_<indicator>_<start>_<end>.<ext>"`.

### M18 · `GET /layers/{id}/before-after?before&after&region_id` → `BeforeAfter`
- `url_template` de la couche avec `{date}` remplacé par chaque date.
- Si `region_id` : `comparison` = M16 sur l'année de `before` vs l'année de `after`.
- Couche inconnue → 404 `layer_not_found`.

## Bloc 5 — Vues métier

### M19 · `GET /dashboard?date=` → `Dashboard`
- **Fichiers** : `routers/views.py`, `services/indicators.py`.
- `regions` = M14 pour les 5 régions.
- `highlights` : les 3 plus grandes anomalies absolues du mois (toutes régions/indicateurs),
  en phrases gabarit, `nature="observed"`, `source_ids=["ds:<dataset_id>"]`.

### M20 · `GET /regions/{id}/agriculture?date=` → `AgriInsight`
- `season` : dérivée du mois **et de la région** — sud (maritime, plateaux) : 2 saisons des
  pluies (avril–juillet, septembre–octobre) ; nord (centrale, kara, savanes) : une saison
  (mai–octobre). Mois de bascule → `transition`.
- `statements` : 1 phrase `observed` par indicateur clé + 1 à 2 conseils `interpreted`
  issus de règles simples (ex. pluie `below_normal` en saison des pluies → « Surveillez
  l'humidité du sol avant de semer »). Jamais de `predicted`.
- `disclaimer` = `DISCLAIMER`.

### M21 · `POST /voice/transcribe`
- 501 `in_development`. Rien d'autre.

## Bloc 6 — IA et RAG

### M22 · `POST /admin/rag/ingest`
- **Fichiers** : `routers/admin.py`, `ai/rag.py`.
- Lit `data/corpus/` + `sources.json` ; découpe en morceaux de ~600 tokens (chevauchement 80) ;
  vectorise ; écrit dans la collection Chroma `agbea_corpus`.
- Id de chaque morceau = `sha1(file + index)` → upsert : relancer ne crée pas de doublons.
- Métadonnées : `title`, `source_url`, `file`, `region_ids`, `indicators`.
- Réponse : `{"documents": <n>, "chunks": <n>}`.

### M23 · `GET /admin/rag/documents`
- Réponse : `{"documents": [{"file", "title", "source_url", "chunks"}]}`.

### M24 · `POST /explain` → `ExplainResponse`
- **Fichiers** : `routers/ai.py`, `ai/graph.py`, `ai/prompts.py`.
- Appelle M14 pour la région/date, récupère 3–5 morceaux du corpus filtrés par indicateur,
  puis le LLM en **sortie structurée** (`Statement[]`).
- Les phrases `observed` ne reprennent que les chiffres de M14 (source `computed:<region>:<indicator>:<date>`).
- Ton et longueur selon `profile` (voir `ai_tone` dans `/profiles`) et `mode`.
- Tout `source_id` cité existe dans `sources`.

### M25 · `POST /chat/stream` (SSE)
- Graphe LangGraph : `route` (région, indicateur, hors sujet ?) → `fetch_data` (services M14/M15)
  → `retrieve` (Chroma) → `generate`. Checkpointer SQLite par `thread_id`.
- Événements dans l'ordre : `meta` → `status` (≥ 1) → `token` (≥ 1) → `data` (optionnel)
  → `sources` → `done`. En cas d'erreur : `error` puis fin du flux.
- Hors sujet → réponse polie qui ramène au climat et à l'environnement du Togo, sans RAG.
- Header `X-Session-Id` présent → crée ou met à jour le thread (M04).

### M26 · `POST /chat` → `ChatResponse`
- Même graphe, sans streaming. Même `thread_id` en entrée → même `thread_id` en sortie.

---

## Variables d'environnement (`.env.example`)

```
DATA_DIR=data
DB_PATH=agbea.sqlite
CHROMA_DIR=.chroma
CORS_ORIGINS=http://localhost:5173,https://agbea-climat.vercel.app
LLM_PROVIDER=anthropic          # ou openai
LLM_MODEL=
LLM_API_KEY=
EMBEDDING_MODEL=
```
