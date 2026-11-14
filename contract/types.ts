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
  area_km2?: number;
}

/** GET /regions?format=geojson → FeatureCollection dont properties = Region */
export interface RegionFeatureCollection {
  type: "FeatureCollection";
  features: Array<{
    type: "Feature";
    geometry: GeoJSON.Geometry; // npm i -D @types/geojson
    properties: Region;
  }>;
}

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
  citation?: string;
}

// ───────────────────────── Carte ─────────────────────────

export interface LegendStop { value: number; color: string; label?: string }

export interface MapLayer {
  id: string;                 // "ndvi", "precipitation", "lst_day"
  indicator: IndicatorId;
  dataset_id: string;
  title: string;
  type: "wmts" | "xyz" | "geojson";
  url_template: string;       // ex. tuile GIBS avec {date}{z}{y}{x}
  available_dates: string[];  // ou plage
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
  valid_frac?: number | null;  // part de la région visible par le satellite (0–1), mois seulement
  low_coverage?: boolean;      // true si valid_frac < 0,5 : valeur peu représentative, à signaler
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
  label: string;      // "2001–2010"
  start: string;
  end: string;
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
  id: string;
  kind: "dataset" | "document" | "computed"; // computed = chiffre issu de nos séries
  title: string;
  url?: string;
  dataset_id?: string;
  snippet?: string;
  page?: number;
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
  date?: string;
  mode: Mode;
  lang: Lang;
}

export interface ExplainResponse {
  title: string;
  statements: Statement[]; // le front colore par nature
  sources: Source[];
  disclaimer: string;      // "Ne remplace pas les prévisions officielles…"
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
  lang: Lang;
  region_id?: string;      // région sélectionnée sur la carte
  location?: [number, number]; // [lon, lat] si clic carte
}

/** POST /chat/stream → text/event-stream ; chaque `data:` est un ChatEvent */
export type ChatEvent =
  | { type: "meta"; thread_id: string }
  | { type: "status"; step: "routing" | "fetching_data" | "retrieving" | "generating" }
  | { type: "token"; content: string }
  | { type: "data"; series?: TimeSeries; snapshot?: IndicatorSnapshot } // graphe inline
  | { type: "sources"; sources: Source[] }
  | { type: "done"; statements?: Statement[] }
  | { type: "error"; message: string };

/** POST /chat (non-stream, fallback) */
export interface ChatResponse {
  thread_id: string;
  answer: string;
  statements: Statement[];
  sources: Source[];
  data?: { series?: TimeSeries[]; snapshots?: IndicatorSnapshot[] };
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
  layer_id?: string;             // couche carte associée
  status: FeatureStatus;
}

/** GET /dashboard — vue nationale (Home + dashboard) */
export interface Dashboard {
  date: string;
  regions: RegionSummary[];
  highlights: Statement[];       // 2-3 faits marquants du mois
}

/** GET /layers/{id}/before-after — écran Avant / Après */
export interface BeforeAfter {
  layer_id: string;
  before: { date: string; url_template: string };
  after: { date: string; url_template: string };
  comparison?: Comparison;       // si region_id fourni
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
  data_last_updated: string;
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

/** Erreur (4xx / 5xx) : `message` lisible, `response.code` en snake_case (region_not_found, ...) */
export interface ApiError {
  status: "error";
  message: string;
  response: { code: string; details: unknown | null };
}

export type ApiResult<T> = ApiResponse<T> | ApiError;
