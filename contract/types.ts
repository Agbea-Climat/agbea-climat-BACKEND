/**
 * AGBÉA CLIMAT — Contrat API partagé (front ⇄ back)
 * Miroir exact de backend/schemas/. Toute modif se fait des DEUX côtés.
 * Base URL : /api/v1
 * Chaque réponse JSON est enveloppée : ApiResponse<T> (succès) ou ApiError (voir fin du fichier).
 */

// ───────────────────────── Enums ─────────────────────────

export type Mode = "public" | "scientific";
export type Lang = "fr" | "en" | "ee"; // ee = éwé (prévu, pas pour la démo)

export type IndicatorId =
  | "precipitation" // GPM IMERG — mm
  | "ndvi"          // MODIS MOD13A1 — sans unité (-1..1)
  | "lst_day"       // MODIS MOD11A2 — °C
  | "elevation"     // NASADEM (SRTM retraité) — m (statique)
  | "land_cover";   // optionnel J2 (MODIS/Landsat)

export type Granularity = "month" | "year";

/** Slide 10 : on sépare toujours ce qui est observé / interprété / prédit */
export type StatementNature = "observed" | "interpreted" | "predicted";

export type ProfileId = "farmer" | "community" | "researcher" | "decision_maker";

export type FeatureStatus = "prototype" | "in_development" | "planned";

// ───────────────────────── Géographie ─────────────────────────

export interface Region {
  id: string;            // "maritime" | "plateaux" | "centrale" | "kara" | "savanes"
  name: string;          // "Maritime"
  capital: string;       // "Lomé"
  centroid: [number, number]; // [lon, lat]
  bbox: [number, number, number, number]; // [minLon, minLat, maxLon, maxLat]
  area_km2?: number | null;
}

/** GET /regions/geojson → FeatureCollection dont properties = Region (limites officielles) */
export interface RegionFeatureCollection {
  type: "FeatureCollection";
  source?: string | null;      // attribution obligatoire des limites (geodata.gouv.tg, via MAP TOGO), à afficher avec la carte
  features: Array<{
    type: "Feature";
    geometry: GeoJSON.Polygon | GeoJSON.MultiPolygon; // npm i -D @types/geojson — positions en [lon, lat]
    properties: Region;
  }>;
}

/** GET /locate?lon=&lat= → Region. lon ∈ [-180, 180], lat ∈ [-90, 90], nombres finis (sinon 422 validation_error).
 *  Hors des contours nationaux → 404 outside_togo : aucune tolérance sur les frontières terrestres (Ghana, Burkina Faso, Bénin).
 *  Seule tolérance : un point en mer à ≤ 100 m du littoral → "maritime" (trait de côte officiel approximatif).
 *  Si (lat, lon) inversés tombent dans le Togo, la 404 le suggère :
 *  response.details = { hint: string; suggested: { lon: number; lat: number }; region_id: string }. */

// ───────────────────────── Provenance (slide 10) ─────────────────────────

export interface Dataset {
  id: string;                 // "gpm_imerg"
  name: string;               // "NASA GPM IMERG (Final)"
  provider: string;           // "NASA GES DISC"
  variable: string;           // "Precipitation"
  indicator: IndicatorId;
  units: string;              // "mm"
  spatial_resolution: string; // "0.1° (~10 km)"
  temporal_resolution: string;// "monthly"
  coverage: string;           // "60°N–60°S"
  period_start: string;       // ISO date "1998-01-01"
  period_end: string | null;  // null = présent
  limitations: string[];      // ["Estimation satellite, pas un pluviomètre"]
  source_url: string;
  citation?: string | null;
}

// ───────────────────────── Carte ─────────────────────────

export interface LegendStop { value: number; color: string; label?: string | null }

export interface MapLayer {
  id: string;                 // "ndvi", "precipitation", "lst_day"
  indicator: IndicatorId;
  dataset_id: string;         // dataset des séries de l'indicateur (pas toujours le produit des tuiles)
  title: string;
  description?: string | null; // provenance exacte des tuiles (produit, résolution, unité)
  type: "wmts" | "xyz" | "geojson";
  url_template: string;       // ex. tuile GIBS avec {date}{z}{y}{x}
  available_dates: string[];  // YYYY-MM-DD, dates publiées par GIBS (relevé figé côté backend)
  default_date: string;
  opacity: number;            // 0..1
  legend: LegendStop[];
  modes: Mode[];              // couches visibles dans quel mode
  max_zoom?: number | null;   // zoom maximal servi (au-delà, GIBS répond 400)
}

// ───────────────────────── Indicateurs ─────────────────────────

export interface TimePoint {
  date: string;        // "2024-07" (month) ou "2024" (year)
  value: number | null;
  baseline?: number | null; // moyenne climatologique même mois (2001–2020)
  anomaly_pct?: number | null;
  valid_frac?: number | null;  // part de la région visible par le satellite (0–1) ; en "year" : mois agrégé le moins couvert
  low_coverage?: boolean;      // true si valid_frac < 0,5 : valeur peu représentative, à signaler ; en "year" : un des mois l'est
  months_count?: number | null; // "year" : nb de mois avec valeur (12 = année entière, moins = année partielle) ; null en "month"
}

export interface TimeSeries {
  region_id: string;
  indicator: IndicatorId;
  units: string;
  granularity: Granularity;
  baseline_period: [string, string]; // ["2001", "2020"]
  points: TimePoint[];
  dataset_id: string;
  nature: "observed";
}

/** Lue sur l'écart AFFICHÉ : anomalie % à 0,1 (> +10 / < −10) ; température : valeur − normale affichée,
 *  à 0,1 °C (> +1,5 / < −1,5). Ex. anomaly_pct 10.0 → "normal", 10.1 → "above_normal". */
export type Trend = "above_normal" | "normal" | "below_normal" | "unknown";

export interface IndicatorSnapshot {
  indicator: IndicatorId;
  label: string;          // "Pluie du mois"
  value: number | null;
  units: string;
  date: string;
  baseline: number | null;
  anomaly_pct: number | null;
  trend: Trend;
  plain_summary: string;  // phrase simple pour le mode public (template, pas LLM)
  dataset_id: string;
  valid_frac: number | null;  // part de la région visible par le satellite (0–1)
  low_coverage: boolean;      // true si valid_frac < 0,5 : valeur peu représentative, à signaler
}

export interface RegionSummary {
  region: Region;
  date: string;
  indicators: IndicatorSnapshot[];
}

export interface PeriodStats {
  label: string;      // années entières utilisées : "2001–2010", "2016–2024" (2025 incomplète), "2001–2010 (sans 2005)" ;
                      // before-after sur mois communs : "2026 (janvier–octobre)"
  start: string;      // première année utilisée (peut différer de l'année demandée si incomplète)
  end: string;        // dernière année utilisée
  mean: number | null;
  min: number | null;
  max: number | null;
}

export interface Comparison {
  region_id: string;
  indicator: IndicatorId;
  units: string;
  period_a: PeriodStats;
  period_b: PeriodStats;
  delta_abs: number | null;
  delta_pct: number | null;
  dataset_id: string;
}

// ───────────────────────── IA / RAG ─────────────────────────

export interface Source {
  // dataset  : "ds:<dataset_id>" ; document : "doc:<12 hex>" (une source par document)
  // computed : "computed:<region>:<indicator>:<date>", <date> = YYYY-MM (mois), YYYY (année),
  //            YYYY/YYYY (moyenne d'une période) ou "static" (altitude)
  id: string;
  kind: "dataset" | "document" | "computed"; // computed = chiffre issu de nos séries
  title: string;
  url?: string | null;
  dataset_id?: string | null;
  snippet?: string | null;
  page?: number | null;
}

export interface Statement {
  text: string;
  nature: StatementNature;
  source_ids: string[];
}

export interface ExplainRequest {
  profile?: ProfileId;
  region_id: string;
  indicator: IndicatorId;
  date?: string;           // YYYY-MM dans la période des données, sinon 400 invalid_period
  mode: Mode;
  lang: Lang;              // "ee" : repli sur le français
}
// Erreurs : indicator "land_cover" → 501 in_development ; date mal formée / hors données → 400 invalid_period

export interface ExplainResponse {
  title: string;
  statements: Statement[]; // le front colore par nature
  sources: Source[];
  disclaimer: string;      // texte exact de DISCLAIMER (français, quelle que soit la langue)
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ChatRequest {
  thread_id?: string;      // absent = nouvelle conversation
  profile?: ProfileId;     // adapte le ton et le contenu de la réponse
  message: string;
  mode: Mode;
  lang: Lang;              // "ee" : repli sur le français
  region_id?: string;      // région sélectionnée sur la carte (inconnue → 404 region_not_found)
  location?: [number, number]; // [lon, lat] si clic carte (hors Togo → 404 outside_togo)
}

/** POST /chat/stream → text/event-stream ; chaque `data:` est un ChatEvent */
export type ChatEvent =
  | { type: "meta"; thread_id: string }
  | { type: "status"; step: "routing" | "fetching_data" | "retrieving" | "generating" }
  | { type: "token"; content: string }
  // graphe inline : un événement par série ; les valeurs du mois dans `snapshots`
  // (`snapshot` rempli aussi quand il n'y en a qu'une)
  | { type: "data"; series?: TimeSeries | null; snapshot?: IndicatorSnapshot | null; snapshots?: IndicatorSnapshot[] | null }
  | { type: "sources"; sources: Source[] }
  | { type: "done"; statements?: Statement[] | null; disclaimer: string } // disclaimer = texte exact
  | { type: "error"; message: string };

/** POST /chat (non-stream, fallback) */
export interface ChatResponse {
  thread_id: string;
  answer: string;          // se termine toujours par l'avertissement (traduit si lang = "en")
  statements: Statement[];
  sources: Source[];
  data?: { series?: TimeSeries[]; snapshots?: IndicatorSnapshot[] } | null;
  disclaimer: string;      // texte exact de DISCLAIMER
}

// ───────────────────────── Ajouts v0.2 ─────────────────────────

/** GET /indicators — catalogue des indicateurs disponibles */
export interface Indicator {
  id: IndicatorId;
  label: string;                 // "Verdure de la végétation"
  units: string;
  dataset_id: string;
  description_public: string;    // 1 phrase simple
  description_scientific: string;
  has_timeseries: boolean;       // false pour elevation
  layer_id?: string | null;      // couche carte associée (null : aucune, ex. elevation)
  status: FeatureStatus;
}

/** GET /dashboard — vue nationale (Home + dashboard) */
export interface Dashboard {
  date: string;
  regions: RegionSummary[];
  highlights: Statement[];       // 1-3 plus grands écarts du mois (valeurs du mois, hors faible couverture), ou 1 phrase « aucun écart marqué »
}

/** GET /layers/{id}/before-after — écran Avant / Après */
export interface BeforeAfter {
  layer_id: string;
  before: { date: string; url_template: string };
  after: { date: string; url_template: string };
  comparison?: Comparison | null;  // si region_id fourni et années comparables (entières, ou ≥ 6 mois communs)
  comparison_note?: string | null; // pourquoi comparison est null, ou « comparaison sur les mêmes mois (…) »
}

/** GET /regions/{id}/agriculture — mode Public / Agriculture */
export interface AgriInsight {
  region_id: string;
  date: string;
  season: "dry" | "rainy" | "transition";
  rainfall_status: Trend;
  vegetation_status: Trend;
  statements: Statement[];       // nature "interpreted", jamais "predicted" sans source
  disclaimer: string;
}

// Export : GET /regions/{id}/timeseries/export?indicator&format=csv|json
// → fichier téléchargeable (Content-Disposition), avec en-tête source/unités

// ───────────────────────── Types d'utilisateurs (slide 11) ─────────────────────────

/** GET /profiles — section « Pour qui ? » + choix du profil */
export interface Profile {
  id: ProfileId;
  title: string;               // "Agriculteurs"
  audience: string;            // "Agriculteurs, coopératives"
  benefit: string;             // phrase de la slide 11
  icon: string;                // nom d'icône côté front
  default_mode: Mode;
  landing_screen: "agriculture" | "dashboard" | "map" | "scientific";
  featured_indicators: IndicatorId[];
  ai_tone: string;             // info pour l'équipe, pas forcément affichée
}

// ───────────────────────── Sessions anonymes ─────────────────────────
// POST /sessions → Session ; stocker session_id en localStorage
// Envoyer ensuite le header X-Session-Id sur /chat et /chat/stream

export interface Preferences {
  profile?: ProfileId | null;
  region_id?: string | null;
  lang?: Lang | null;
  mode?: Mode | null;
}

export interface ThreadSummary {
  thread_id: string;
  title: string;
  updated_at: string; // ISO
}

/** GET /sessions/{id} — threads triés du plus récent au plus ancien */
export interface Session {
  session_id: string;
  preferences: Preferences;
  threads: ThreadSummary[];
  created_at: string;
  last_seen_at: string;
}
// PATCH /sessions/{id}/preferences  body: Preferences → Preferences

// ───────────────────────── Divers ─────────────────────────

export interface Feature {
  id: string;
  title: string;
  status: FeatureStatus;
}

export interface AppMeta {
  version: string;
  regions_count: number;
  data_last_updated: string;     // YYYY-MM-DD, dernier mois toutes séries confondues
  data_last_updated_by_indicator?: Partial<Record<IndicatorId, string>> | null; // "YYYY-MM" par série (ex. pluie 2025-09, lst_day 2022-12)
  features: Feature[]; // affichage honnête des statuts (slide 9)
}

// ───────────────────────── Enveloppe ─────────────────────────
// Toutes les réponses JSON sont enveloppées (backend/schemas/envelope.py).
// Sauf : flux SSE POST /chat/stream et fichiers GET /regions/{id}/timeseries/export.

/** Succès (2xx) : les données sont dans `response`. Ex. GET /regions → ApiResponse<Region[]> */
export interface ApiResponse<T> {
  status: "success";
  message: string; // "OK" ou message d'action ("Session créée", ...)
  response: T;
}

/** Erreur (4xx / 5xx) : `message` lisible (français), `response.code` en snake_case (region_not_found, ...).
 *  422 validation_error : details = ValidationIssue[] ; 404 not_found / 405 method_not_allowed (route inconnue,
 *  méthode refusée) : details = { path, method } ; 503 data_unavailable (routes qui lisent data/ seulement) :
 *  fichiers de données absents. `message` coupé à 300 caractères (identifiant reçu très long). */
export interface ValidationIssue {
  type: string;                    // type Pydantic : "missing", "less_than_equal", "finite_number"...
  loc: (string | number)[];        // ["query", "lon"]
  msg: string;                     // en français ("doit être inférieur ou égal à 180"…)
  input?: string | number | boolean | null; // valeur reçue, tronquée à 100 caractères ; absente pour un objet ou une liste
}

/** Erreur 422 : ApiError dont details est typé */
export interface ApiValidationError {
  status: "error";
  message: string;
  response: { code: "validation_error"; details: ValidationIssue[] };
}

export interface ApiError {
  status: "error";
  message: string;
  response: { code: string; details: unknown | null };
}

export type ApiResult<T> = ApiResponse<T> | ApiError;
