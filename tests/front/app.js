/* AGBÉA CLIMAT — front de test des données.
 * Lit uniquement les fichiers publiés par le pipeline (/api = data/api) et les contours
 * officiels (/reference/map_togo). Aucune valeur n'est calculée ou inventée ici, sauf
 * l'affichage (moyennes de période, couleurs).
 */
"use strict";

const API = "api";
const REF = "reference/map_togo";

const IND_ORDER = ["rainfall", "ndvi", "lst_day", "lst_night", "air_temp", "rainfall_merra2"];
const SEASON_LABEL = { annual: "Année", jfm: "Janv.-mars (saison sèche)", mjjaso: "Mai-oct. (saison des pluies)" };
const LEVEL_LABEL = { country: "Pays", region: "Région", prefecture: "Préfecture", canton: "Canton", site: "Site pilote" };

// palettes : séquentielle par indicateur, divergente pour anomalies / tendances
const PAL = {
  rainfall: ["#f7fbff", "#c6dbef", "#6baed6", "#2171b5", "#08306b"],
  rainfall_merra2: ["#f7fbff", "#c6dbef", "#6baed6", "#2171b5", "#08306b"],
  ndvi: ["#a6611a", "#dfc27d", "#f5f5d5", "#80cdc1", "#1b7837"],
  lst_day: ["#fff5eb", "#fdbe85", "#fd8d3c", "#d94701", "#7f2704"],
  lst_night: ["#fff5eb", "#fdbe85", "#fd8d3c", "#d94701", "#7f2704"],
  air_temp: ["#fff5eb", "#fdbe85", "#fd8d3c", "#d94701", "#7f2704"],
  elevation: ["#1a9850", "#a6d96a", "#fee08b", "#d7a26b", "#8c510a", "#ffffff"],
};
const DIV = {
  rainfall: ["#8c510a", "#dfc27d", "#f5f5f5", "#80cdc1", "#01665e"],   // sec ← → humide
  ndvi: ["#8c510a", "#dfc27d", "#f5f5f5", "#a6dba0", "#1b7837"],
  temp: ["#2166ac", "#92c5de", "#f7f7f7", "#f4a582", "#b2182b"],      // froid ← → chaud
};
const divFor = (ind) => ind.startsWith("rain") ? DIV.rainfall : ind === "ndvi" ? DIV.ndvi : DIV.temp;

const S = {
  catalog: null, validation: null, summaries: new Map(), charts: [], map: null,
  selected: null, rasterReq: 0, layerFiles: {},
};

// ----------------------------------------------------------------------------- utilitaires
const $ = (sel) => document.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const nf = (v, d = 2) => v == null || Number.isNaN(v) ? "—" : Number(v).toLocaleString("fr-FR", { maximumFractionDigits: d, minimumFractionDigits: 0 });
const sign = (v, d = 2) => v == null ? "—" : (v > 0 ? "+" : "") + nf(v, d);
const decimals = (ind) => ind === "ndvi" ? 3 : ind.startsWith("rain") ? 0 : 1;

async function getJSON(url) {
  const r = await fetch(url, { cache: "no-cache" });
  if (!r.ok) throw new Error(`${url} → HTTP ${r.status}`);
  return r.json();
}
async function summary(id) {
  if (!S.summaries.has(id)) S.summaries.set(id, getJSON(`${API}/summaries/${encodeURIComponent(id)}.json`).catch(() => null));
  return S.summaries.get(id);
}
function indMeta(ind) { return S.catalog?.indicators?.[ind] ?? { label: ind, unit: "" }; }
function unitOf(ind) { const u = indMeta(ind).unit || ""; return u.startsWith("sans unité") ? "" : u; }

function lerpColor(stops, t) {
  t = Math.min(1, Math.max(0, t));
  const n = stops.length - 1, i = Math.min(n - 1, Math.floor(t * n)), f = t * n - i;
  const a = hex(stops[i]), b = hex(stops[i + 1]);
  return [0, 1, 2].map((k) => Math.round(a[k] + (b[k] - a[k]) * f));
}
const hex = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
const rgb = (c) => `rgb(${c[0]},${c[1]},${c[2]})`;

function legendHTML(stops, lo, hi, unit, note = "") {
  return `<div class="bar" style="background:linear-gradient(90deg,${stops.join(",")})"></div>
    <div class="ticks"><span>${nf(lo, 3)}</span><span>${esc(unit)}</span><span>${nf(hi, 3)}</span></div>
    ${note ? `<div class="hint">${note}</div>` : ""}`;
}

// ----------------------------------------------------------------------------- démarrage
async function init() {
  document.querySelectorAll(".tab").forEach((b) => b.addEventListener("click", () => showTab(b.dataset.tab)));
  try {
    [S.catalog, S.validation] = await Promise.all([getJSON(`${API}/catalog.json`), getJSON(`${API}/validation.json`).catch(() => null)]);
  } catch (e) {
    $("#meta").textContent = "Impossible de lire data/api : " + e.message;
    return;
  }
  const v = S.validation?.summary;
  $("#meta").innerHTML = `données générées le ${new Date(S.catalog.generated_at).toLocaleString("fr-FR")} · pipeline ${esc(S.catalog.pipeline_version)} · réf. ${esc(S.catalog.baseline)}`
    + (v ? ` · contrôles <span class="badge b-pass">${v.pass} ok</span> <span class="badge b-warn">${v.warn}</span> <span class="badge b-fail">${v.fail}</span>` : "");

  const inds = IND_ORDER.filter((i) => S.catalog.indicators[i]);
  $("#ch-ind").innerHTML = inds.filter((i) => i !== "air_temp" && i !== "rainfall_merra2")
    .map((i) => `<option value="${i}">${esc(indMeta(i).label)}</option>`).join("");
  await initMap();
  await initRasterControls();
  renderCatalog(); renderChecks(); renderFiles();
  ["#ch-level", "#ch-ind", "#ch-stat"].forEach((s) => $(s).addEventListener("change", updateChoropleth));
  $("#btn-country").addEventListener("click", () => selectUnit("TG"));
  updateChoropleth();
  selectUnit("lome");
}

function showTab(name) {
  document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  document.querySelectorAll(".tab-page").forEach((p) => (p.hidden = p.id !== `tab-${name}`));
  if (name === "explorer") S.map?.resize();
}

// ----------------------------------------------------------------------------- carte
const BASEMAPS = {
  osm: { tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"], attribution: "© contributeurs OpenStreetMap" },
  sat: { tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"], attribution: "Imagerie © Esri" },
};

async function initMap() {
  const map = (S.map = new maplibregl.Map({
    container: "map",
    style: { version: 8, sources: {}, layers: [{ id: "bg", type: "background", paint: { "background-color": "#e8eef3" } }] },
    bounds: [[-0.6, 5.9], [2.3, 11.3]], fitBoundsOptions: { padding: 20 }, attributionControl: { compact: true },
  }));
  map.addControl(new maplibregl.NavigationControl(), "top-right");
  map.addControl(new maplibregl.ScaleControl({ unit: "metric" }));
  await new Promise((res) => map.on("load", res));

  for (const [k, b] of Object.entries(BASEMAPS)) {
    map.addSource(`bm-${k}`, { type: "raster", tiles: b.tiles, tileSize: 256, attribution: b.attribution, maxzoom: 18 });
    map.addLayer({ id: `bm-${k}`, type: "raster", source: `bm-${k}`, layout: { visibility: k === "osm" ? "visible" : "none" } });
  }
  $("#basemap").addEventListener("change", (e) => {
    for (const k of Object.keys(BASEMAPS)) map.setLayoutProperty(`bm-${k}`, "visibility", e.target.value === k ? "visible" : "none");
  });

  const [country, regions, prefs, sites] = await Promise.all([
    getJSON(`${REF}/country.geojson`), getJSON(`${REF}/regions.geojson`),
    getJSON(`${REF}/prefectures.geojson`), getJSON(`${API}/units/site.geojson`),
  ]);
  S.featureIds = {
    regions: regions.features.map((f) => f.properties.unit_id),
    prefectures: prefs.features.map((f) => f.properties.unit_id),
  };
  map.addSource("country", { type: "geojson", data: country, attribution: "Limites : geodata.gouv.tg (via MAP TOGO)" });
  map.addSource("regions", { type: "geojson", data: regions, promoteId: "unit_id" });
  map.addSource("prefectures", { type: "geojson", data: prefs, promoteId: "unit_id" });
  map.addSource("sites", { type: "geojson", data: sites, promoteId: "unit_id" });

  // couche raster vide (remplie à la demande) — placée sous les contours
  map.addSource("raster", { type: "image", url: blankPNG(), coordinates: [[-0.3, 11.3], [2, 11.3], [2, 6], [-0.3, 6]] });
  map.addLayer({ id: "raster", type: "raster", source: "raster", paint: { "raster-opacity": 0.75, "raster-resampling": "nearest" }, layout: { visibility: "none" } });

  for (const lvl of ["regions", "prefectures"]) {
    // état par unité : v = valeur normalisée 0..1 (−1 = pas de donnée), ns = tendance non significative
    map.addLayer({ id: `${lvl}-fill`, type: "fill", source: lvl, paint: {
      "fill-color": "rgba(0,0,0,0)",
      "fill-opacity": ["case",
        ["<", ["coalesce", ["feature-state", "v"], -1], 0], 0,
        ["boolean", ["feature-state", "ns"], false], 0.25,
        ["boolean", ["feature-state", "hover"], false], 0.9, 0.72] } });
  }
  map.addLayer({ id: "prefectures-line", type: "line", source: "prefectures", paint: { "line-color": "#3c4f63", "line-width": 0.7 } });
  map.addLayer({ id: "regions-line", type: "line", source: "regions", paint: { "line-color": "#0b2545", "line-width": 2 } });
  map.addLayer({ id: "country-line", type: "line", source: "country", paint: { "line-color": "#0b2545", "line-width": 3 } });
  map.addLayer({ id: "sites-fill", type: "fill", source: "sites", paint: { "fill-color": "#c2410c", "fill-opacity": 0.25 } });
  map.addLayer({ id: "sites-line", type: "line", source: "sites", paint: { "line-color": "#c2410c", "line-width": 2 } });
  map.addLayer({ id: "selected", type: "line", source: "prefectures", filter: ["==", ["get", "unit_id"], ""], paint: { "line-color": "#ffd60a", "line-width": 4 } });

  const vis = (ids, on) => ids.forEach((id) => map.setLayoutProperty(id, "visibility", on ? "visible" : "none"));
  $("#lyr-country").addEventListener("change", (e) => vis(["country-line"], e.target.checked));
  $("#lyr-regions").addEventListener("change", (e) => vis(["regions-line", "regions-fill"], e.target.checked));
  $("#lyr-prefectures").addEventListener("change", (e) => vis(["prefectures-line", "prefectures-fill"], e.target.checked));
  $("#lyr-sites").addEventListener("change", (e) => vis(["sites-fill", "sites-line"], e.target.checked));

  // survol + clic : site > préfecture > région
  const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false });
  let hovered = null;
  const pickable = () => ["sites-fill", "prefectures-fill", "regions-fill"].filter((l) => map.getLayoutProperty(l, "visibility") !== "none");
  map.on("mousemove", (e) => {
    const f = map.queryRenderedFeatures(e.point, { layers: pickable() })[0];
    if (hovered) map.setFeatureState(hovered, { hover: false });  // hover toujours remis à false, jamais supprimé
    hovered = null;
    if (!f) { popup.remove(); map.getCanvas().style.cursor = ""; return; }
    map.getCanvas().style.cursor = "pointer";
    if (f.source !== "sites") { hovered = { source: f.source, id: f.properties.unit_id }; map.setFeatureState(hovered, { hover: true }); }
    const val = S.choro?.values?.get(f.properties.unit_id);
    const name = f.properties.nom ?? f.properties.name;
    popup.setLngLat(e.lngLat).setHTML(`<b>${esc(name)}</b> <span class="hint">${esc(f.properties.unit_id)}</span>`
      + (val != null && f.source.startsWith(S.choro?.level ?? "x") ? `<br>${esc(S.choro.label)} : <b>${nf(val, S.choro.dec)}</b> ${esc(S.choro.unit)}` : "")).addTo(map);
  });
  map.on("click", (e) => {
    const f = map.queryRenderedFeatures(e.point, { layers: pickable() })[0];
    if (f) selectUnit(f.properties.unit_id);
  });
}

function blankPNG() {
  const c = document.createElement("canvas"); c.width = c.height = 1; return c.toDataURL();
}

// ----------------------------------------------------------------------------- carte thématique
async function updateChoropleth() {
  const map = S.map, level = $("#ch-level").value, ind = $("#ch-ind").value, stat = $("#ch-stat").value;
  // remise à zéro par valeur (et non removeFeatureState : MapLibre 4.7 plante au rendu si l'état n'existait pas)
  for (const src of ["regions", "prefectures"]) {
    S.featureIds[src].forEach((id) => map.setFeatureState({ source: src, id }, { v: -1, ns: false }));
  }
  S.choro = null;
  if (!level) { $("#ch-legend").innerHTML = ""; return; }
  const src = level === "region" ? "regions" : "prefectures";
  const ids = S.featureIds[src];
  const docs = await Promise.all(ids.map(summary));
  const values = new Map(), sig = new Map();
  const isRain = ind.startsWith("rain");
  docs.forEach((d, k) => {
    if (!d) return;
    const ann = (d.annual?.[ind] ?? []).filter((r) => r.value != null);
    let v = null;
    if (stat === "mean") {
      const b = ann.filter((r) => r.year >= 2001 && r.year <= 2020);
      v = b.length ? b.reduce((s, r) => s + r.value, 0) / b.length : null;
    } else if (stat === "last") v = ann.at(-1)?.value ?? null;
    else if (stat === "anom") { const r = ann.at(-1); v = r ? (isRain ? r.anomaly_pct : r.anomaly) : null; }
    else if (stat === "trend") { const t = d.trends?.[ind]?.annual; v = t?.sen_slope_per_decade ?? null; sig.set(ids[k], !!t?.significant); }
    if (v != null) values.set(ids[k], v);
  });
  const vals = [...values.values()];
  if (!vals.length) { $("#ch-legend").innerHTML = `<div class="hint">Pas de valeur pour cette combinaison (ex. NDVI annuel trop nuageux sur la côte).</div>`; return; }
  const diverging = stat === "anom" || stat === "trend";
  let lo = Math.min(...vals), hi = Math.max(...vals);
  if (diverging) { const m = Math.max(Math.abs(lo), Math.abs(hi)) || 1; lo = -m; hi = m; }
  const stops = diverging ? divFor(ind) : PAL[ind];
  const ramp = ["interpolate", ["linear"], ["coalesce", ["feature-state", "v"], 0]];
  stops.forEach((c, i) => ramp.push(i / (stops.length - 1), c));
  map.setPaintProperty(`${src}-fill`, "fill-color", ramp);
  values.forEach((v, id) => {
    map.setFeatureState({ source: src, id }, {
      v: Math.min(1, Math.max(0, (v - lo) / (hi - lo || 1))),
      ns: stat === "trend" && !sig.get(id),   // non significatif : délavé
    });
  });
  const unit = stat === "anom" && isRain ? "%" : stat === "trend" ? `${unitOf(ind)} / décennie` : unitOf(ind);
  const label = { mean: "moyenne 2001-2020", last: "dernière année", anom: "anomalie", trend: "tendance" }[stat];
  S.choro = { level: src, values, label, unit, dec: decimals(ind) + (stat === "trend" ? 2 : 0) };
  const missing = ids.length - values.size;
  $("#ch-legend").innerHTML = legendHTML(stops, lo, hi, unit,
    (stat === "trend" ? "Couleurs délavées = tendance non significative (Mann-Kendall, p ≥ 0,05). " : "")
    + (missing ? `${missing} unité(s) sans valeur (transparentes).` : ""));
}

// ----------------------------------------------------------------------------- rasters
async function initRasterControls() {
  const inds = ["rainfall", "ndvi", "lst_day", "lst_night", "elevation"];
  const opts = [];
  for (const ind of inds) {
    try {
      const list = await getJSON(`${API}/layers/${ind}/`);  // index JSON nginx
      const names = list.filter((x) => x.type === "file").map((x) => x.name);
      S.layerFiles[ind] = names;
      opts.push(`<option value="${ind}">${esc(ind === "elevation" ? "Altitude (NASADEM)" : indMeta(ind).label)}</option>`);
    } catch { /* couche absente */ }
  }
  $("#r-ind").insertAdjacentHTML("beforeend", opts.join(""));
  const onInd = () => {
    const ind = $("#r-ind").value;
    // la carte thématique recouvre les pixels : on la coupe quand on choisit une couche raster
    if (ind && $("#ch-level").value) { $("#ch-level").value = ""; updateChoropleth(); }
    const years = (S.layerFiles[ind] ?? []).map((n) => n.match(/^(\d{4})\.tif$/)?.[1]).filter(Boolean).sort();
    S.rasterYears = years;
    $("#r-year").max = Math.max(0, years.length - 1); $("#r-year").value = Math.max(0, years.length - 1);
    updateRaster();
  };
  $("#r-ind").addEventListener("change", onInd);
  $("#r-kind").addEventListener("change", updateRaster);
  $("#r-year").addEventListener("input", () => { $("#r-year-val").textContent = S.rasterYears?.[+$("#r-year").value] ?? ""; });
  $("#r-year").addEventListener("change", updateRaster);
  $("#r-opacity").addEventListener("input", (e) => S.map.setPaintProperty("raster", "raster-opacity", e.target.value / 100));
}

async function updateRaster() {
  const map = S.map, ind = $("#r-ind").value, kind = $("#r-kind").value;
  const req = ++S.rasterReq;
  if (!ind) { map.setLayoutProperty("raster", "visibility", "none"); $("#r-legend").innerHTML = ""; $("#r-status").textContent = ""; return; }
  let file;
  if (ind === "elevation") file = "elevation.tif";
  else if (kind === "baseline") file = "baseline.tif";
  else if (kind === "anomaly") file = (S.layerFiles[ind] ?? []).find((n) => n.startsWith("anomaly_"));
  else file = `${S.rasterYears[+$("#r-year").value]}.tif`;
  $("#r-year-val").textContent = kind === "year" && ind !== "elevation" ? S.rasterYears[+$("#r-year").value] : "";
  if (!file) { $("#r-status").textContent = "Fichier introuvable."; return; }
  $("#r-status").textContent = `Chargement de ${ind}/${file}…`;
  try {
    const tiff = await GeoTIFF.fromUrl(`${API}/layers/${ind}/${file}`);
    const img = await tiff.getImage();
    const [w, s, e, n] = img.getBoundingBox();
    const scale = Math.min(1, 1400 / img.getHeight()); // l'altitude (~6 000 lignes) est sous-échantillonnée à l'affichage
    const W = Math.round(img.getWidth() * scale), H = Math.round(img.getHeight() * scale);
    const [band] = await img.readRasters({ width: W, height: H, resampleMethod: "nearest" });
    if (req !== S.rasterReq) return;
    const nodata = img.getGDALNoData();
    const ok = (v) => Number.isFinite(v) && v !== nodata;
    const vals = []; for (let i = 0; i < band.length; i += 7) if (ok(band[i])) vals.push(band[i]);
    vals.sort((a, b) => a - b);
    const q = (p) => vals[Math.min(vals.length - 1, Math.floor(p * vals.length))];
    const anomaly = file.startsWith("anomaly_");
    let lo = q(0.02), hi = q(0.98);
    if (anomaly) { const m = Math.max(Math.abs(lo), Math.abs(hi)) || 1; lo = -m; hi = m; }
    const stops = anomaly ? divFor(ind) : PAL[ind];
    // reprojection des lignes : grille EPSG:4326 → Web Mercator (la source image de MapLibre est linéaire en Mercator)
    const merc = (lat) => Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360));
    const yN = merc(n), yS = merc(s);
    const cv = document.createElement("canvas"); cv.width = W; cv.height = H;
    const ctx = cv.getContext("2d"), out = ctx.createImageData(W, H);
    for (let r = 0; r < H; r++) {
      const lat = (360 / Math.PI) * Math.atan(Math.exp(yN + ((yS - yN) * (r + 0.5)) / H)) - 90;
      const sr = Math.min(H - 1, Math.max(0, Math.floor(((n - lat) / (n - s)) * H)));
      for (let c = 0; c < W; c++) {
        const v = band[sr * W + c], o = (r * W + c) * 4;
        if (!ok(v)) { out.data[o + 3] = 0; continue; }
        const col = lerpColor(stops, (v - lo) / (hi - lo || 1));
        out.data[o] = col[0]; out.data[o + 1] = col[1]; out.data[o + 2] = col[2]; out.data[o + 3] = 255;
      }
    }
    ctx.putImageData(out, 0, 0);
    map.getSource("raster").updateImage({ url: cv.toDataURL(), coordinates: [[w, n], [e, n], [e, s], [w, s]] });
    map.setLayoutProperty("raster", "visibility", "visible");
    const unit = ind === "elevation" ? "m" : (anomaly && ind.startsWith("rain") ? "mm" : unitOf(ind));
    const tags = img.getGDALMetadata?.() ?? {};
    $("#r-legend").innerHTML = legendHTML(stops, lo, hi, unit, "Échelle : percentiles 2-98 % des pixels.");
    $("#r-status").textContent = `${ind}/${file} · ${img.getWidth()}×${img.getHeight()} px · ${Object.entries(tags).map(([k, v]) => `${k}=${v}`).join(", ")}`;
  } catch (err) {
    $("#r-status").textContent = "Erreur : " + err.message;
  }
}

// ----------------------------------------------------------------------------- fiche d'une unité
async function selectUnit(id) {
  S.selected = id;
  const d = await summary(id);
  const panel = $("#panel");
  S.charts.forEach((c) => c.destroy()); S.charts = [];
  if (!d) { panel.innerHTML = `<div class="empty">Pas de fiche pour <b>${esc(id)}</b>.</div>`; return; }
  const u = d.unit;
  const src = u.level === "region" ? "regions" : u.level === "prefecture" ? "prefectures" : u.level === "site" ? "sites" : null;
  S.map.setLayoutProperty("selected", "visibility", src ? "visible" : "none");
  if (src) { if (S.map.getLayer("selected").source !== src) { S.map.removeLayer("selected"); S.map.addLayer({ id: "selected", type: "line", source: src, paint: { "line-color": "#ffd60a", "line-width": 4 } }); }
    S.map.setFilter("selected", ["==", ["get", "unit_id"], id]); }

  const parent = u.parent_id ? await summary(u.parent_id) : null;
  const e = d.elevation_m;
  const inds = IND_ORDER.filter((i) => d.annual?.[i] || d.latest?.[i]);
  let html = `<h2>${esc(u.name)}</h2>
    <dl class="kv">
      <dt>Type</dt><dd>${LEVEL_LABEL[u.level] ?? u.level} · <code>${esc(u.id)}</code></dd>
      ${parent ? `<dt>Dans</dt><dd><button class="link" data-goto="${esc(u.parent_id)}">${esc(parent.unit.name)}</button></dd>` : ""}
      <dt>Surface</dt><dd>${nf(u.area_km2, 1)} km²</dd>
      <dt>Centre</dt><dd>${nf(u.centroid[1], 4)} N, ${nf(u.centroid[0], 4)} E</dd>
      ${e ? `<dt>Altitude</dt><dd>moy. ${nf(e.mean, 0)} m · médiane ${nf(e.median, 0)} · p10-p90 ${nf(e.p10, 0)}-${nf(e.p90, 0)} m · ${nf(e.pct_below_10m, 1)} % sous 10 m <span class="hint">(NASADEM)</span></dd>` : ""}
    </dl>`;

  // dernières observations
  html += `<h4>Dernières observations</h4><div class="cards">`;
  const r30 = d.latest?.rainfall_30d;
  if (r30) html += card("Pluie des 30 derniers jours", r30.value, "mm", 0,
    `${r30.start} → ${r30.end} · normale ${nf(r30.normal, 0)} mm · <b class="${r30.anomaly_pct >= 0 ? "pos" : "neg"}">${sign(r30.anomaly_pct, 0)} %</b>`, "imerg_daily_late", "observed");
  for (const ind of IND_ORDER) {
    const l = d.latest?.[ind]; if (!l) continue;
    const dec = decimals(ind);
    const anom = ind.startsWith("rain") ? `${sign(l.anomaly_pct, 0)} %` : sign(l.anomaly, dec);
    html += card(indMeta(ind).label, l.value, unitOf(ind), dec,
      `${l.date} · normale ${nf(l.clim_mean, dec)} · écart <b class="${(l.anomaly ?? 0) >= 0 ? "pos" : "neg"}">${anom}</b> · ${nf((l.valid_frac ?? 1) * 100, 0)} % valide`, l.dataset, l.nature);
  }
  html += `</div>`;
  if (d.latest?.lst_day) html += `<div class="note">La « dernière observation » est le dernier mois où au moins 50 % de la zone est visible (sans nuages). Elle peut donc dater de plusieurs mois en saison des pluies.</div>`;

  // graphiques
  html += `<h4>Séries</h4><div class="row"><label>Indicateur <select id="sel-ind">${inds.map((i) => `<option value="${i}">${esc(indMeta(i).label)}</option>`).join("")}</select></label>
    <label>Saison <select id="sel-season">${Object.entries(SEASON_LABEL).map(([k, v]) => `<option value="${k}">${v}</option>`).join("")}</select></label></div>
    <div class="chart-box"><canvas id="ch-annual"></canvas></div><div id="trend-line" class="note"></div>
    <div class="chart-box"><canvas id="ch-monthly"></canvas></div>`;

  // tableau des tendances
  html += `<h4>Tendances (Mann-Kendall + pente de Sen)</h4><table><thead><tr><th>Indicateur</th><th>Saison</th><th>Période</th><th class="num">Pente / déc.</th><th class="num">IC 95 %</th><th class="num">p</th><th></th></tr></thead><tbody>`;
  for (const ind of IND_ORDER) for (const [sea, t] of Object.entries(d.trends?.[ind] ?? {})) {
    const dec = decimals(ind) + 2;
    html += `<tr><td>${esc(indMeta(ind).label)}</td><td>${SEASON_LABEL[sea] ?? sea}</td><td>${t.first_year}-${t.last_year} (${t.n_years})</td>
      <td class="num">${sign(t.sen_slope_per_decade, dec)}${t.sen_slope_pct_per_decade != null ? ` <span class="hint">(${sign(t.sen_slope_pct_per_decade, 1)} %)</span>` : ""}</td>
      <td class="num">${sign(t.sen_ci95_low_per_decade, dec)} ; ${sign(t.sen_ci95_high_per_decade, dec)}</td>
      <td class="num">${nf(t.p_value, 3)}</td><td><span class="badge ${t.significant ? "b-sig" : "b-ns"}">${t.significant ? t.direction : "ns"}</span></td></tr>`;
  }
  html += `</tbody></table><div class="note">« ns » = pas de tendance significative au seuil de 5 %. Ne parler de tendance que pour les lignes vertes.</div>`;
  if (d.trends?.lst_night) html += `<div class="warnbox">LST de nuit : hausse forte et généralisée, à confirmer avec Aqua avant toute communication (voir notes/2026-11-14_resultats-premiere-analyse.md).</div>`;

  html += `<h4>JSON brut</h4><details><summary>${esc(`${API}/summaries/${id}.json`)}</summary><pre style="white-space:pre-wrap;font-size:11px">${esc(JSON.stringify(d, null, 1))}</pre></details>`;
  panel.innerHTML = html;
  panel.querySelectorAll("[data-goto]").forEach((b) => b.addEventListener("click", () => selectUnit(b.dataset.goto)));
  const redraw = () => drawCharts(d, $("#sel-ind").value, $("#sel-season").value);
  $("#sel-ind").addEventListener("change", redraw); $("#sel-season").addEventListener("change", redraw);
  redraw();
}

function card(label, value, unit, dec, sub, dataset, nature) {
  const ds = S.catalog?.datasets?.[dataset];
  return `<div class="card"><div class="lbl">${esc(label)} <span class="badge ${nature === "observed" ? "b-obs" : "b-der"}" title="${nature === "observed" ? "mesuré par satellite" : "réanalyse / calcul"}">${nature === "observed" ? "observé" : "dérivé"}</span></div>
    <div class="val">${nf(value, dec)} <small>${esc(unit)}</small></div><div class="sub">${sub}</div>
    <div class="sub">${esc(ds?.short_name ?? dataset)} ${ds?.version ? "v" + esc(ds.version) : ""} · ${esc(ds?.native_resolution ?? "")}</div></div>`;
}

async function drawCharts(d, ind, season) {
  S.charts.forEach((c) => c.destroy()); S.charts = [];
  const dec = decimals(ind), unit = unitOf(ind), rain = ind.startsWith("rain");
  // série saisonnière : la fiche contient l'annuel ; les autres saisons viennent de tables/seasonal.csv
  let rows = season === "annual" ? (d.annual?.[ind] ?? []) : await seasonalRows(d.unit.id, ind, season);
  rows = rows.filter((r) => r.year != null);
  const years = rows.map((r) => r.year);
  const vals = rows.map((r) => r.value);
  const base = rows.map((r) => (r.value != null && r.anomaly != null ? r.value - r.anomaly : null)).find((v) => v != null);
  const t = d.trends?.[ind]?.[season];
  const sets = [{ type: rain ? "bar" : "line", label: `${indMeta(ind).label} (${SEASON_LABEL[season]})`, data: vals,
    backgroundColor: rain ? "#6baed6" : "#13598f", borderColor: "#13598f", pointRadius: 2, spanGaps: false }];
  if (base != null) sets.push({ type: "line", label: "Moyenne de référence 2001-2020", data: years.map(() => base), borderColor: "#888", borderDash: [4, 4], pointRadius: 0 });
  if (t) {
    // droite de Sen passant par le point médian (convention usuelle)
    const ok = rows.filter((r) => r.value != null && r.year >= t.first_year && r.year <= t.last_year);
    const med = (a) => { const s = [...a].sort((x, y) => x - y); const m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
    const xm = med(ok.map((r) => r.year)), ym = med(ok.map((r) => r.value)), b = t.sen_slope_per_decade / 10;
    sets.push({ type: "line", label: `Pente de Sen ${t.significant ? "(significative)" : "(non significative)"}`,
      data: years.map((y) => (y >= t.first_year && y <= t.last_year ? ym + b * (y - xm) : null)),
      borderColor: t.significant ? "#2e7d32" : "#b0b8c2", borderWidth: 2, pointRadius: 0 });
    $("#trend-line").innerHTML = `Tendance ${t.first_year}-${t.last_year} : <b>${sign(t.sen_slope_per_decade, dec + 2)} ${esc(unit)}/décennie</b>, p = ${nf(t.p_value, 3)} → ${t.significant ? `<b>${t.direction}</b> significative` : "pas de tendance significative"}.`;
  } else $("#trend-line").textContent = "Pas assez d'années valides pour tester une tendance (au moins 10).";
  S.charts.push(new Chart($("#ch-annual"), { type: rain ? "bar" : "line", data: { labels: years, datasets: sets },
    options: { maintainAspectRatio: false, animation: false, plugins: { legend: { labels: { boxWidth: 10, font: { size: 10 } } },
      title: { display: true, text: `${indMeta(ind).label} — ${SEASON_LABEL[season]} (${unit || "indice"})` } },
      scales: { y: { beginAtZero: rain } } } }));

  const m = d.recent_monthly?.[ind] ?? [];
  S.charts.push(new Chart($("#ch-monthly"), { type: "line", data: { labels: m.map((r) => r.date), datasets: [
    { label: "Valeur mensuelle", data: m.map((r) => r.value), borderColor: "#13598f", backgroundColor: "#13598f", pointRadius: 2, spanGaps: false },
    { label: "Normale du mois (2001-2020)", data: m.map((r) => r.clim_mean), borderColor: "#888", borderDash: [4, 4], pointRadius: 0 },
  ] }, options: { maintainAspectRatio: false, animation: false, plugins: { legend: { labels: { boxWidth: 10, font: { size: 10 } } },
    title: { display: true, text: "24 derniers mois disponibles vs normale (trous = moins de 50 % de la zone visible)" } } } }));
}

// tables/seasonal.csv chargé une seule fois (≈ 10 Mo) pour les saisons autres que l'année
let SEASONAL = null;
async function seasonalRows(id, ind, season) {
  if (!SEASONAL) {
    const txt = await (await fetch(`${API}/tables/seasonal.csv`)).text();
    const [head, ...lines] = txt.trim().split("\n");
    const cols = head.split(",");
    const ix = Object.fromEntries(cols.map((c, i) => [c, i]));
    SEASONAL = new Map();
    for (const line of lines) {
      const p = line.split(",");
      const key = `${p[ix.unit_id]}|${p[ix.indicator]}|${p[ix.season]}`;
      const num = (c) => (p[ix[c]] === "" ? null : +p[ix[c]]);
      if (!SEASONAL.has(key)) SEASONAL.set(key, []);
      SEASONAL.get(key).push({ year: num("year"), value: num("value"), anomaly: num("anomaly"), anomaly_pct: num("anomaly_pct") });
    }
  }
  return SEASONAL.get(`${id}|${ind}|${season}`) ?? [];
}

// ----------------------------------------------------------------------------- onglets documentaires
function renderCatalog() {
  const c = S.catalog;
  let h = `<h2>Catalogue de provenance</h2>
    <p>Référence climatologique <b>${esc(c.baseline)}</b> · test de tendance : ${esc(c.trend_test.method)} (α = ${c.trend_test.alpha}) ·
      règles de complétude : ${Object.entries(c.completeness).map(([k, v]) => `${k} = ${v}`).join(", ")}</p>
    <h4>Nature des valeurs</h4><dl class="kv">${Object.entries(c.nature_legend).map(([k, v]) => `<dt>${k}</dt><dd>${esc(v)}</dd>`).join("")}</dl>
    <h4>Indicateurs</h4><table><thead><tr><th>id</th><th>Libellé</th><th>Unité</th><th>Jeu de données</th><th>Nature</th><th>Agrégation (mois / an)</th><th>Couverture réelle</th></tr></thead><tbody>`;
  for (const [k, v] of Object.entries(c.indicators)) {
    const cov = c.coverage?.[k];
    h += `<tr><td><code>${k}</code></td><td>${esc(v.label)}</td><td>${esc(v.unit)}</td><td>${esc(v.dataset)}</td><td>${esc(v.nature)}</td>
      <td>${esc(v.monthly_agg ?? "—")} / ${esc(v.annual_agg ?? "—")}</td><td>${cov ? `${cov.first_month} → ${cov.last_month} (${cov.n_months} mois)` : "—"}</td></tr>`;
  }
  h += `</tbody></table><h4>Jeux de données</h4><div class="grid">`;
  for (const [k, d] of Object.entries(c.datasets)) {
    h += `<div class="card"><div class="lbl"><code>${k}</code></div><b>${esc(d.title)}</b>
      <dl class="kv" style="margin-top:6px">
        <dt>Produit</dt><dd>${esc(d.short_name)} v${esc(d.version)}</dd><dt>Fournisseur</dt><dd>${esc(d.provider)}</dd>
        <dt>DOI</dt><dd>${d.doi ? `<a href="https://doi.org/${esc(d.doi)}" target="_blank" rel="noopener">${esc(d.doi)}</a>` : "—"}</dd>
        <dt>Page</dt><dd><a href="${esc(d.url)}" target="_blank" rel="noopener">${esc(d.url)}</a></dd>
        <dt>Accès</dt><dd>${esc(d.access)}</dd><dt>Variable</dt><dd>${esc(d.variable)}</dd>
        <dt>Résolution</dt><dd>${esc(d.native_resolution)} · ${esc(d.temporal_resolution)}</dd>
        <dt>Couverture</dt><dd>${esc(d.coverage)}</dd><dt>Licence</dt><dd>${esc(d.license)}</dd>
      </dl><b style="font-size:12px">Limites</b><ul>${(d.limits ?? []).map((l) => `<li>${esc(l)}</li>`).join("")}</ul></div>`;
  }
  $("#tab-catalog").innerHTML = h + `</div>`;
}

function renderChecks() {
  const v = S.validation;
  if (!v) { $("#tab-checks").innerHTML = "<p>validation.json absent.</p>"; return; }
  $("#tab-checks").innerHTML = `<h2>Contrôles automatiques</h2><p>Générés le ${new Date(v.generated_at).toLocaleString("fr-FR")}.</p>
    <table><thead><tr><th>Statut</th><th>Contrôle</th><th>Détail</th></tr></thead><tbody>
    ${v.checks.map((c) => `<tr><td><span class="badge b-${c.status}">${c.status}</span></td><td>${esc(c.check)}</td><td>${esc(c.detail)}</td></tr>`).join("")}
    </tbody></table>`;
}

async function renderFiles() {
  let h = `<h2>Fichiers publiés (data/api)</h2><p>Tout ce que le backend consomme. Format décrit dans <code>docs/contrat-donnees.md</code>.</p>`;
  for (const dir of ["", "tables/", "units/", "summaries/", "layers/"]) {
    try {
      const list = await getJSON(`${API}/${dir}`);
      h += `<h4>/${dir || ""}</h4><table><thead><tr><th>Nom</th><th class="num">Taille</th><th>Modifié</th></tr></thead><tbody>`
        + list.slice(0, 80).map((f) => `<tr><td>${f.type === "directory" ? "📁 " : ""}<a href="${API}/${dir}${encodeURIComponent(f.name)}${f.type === "directory" ? "/" : ""}" target="_blank">${esc(f.name)}</a></td>
          <td class="num">${f.size != null ? nf(f.size / 1024, 0) + " Ko" : ""}</td><td>${esc(f.mtime ?? "")}</td></tr>`).join("")
        + `</tbody></table>${list.length > 80 ? `<p class="hint">… ${list.length - 80} autres</p>` : ""}`;
    } catch { /* répertoire absent */ }
  }
  h += `<h4>Contours</h4><p><a href="${REF}/" target="_blank">${REF}/</a> — Contenu provenant de la Plateforme Géodata (geodata.gouv.tg) en date du 2026-10-23, via le projet MAP TOGO.</p>`;
  $("#tab-files").innerHTML = h;
}

init();
