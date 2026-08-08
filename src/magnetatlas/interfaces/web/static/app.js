"use strict";

const STORAGE_KEYS = {
  favorites: "magnetatlas.favorites",
  recents: "magnetatlas.recents",
  theme: "magnetatlas.theme",
};

const state = {
  map: null,
  collection: { type: "FeatureCollection", features: [] },
  featureIndex: new Map(),
  selectedId: null,
  popup: null,
  searchTimer: null,
  searchController: null,
  viewportTimer: null,
  viewportController: null,
  searchActive: false,
  locationWatchId: null,
  locationMarker: null,
  lastPosition: null,
  followLocation: false,
  centerOnNextLocation: false,
  layers: [],
  datasetSummary: null,
};

const elements = {};

function byId(id) {
  return document.getElementById(id);
}

function storedIds(key) {
  try {
    const value = JSON.parse(localStorage.getItem(key) || "[]");
    return Array.isArray(value) ? value.filter((item) => typeof item === "string") : [];
  } catch {
    return [];
  }
}

function saveIds(key, ids) {
  localStorage.setItem(key, JSON.stringify([...new Set(ids)]));
}

function findFeature(featureId) {
  return state.featureIndex.get(String(featureId));
}

const LAYER_COLORS = [
  "#8f3b2f", "#31688e", "#4f772d", "#8b5a2b", "#6d4c91", "#007f86",
  "#b05a00", "#465d73", "#a23e78", "#5e6b32", "#2f6f4e", "#704214",
];

function stableColor(value) {
  const hash = [...String(value)].reduce(
    (result, character) => ((result * 31) + character.codePointAt(0)) >>> 0,
    0,
  );
  return LAYER_COLORS[hash % LAYER_COLORS.length];
}

function layerColor(layer) {
  return layer.legend?.[0]?.color || stableColor(layer.id);
}

function normalizedWords(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("sv-SE")
    .split(/[^a-z0-9]+/)
    .filter((word) => word.length > 3)
    .map((word) => word.replace(/s$/, ""));
}

function layerForFeature(properties) {
  const sourceWords = new Set(normalizedWords(properties.source?.name));
  const candidates = state.layers.filter((layer) => layer.enabled && layer.supported);
  const match = candidates
    .map((layer) => {
      const words = normalizedWords(`${layer.provider} ${layer.dataset} ${layer.name}`);
      const score = words.filter((word) => sourceWords.has(word)).length;
      return { layer, score };
    })
    .sort((left, right) => right.score - left.score)[0];
  return match?.score > 0 ? match.layer : null;
}

function renderLegend() {
  elements.legendList.replaceChildren();
  const active = state.layers.filter((layer) => layer.active && layer.supported);
  active.forEach((layer) => {
    const entries = layer.legend?.length
      ? layer.legend
      : [{ label: layer.name, color: layerColor(layer) }];
    entries.forEach((entry) => {
      const item = document.createElement("div");
      item.className = "legend-item";
      const swatch = document.createElement("span");
      swatch.className = `legend-swatch legend-swatch-${layer.geometry_type}`;
      swatch.style.setProperty("--legend-color", entry.color);
      const text = document.createElement("span");
      text.textContent = `${entry.label} · ${layer.provider}`;
      item.append(swatch, text);
      elements.legendList.append(item);
    });
  });
  if (!active.length) {
    const empty = document.createElement("p");
    empty.textContent = "Aktivera ett lager för att visa dess legend.";
    elements.legendList.append(empty);
  }
}

function updateLayerStatistics() {
  const active = state.layers.filter((layer) => layer.active && layer.supported);
  elements.activeLayerCount.textContent = `${active.length} aktiva`;
  elements.activeLayerStat.textContent = active.length.toLocaleString("sv-SE");
  elements.activeProviderCount.textContent = new Set(active.map((layer) => layer.provider))
    .size.toLocaleString("sv-SE");
}

function updateZoomInformation() {
  if (!state.map) return;
  const zoom = state.map.getZoom();
  const active = state.layers.filter((layer) => layer.active && layer.supported);
  const available = active.filter((layer) => zoom >= layer.min_zoom && zoom <= layer.max_zoom);
  elements.layerZoomInfo.textContent = active.length
    ? `Zoom ${zoom.toFixed(1)} · ${available.length} av ${active.length} aktiva lager visas här`
    : `Zoom ${zoom.toFixed(1)} · inga aktiva lager`;
}

function renderLayers(layers) {
  state.layers = layers;
  elements.layerList.replaceChildren();
  const categories = new Map();
  layers.forEach((layer) => {
    const category = layer.category || "Övrigt";
    categories.set(category, [...(categories.get(category) || []), layer]);
  });
  categories.forEach((categoryLayers, category) => {
    const group = document.createElement("section");
    group.className = "layer-category";
    const heading = document.createElement("h3");
    heading.textContent = category;
    group.append(heading);
    categoryLayers.forEach((layer) => {
      const card = document.createElement("article");
      card.className = `layer-item${layer.enabled && layer.supported ? " is-available" : " is-future"}${layer.active ? " is-active" : ""}`;
      card.style.setProperty("--layer-color", layerColor(layer));
      const label = document.createElement("label");
      label.className = "layer-toggle";
      const icon = document.createElement("span");
      icon.className = "layer-icon";
      icon.textContent = layer.icon || "◇";
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = layer.active;
      checkbox.disabled = !layer.enabled || !layer.supported;
      checkbox.setAttribute("aria-label", layer.name);
      const content = document.createElement("span");
      const name = document.createElement("strong");
      name.textContent = layer.name;
      const status = document.createElement("small");
      status.textContent = layer.enabled && layer.supported
        ? `${layer.active ? "Aktivt" : "Inaktivt"} · ${layer.description}`
        : `Kommer senare · ${layer.layer_type}`;
      content.append(name, status);
      label.append(icon, content, checkbox);
      card.append(label);
      const metadata = document.createElement("div");
      metadata.className = "layer-metadata";
      metadata.textContent = `${layer.provider} · ${layer.dataset} · zoom ${layer.min_zoom}–${layer.max_zoom}`;
      card.append(metadata);
      if (layer.enabled && layer.supported) {
        const opacity = document.createElement("label");
        opacity.className = "opacity-control";
        const text = document.createElement("span");
        text.textContent = "Opacitet";
        const value = document.createElement("output");
        value.textContent = `${Math.round(layer.opacity * 100)} %`;
        const slider = document.createElement("input");
        slider.type = "range";
        slider.min = "0";
        slider.max = "100";
        slider.value = String(Math.round(layer.opacity * 100));
        slider.setAttribute("aria-label", `Opacitet för ${layer.name}`);
        slider.addEventListener("input", () => {
          layer.opacity = Number(slider.value) / 100;
          value.textContent = `${slider.value} %`;
          applyFeatureStyles();
        });
        opacity.append(text, slider, value);
        card.append(opacity);
      }
      checkbox.addEventListener("change", async () => {
        checkbox.disabled = true;
        try {
          const action = checkbox.checked ? "enable" : "disable";
          const response = await fetch(`/api/layers/${encodeURIComponent(layer.id)}/${action}`, {
            method: "POST",
            headers: { Accept: "application/json" },
          });
          if (!response.ok) throw new Error(`HTTP ${response.status}`);
          const updated = await response.json();
          renderLayers(state.layers.map((item) => item.id === updated.id ? updated : item));
          loadViewport();
        } catch (error) {
          checkbox.checked = !checkbox.checked;
          checkbox.disabled = false;
          console.error(error);
        }
      });
      group.append(card);
    });
    elements.layerList.append(group);
  });
  updateLayerStatistics();
  renderLegend();
  updateZoomInformation();
  applyFeatureStyles();
}

async function loadLayers() {
  const response = await fetch("/api/layers", {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const payload = await response.json();
  renderLayers(payload.layers);
}

function renderEvidenceRules(rules) {
  elements.rulesCount.textContent = rules.length.toLocaleString("sv-SE");
  elements.rulesList.replaceChildren();
  rules.forEach((rule) => {
    const item = document.createElement("div");
    item.className = `layer-item${rule.enabled ? " is-available" : ""}`;
    const content = document.createElement("span");
    const heading = document.createElement("strong");
    heading.textContent = `${rule.title} · v${rule.version}`;
    const details = document.createElement("small");
    details.textContent = `${rule.category} · ${rule.enabled ? "Aktiv" : "Inaktiv"} · ${rule.description}`;
    content.append(heading, details);
    item.append(content);
    elements.rulesList.append(item);
  });
}

async function loadEvidenceRules() {
  const response = await fetch("/api/evidence-rules", {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const payload = await response.json();
  renderEvidenceRules(payload.rules);
}

function renderEvidence(report) {
  elements.evidenceCount.textContent = report.evidence_count.toLocaleString("sv-SE");
  elements.evidenceList.replaceChildren();
  if (!report.evidence.length) {
    const empty = document.createElement("p");
    empty.textContent = "Inga evidensobjekt i kartutsnittet.";
    elements.evidenceList.append(empty);
    return;
  }
  report.evidence.slice(0, 100).forEach((evidence) => {
    const item = document.createElement("div");
    item.className = "layer-item is-available";
    const content = document.createElement("span");
    const heading = document.createElement("strong");
    heading.textContent = `${evidence.type} · ${evidence.provider}`;
    const details = document.createElement("small");
    details.textContent = `${evidence.strength} · ${evidence.provenance.source} · ${evidence.provenance.source_id}`;
    content.append(heading, details);
    item.append(content);
    elements.evidenceList.append(item);
  });
}

async function loadEvidence() {
  const parameters = viewportParameters();
  parameters.set("area", "visible-map");
  const response = await fetch(`/api/evidence-report?${parameters}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  renderEvidence(await response.json());
}

function renderAnalysis(analysis) {
  elements.analysisCount.textContent = analysis.summary.result_count.toLocaleString("sv-SE");
  elements.analysisList.replaceChildren();
  if (!analysis.results.length) {
    const empty = document.createElement("p");
    empty.textContent = "Inga analyser för evidensen i kartutsnittet.";
    elements.analysisList.append(empty);
    return;
  }
  analysis.results.slice(0, 100).forEach((result) => {
    const item = document.createElement("div");
    item.className = "layer-item is-available";
    const content = document.createElement("span");
    const heading = document.createElement("strong");
    heading.textContent = `${result.category} · ${result.confidence}`;
    const details = document.createElement("small");
    details.textContent = `${result.summary} · ${result.evidence_references.length} evidens · ${result.rule_id}@${result.rule_version}`;
    content.append(heading, details);
    item.append(content);
    elements.analysisList.append(item);
  });
}

async function loadAnalysis() {
  const parameters = viewportParameters();
  parameters.set("area", "visible-map");
  const response = await fetch(`/api/analysis-report?${parameters}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  renderAnalysis(await response.json());
}

function safeExternalLink(container, text, url) {
  container.textContent = "";
  if (!url) {
    container.textContent = text;
    return;
  }
  try {
    const parsed = new URL(url);
    if (!['https:', 'http:'].includes(parsed.protocol)) throw new Error("Unsafe URL");
    const link = document.createElement("a");
    link.textContent = text;
    link.href = parsed.href;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    container.append(link);
  } catch {
    container.textContent = text;
  }
}

function timeText(timeSpan) {
  if (!timeSpan) return "Tid saknas";
  if (timeSpan.original_text) return timeSpan.original_text;
  if (timeSpan.start && timeSpan.end) return `${timeSpan.start}–${timeSpan.end}`;
  return timeSpan.start || timeSpan.end || "Tid saknas";
}

function confidenceText(confidence) {
  if (!confidence) return "Okänd";
  return confidence.rationale
    ? `${confidence.label} – ${confidence.rationale}`
    : confidence.label;
}

function coordinatesText(feature) {
  const navigation = feature.properties.navigation;
  if (!navigation) return "Koordinater saknas";
  const suffix = navigation.approximate ? " (ungefärlig punkt)" : "";
  return `${navigation.latitude.toFixed(6)}, ${navigation.longitude.toFixed(6)}${suffix}`;
}

function provenanceText(properties) {
  const provenance = properties.provenance;
  if (!provenance) return "Proveniensuppgift saknas";
  const fetched = provenance.fetched_at
    ? new Date(provenance.fetched_at).toLocaleString("sv-SE")
    : "okänd hämtningstid";
  return `${provenance.source}, käll-ID ${provenance.source_id}, hämtad ${fetched}`;
}

function sourceProperty(properties, name) {
  const namespaces = Object.values(properties.source_properties || {});
  for (const values of namespaces) {
    if (values && typeof values === "object" && values[name] != null) {
      return values[name];
    }
  }
  return null;
}

function boundsForGeometry(geometry) {
  if (!geometry) return null;
  const points = [];
  function collect(coordinates) {
    if (typeof coordinates[0] === "number") {
      points.push(coordinates);
      return;
    }
    coordinates.forEach(collect);
  }
  collect(geometry.coordinates);
  if (!points.length) return null;
  return points.reduce(
    (bounds, point) => bounds.extend(point),
    new maplibregl.LngLatBounds(points[0], points[0]),
  );
}

function focusFeature(feature) {
  if (!state.map || !feature.geometry) return;
  if (feature.geometry.type === "Point") {
    state.map.flyTo({ center: feature.geometry.coordinates, zoom: 15, duration: 550 });
    return;
  }
  const bounds = boundsForGeometry(feature.geometry);
  if (bounds) state.map.fitBounds(bounds, { padding: 100, maxZoom: 15 });
}

function setSelectedState(featureId) {
  if (!state.map || !state.map.getSource("atlas-features")) return;
  if (state.selectedId !== null) {
    state.map.setFeatureState(
      { source: "atlas-features", id: state.selectedId },
      { selected: false },
    );
  }
  state.selectedId = featureId;
  state.map.setFeatureState(
    { source: "atlas-features", id: featureId },
    { selected: true },
  );
}

function animatePanel() {
  elements.infoPanel.classList.remove("panel-enter");
  requestAnimationFrame(() => elements.infoPanel.classList.add("panel-enter"));
}

function addRecent(featureId) {
  const recents = storedIds(STORAGE_KEYS.recents).filter((item) => item !== featureId);
  saveIds(STORAGE_KEYS.recents, [featureId, ...recents].slice(0, 8));
}

function updateFavoriteButton(featureId) {
  const favorite = storedIds(STORAGE_KEYS.favorites).includes(featureId);
  elements.favoriteButton.setAttribute("aria-pressed", String(favorite));
  elements.favoriteButton.textContent = favorite ? "★ Sparad favorit" : "☆ Spara favorit";
}

function toggleFavorite() {
  if (state.selectedId === null) return;
  const id = String(state.selectedId);
  const favorites = storedIds(STORAGE_KEYS.favorites);
  saveIds(
    STORAGE_KEYS.favorites,
    favorites.includes(id) ? favorites.filter((item) => item !== id) : [id, ...favorites],
  );
  updateFavoriteButton(id);
}

function showFeature(feature, { focus = false, remember = true } = {}) {
  const properties = feature.properties;
  const layer = layerForFeature(properties);
  elements.welcome.hidden = true;
  elements.libraryContent.hidden = true;
  elements.featureContent.hidden = false;
  elements.closePanel.hidden = false;
  elements.featureType.textContent = properties.feature_type;
  elements.featureTitle.textContent = properties.title;
  elements.featurePlace.textContent = properties.place || "Platsangivelse saknas";
  elements.featureTime.textContent = timeText(properties.time_span);
  elements.featureDescription.textContent = properties.description || "Beskrivning saknas.";
  elements.featureProvider.textContent = layer?.provider || properties.source?.name || "Okänd";
  elements.featureDataset.textContent = layer?.dataset || "Datasetuppgift saknas";
  elements.featureCategory.textContent = layer?.category || properties.feature_type;
  elements.geometryConfidence.textContent = confidenceText(properties.geometry_confidence);
  elements.featureConfidence.textContent = confidenceText(properties.confidence);
  safeExternalLink(
    elements.featureSource,
    `${properties.source.name} (${properties.source.id})`,
    properties.source.url,
  );
  const license = properties.license;
  if (license) safeExternalLink(elements.featureLicense, license.name, license.url);
  else elements.featureLicense.textContent = "Licensuppgift saknas";
  elements.featureProvenance.textContent = provenanceText(properties);
  elements.featureCoordinates.textContent = coordinatesText(feature);
  const sourceId = properties.source?.id;
  [
    [elements.sourceIdRow, elements.sourceId, sourceId],
    [elements.sourceCategoryRow, elements.sourceCategory, sourceProperty(properties, "category")],
    [elements.sourceUpdatedRow, elements.sourceUpdated, sourceProperty(properties, "last_updated")],
  ].forEach(([row, target, value]) => {
    row.hidden = !value;
    target.textContent = value || "";
  });

  const navigation = properties.navigation;
  elements.navigateButton.hidden = !navigation;
  elements.navigationNote.hidden = !navigation;
  if (navigation) {
    elements.navigateButton.href = navigation.url;
    elements.navigationNote.textContent = navigation.approximate
      ? "Navigationen använder en ungefärlig punkt för objektet."
      : "Navigationen öppnas i OpenStreetMap.";
  } else {
    elements.navigateButton.removeAttribute("href");
  }

  setSelectedState(feature.id);
  updateFavoriteButton(String(feature.id));
  if (remember) addRecent(String(feature.id));
  if (focus) focusFeature(feature);
  elements.infoPanel.scrollTop = 0;
  animatePanel();
}

function appendText(parent, className, text) {
  const element = document.createElement("p");
  element.className = className;
  element.textContent = text;
  parent.append(element);
}

function popupAction(label, handler) {
  const button = document.createElement("button");
  button.className = "popup-button";
  button.type = "button";
  button.textContent = label;
  button.addEventListener("click", handler);
  return button;
}

function showWhy(feature) {
  const discovery = feature.properties.discovery;
  elements.whySources.textContent = discovery.supporting_sources.join(", ") || "Okänd";
  elements.whyEstimated.textContent = discovery.estimated
    ? "Ja, minst en uppgift är uppskattad eller osäker."
    : "Nej, inga uppskattningar är markerade.";
  elements.whyDataSource.textContent = discovery.data_source;
  if (!elements.whyDialog.open) elements.whyDialog.showModal();
}

function showPopup(feature, coordinates) {
  if (state.popup) state.popup.remove();
  const properties = feature.properties;
  const layer = layerForFeature(properties);
  const card = document.createElement("div");
  card.className = "popup-card";
  const title = document.createElement("strong");
  title.className = "popup-title";
  title.textContent = properties.title;
  card.append(title);
  appendText(
    card,
    "popup-meta",
    [properties.feature_type, properties.place].filter(Boolean).join(" · "),
  );
  const facts = document.createElement("dl");
  facts.className = "popup-facts";
  [
    ["Provider", layer?.provider || properties.source?.name],
    ["Dataset", layer?.dataset],
    ["Kategori", layer?.category || properties.feature_type],
    ["Confidence", confidenceText(properties.confidence)],
    ["Licens", properties.license?.name],
  ].filter(([, value]) => value).forEach(([label, value]) => {
    const row = document.createElement("div");
    const term = document.createElement("dt");
    term.textContent = label;
    const description = document.createElement("dd");
    description.textContent = value;
    row.append(term, description);
    facts.append(row);
  });
  card.append(facts);
  if (properties.source?.name) appendText(card, "popup-source", properties.source.name);
  const actions = document.createElement("div");
  actions.className = "popup-actions";
  actions.append(popupAction("Visa detaljer", () => loadFeatureDetails(feature.id)));
  card.append(actions);
  if (properties.navigation) {
    const navigate = document.createElement("a");
    navigate.className = "primary-button";
    navigate.textContent = "Navigera hit";
    navigate.href = properties.navigation.url;
    navigate.target = "_blank";
    navigate.rel = "noopener noreferrer";
    card.append(navigate);
  }
  state.popup = new maplibregl.Popup({ closeButton: true, maxWidth: "21rem" })
    .setLngLat(coordinates)
    .setDOMContent(card)
    .addTo(state.map);
}

async function loadFeatureDetails(featureId, { focus = false } = {}) {
  const known = findFeature(featureId);
  if (known?.properties?.provenance) {
    showFeature(known, { focus });
    return known;
  }
  try {
    const response = await fetch(`/api/features/${encodeURIComponent(featureId)}`, {
      headers: { Accept: "application/geo+json" },
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const feature = await response.json();
    state.featureIndex.set(String(feature.id), feature);
    showFeature(feature, { focus });
    return feature;
  } catch (error) {
    elements.mapStatus.hidden = false;
    elements.mapStatus.classList.add("is-error");
    elements.mapStatusText.textContent = "Objektets detaljer kunde inte laddas.";
    console.error(error);
    return null;
  }
}

async function selectFeature(feature, { focus = true, popup = false, coordinates = null } = {}) {
  const detailed = await loadFeatureDetails(feature.id, { focus });
  if (popup && coordinates && detailed) showPopup(detailed, coordinates);
  closeSearch();
}

function clearSelectedState() {
  if (state.selectedId !== null && state.map?.getSource("atlas-features")) {
    state.map.setFeatureState(
      { source: "atlas-features", id: state.selectedId },
      { selected: false },
    );
  }
  state.selectedId = null;
}

function closePanel() {
  elements.featureContent.hidden = true;
  elements.libraryContent.hidden = true;
  elements.closePanel.hidden = true;
  elements.welcome.hidden = false;
  if (state.popup) state.popup.remove();
  clearSelectedState();
}

function closeSearch() {
  elements.searchResults.hidden = true;
  elements.searchInput.setAttribute("aria-expanded", "false");
}

function searchParameters() {
  const parameters = new URLSearchParams();
  const query = elements.searchInput.value.trim();
  if (query) parameters.set("q", query);
  if (elements.typeFilter.value) parameters.append("type", elements.typeFilter.value);
  if (elements.periodFilter.value) parameters.append("period", elements.periodFilter.value);
  if (elements.sourceFilter.value) parameters.append("source", elements.sourceFilter.value);
  return parameters;
}

function renderSearchResults(features, message = null) {
  elements.searchResults.replaceChildren();
  if (message || !features.length) {
    const empty = document.createElement("p");
    empty.className = "search-empty";
    empty.textContent = message || "Ingen plats matchar din sökning och dina filter.";
    elements.searchResults.append(empty);
  } else {
    const summary = document.createElement("p");
    summary.className = "search-summary";
    summary.textContent = `${features.length.toLocaleString("sv-SE")} träffar · visa med Enter`;
    elements.searchResults.append(summary);
    features.slice(0, 20).forEach((feature) => {
      const button = document.createElement("button");
      button.className = "search-result";
      button.type = "button";
      button.setAttribute("role", "option");
      const title = document.createElement("strong");
      title.textContent = feature.properties.title;
      const detail = document.createElement("small");
      detail.textContent = [
        feature.properties.feature_type,
        feature.properties.place,
        feature.properties.source?.id,
      ].filter(Boolean).join(" · ");
      button.append(title, detail);
      button.addEventListener("click", () => selectFeature(feature));
      elements.searchResults.append(button);
    });
  }
  elements.searchResults.hidden = false;
  elements.searchInput.setAttribute("aria-expanded", "true");
}

function updateVisibleFeatures(collection) {
  const source = state.map?.getSource("atlas-features");
  if (source) source.setData(collection);
  elements.activeFeatureCount.textContent = collection.features.length.toLocaleString("sv-SE");
  applyFeatureStyles();
}

function styleExpressions() {
  const sources = new Map();
  state.collection.features.forEach((feature) => {
    const name = feature.properties.source?.name;
    if (!name || sources.has(name)) return;
    const layer = layerForFeature(feature.properties);
    sources.set(name, {
      color: layer ? layerColor(layer) : stableColor(name),
      opacity: layer?.opacity ?? 0.8,
    });
  });
  if (!sources.size) return { color: "#55615a", opacity: 0.75 };
  const sourceName = ["get", "name", ["get", "source"]];
  const color = ["match", sourceName];
  const opacity = ["match", sourceName];
  sources.forEach((style, name) => {
    color.push(name, style.color);
    opacity.push(name, style.opacity);
  });
  color.push("#55615a");
  opacity.push(0.75);
  return { color, opacity };
}

function applyFeatureStyles() {
  if (!state.map?.getLayer("atlas-points")) return;
  const expressions = styleExpressions();
  const selectedColor = [
    "case",
    ["boolean", ["feature-state", "selected"], false],
    "#f59e0b",
    expressions.color,
  ];
  state.map.setPaintProperty("atlas-polygons", "fill-color", selectedColor);
  state.map.setPaintProperty(
    "atlas-polygons",
    "fill-opacity",
    ["*", expressions.opacity, 0.42],
  );
  state.map.setPaintProperty("atlas-lines", "line-color", selectedColor);
  state.map.setPaintProperty("atlas-lines", "line-opacity", expressions.opacity);
  state.map.setPaintProperty("atlas-point-halos", "circle-stroke-color", expressions.color);
  state.map.setPaintProperty("atlas-point-halos", "circle-opacity", expressions.opacity);
  state.map.setPaintProperty("atlas-points", "circle-color", selectedColor);
  state.map.setPaintProperty("atlas-points", "circle-opacity", expressions.opacity);
}

function replaceViewport(collection) {
  state.collection = collection;
  state.featureIndex = new Map(
    collection.features.map((feature) => [String(feature.id), feature]),
  );
  initializeFacets();
  updateVisibleFeatures(collection);
  if (state.lastPosition) {
    const { latitude, longitude } = state.lastPosition.coords;
    renderNearestFeatures(latitude, longitude);
  }
}

function viewportParameters() {
  const bounds = state.map.getBounds();
  let west = Math.max(-180, bounds.getWest());
  let east = Math.min(180, bounds.getEast());
  if (west > east) [west, east] = [-180, 180];
  return new URLSearchParams({
    bbox: [west, bounds.getSouth(), east, bounds.getNorth()].join(","),
    limit: "5000",
  });
}

async function loadViewport() {
  if (!state.map || state.searchActive) return;
  if (state.viewportController) state.viewportController.abort();
  state.viewportController = new AbortController();
  elements.mapStatus.hidden = false;
  elements.mapStatus.classList.remove("is-error");
  elements.mapStatusText.textContent = "Laddar synligt kartutsnitt…";
  try {
    const response = await fetch(`/api/features?${viewportParameters()}`, {
      signal: state.viewportController.signal,
      headers: { Accept: "application/geo+json" },
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const collection = await response.json();
    replaceViewport(collection);
    await loadEvidence();
    await loadAnalysis();
    if (collection.summary.truncated) {
      elements.mapStatusText.textContent = "Många objekt finns här. Zooma in för att se alla.";
    } else {
      elements.mapStatus.hidden = true;
    }
  } catch (error) {
    if (error.name !== "AbortError") {
      elements.mapStatus.classList.add("is-error");
      elements.mapStatusText.textContent = "Kartutsnittet kunde inte laddas. Försök igen.";
      console.error(error);
    }
  }
}

function scheduleViewportLoad() {
  window.clearTimeout(state.viewportTimer);
  state.viewportTimer = window.setTimeout(loadViewport, 180);
}

async function runSearch() {
  const parameters = searchParameters();
  if (!parameters.toString()) {
    state.searchActive = false;
    loadViewport();
    closeSearch();
    return;
  }
  state.searchActive = true;
  if (state.searchController) state.searchController.abort();
  state.searchController = new AbortController();
  try {
    const response = await fetch(`/api/search?${parameters}`, {
      signal: state.searchController.signal,
      headers: { Accept: "application/geo+json" },
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const result = await response.json();
    clearSelectedState();
    updateVisibleFeatures(result);
    renderSearchResults(result.features);
  } catch (error) {
    if (error.name !== "AbortError") {
      renderSearchResults(
        [],
        "Sökningen kunde inte genomföras. Kontrollera att servern körs och försök igen.",
      );
      console.error(error);
    }
  }
}

function scheduleSearch() {
  window.clearTimeout(state.searchTimer);
  state.searchTimer = window.setTimeout(runSearch, 120);
}

function addOptions(select, values) {
  const existing = new Set([...select.options].map((option) => option.value));
  [...values].sort((left, right) => left.localeCompare(right, "sv-SE")).forEach((value) => {
    if (existing.has(value)) return;
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.append(option);
  });
}

function initializeFacets() {
  const properties = state.collection.features.map((feature) => feature.properties);
  addOptions(elements.typeFilter, new Set(properties.map((item) => item.feature_type)));
  addOptions(elements.sourceFilter, new Set(properties.map((item) => item.source.name)));
}

function renderDatasetSummary(summary) {
  state.datasetSummary = summary;
  elements.datasetStatus.textContent = summary.status;
  elements.datasetCount.textContent = summary.count.toLocaleString("sv-SE");
  elements.activeFeatureCount.textContent = summary.count.toLocaleString("sv-SE");
  elements.datasetImport.textContent = summary.latest_import
    ? new Date(summary.latest_import).toLocaleString("sv-SE")
    : "Ingen import registrerad";
  elements.datasetSource.textContent = summary.source || "Ingen datakälla";
}

function distanceKilometers(latitude, longitude, targetLatitude, targetLongitude) {
  const radians = (degrees) => degrees * Math.PI / 180;
  const latitudeDelta = radians(targetLatitude - latitude);
  const longitudeDelta = radians(targetLongitude - longitude);
  const startLatitude = radians(latitude);
  const endLatitude = radians(targetLatitude);
  const value = Math.sin(latitudeDelta / 2) ** 2
    + Math.cos(startLatitude) * Math.cos(endLatitude)
    * Math.sin(longitudeDelta / 2) ** 2;
  return 6371 * 2 * Math.atan2(Math.sqrt(value), Math.sqrt(1 - value));
}

function renderNearestFeatures(latitude, longitude) {
  const nearest = state.collection.features
    .filter((feature) => feature.properties.navigation)
    .map((feature) => {
      const target = feature.properties.navigation;
      return {
        feature,
        distance: distanceKilometers(
          latitude,
          longitude,
          target.latitude,
          target.longitude,
        ),
      };
    })
    .sort((left, right) => left.distance - right.distance)
    .slice(0, 5);
  elements.nearestList.replaceChildren();
  nearest.forEach(({ feature, distance }) => {
    const button = document.createElement("button");
    button.className = "nearest-item";
    button.type = "button";
    const title = document.createElement("strong");
    title.textContent = feature.properties.title;
    const detail = document.createElement("span");
    detail.textContent = distance < 1
      ? `${Math.round(distance * 1000)} m bort`
      : `${distance.toFixed(1)} km bort`;
    button.append(title, detail);
    button.addEventListener("click", () => selectFeature(feature));
    elements.nearestList.append(button);
  });
  elements.nearestContent.hidden = nearest.length === 0;
}

function locationErrorMessage(error) {
  if (error.code === error.PERMISSION_DENIED) {
    return "Platsåtkomst nekades. Tillåt platsåtkomst i webbläsaren och försök igen.";
  }
  if (error.code === error.POSITION_UNAVAILABLE) {
    return "Din position kunde inte bestämmas. Kontrollera enhetens platstjänster.";
  }
  if (error.code === error.TIMEOUT) {
    return "GPS-positionen tog för lång tid. Försök igen utomhus eller med bättre signal.";
  }
  return "Din position kunde inte hämtas.";
}

function updateLocation(position) {
  state.lastPosition = position;
  const { longitude, latitude, accuracy } = position.coords;
  const coordinates = [longitude, latitude];
  elements.locationAccuracy.textContent = `Noggrannhet: cirka ${Math.round(accuracy)} meter`;
  elements.locationHeading.textContent = "Din aktuella position";
  if (!state.locationMarker) {
    const marker = document.createElement("div");
    marker.className = "location-marker";
    marker.setAttribute("aria-label", "Din aktuella GPS-position");
    state.locationMarker = new maplibregl.Marker({ element: marker })
      .setLngLat(coordinates)
      .addTo(state.map);
  } else {
    state.locationMarker.setLngLat(coordinates);
  }
  renderNearestFeatures(latitude, longitude);
  if (state.followLocation || state.centerOnNextLocation) {
    state.map.easeTo({ center: coordinates, zoom: Math.max(state.map.getZoom(), 15) });
    state.centerOnNextLocation = false;
  }
}

function handleLocationError(error) {
  elements.locationHeading.textContent = "GPS kunde inte startas";
  elements.locationAccuracy.textContent = locationErrorMessage(error);
  state.followLocation = false;
  elements.followLocation.setAttribute("aria-pressed", "false");
  elements.followLocation.textContent = "Följ mig: av";
}

function startLocationWatch() {
  if (state.locationWatchId !== null) return true;
  if (!navigator.geolocation) {
    elements.locationHeading.textContent = "GPS stöds inte";
    elements.locationAccuracy.textContent = "Webbläsaren saknar stöd för platsåtkomst.";
    return false;
  }
  elements.locationHeading.textContent = "Söker efter din position…";
  elements.locationAccuracy.textContent = "Väntar på GPS-signal";
  state.locationWatchId = navigator.geolocation.watchPosition(
    updateLocation,
    handleLocationError,
    { enableHighAccuracy: true, timeout: 15000, maximumAge: 5000 },
  );
  return true;
}

function centerOnLocation() {
  state.centerOnNextLocation = true;
  if (!startLocationWatch()) return;
  if (state.lastPosition) {
    const { longitude, latitude } = state.lastPosition.coords;
    state.map.easeTo({ center: [longitude, latitude], zoom: Math.max(state.map.getZoom(), 15) });
    state.centerOnNextLocation = false;
  }
}

async function startAtGrantedLocation() {
  if (!navigator.permissions || !navigator.geolocation) return;
  try {
    const permission = await navigator.permissions.query({ name: "geolocation" });
    if (permission.state === "granted") {
      state.centerOnNextLocation = true;
      startLocationWatch();
    }
  } catch {
    // Older browsers can use the explicit location buttons instead.
  }
}

function toggleFollowLocation() {
  const nextValue = !state.followLocation;
  if (nextValue && !startLocationWatch()) return;
  state.followLocation = nextValue;
  elements.followLocation.setAttribute("aria-pressed", String(nextValue));
  elements.followLocation.textContent = `Följ mig: ${nextValue ? "på" : "av"}`;
  if (nextValue) centerOnLocation();
}

function renderSavedList(container, ids, emptyText) {
  container.replaceChildren();
  const features = ids.map(findFeature).filter(Boolean);
  if (!features.length) {
    const empty = document.createElement("p");
    empty.className = "saved-empty";
    empty.textContent = emptyText;
    container.append(empty);
    return;
  }
  features.forEach((feature) => {
    const button = document.createElement("button");
    button.className = "saved-item";
    button.type = "button";
    button.textContent = feature.properties.title;
    button.addEventListener("click", () => selectFeature(feature));
    container.append(button);
  });
}

function showLibrary() {
  elements.welcome.hidden = true;
  elements.featureContent.hidden = true;
  elements.libraryContent.hidden = false;
  elements.closePanel.hidden = false;
  renderSavedList(
    elements.favoriteList,
    storedIds(STORAGE_KEYS.favorites),
    "Du har inga sparade favoriter ännu.",
  );
  renderSavedList(
    elements.recentList,
    storedIds(STORAGE_KEYS.recents),
    "Inga platser har öppnats ännu.",
  );
  animatePanel();
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  elements.themeButton.textContent = theme === "dark" ? "☀" : "◐";
  elements.themeButton.title = theme === "dark" ? "Byt till ljust läge" : "Byt till mörkt läge";
}

function toggleTheme() {
  const theme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  localStorage.setItem(STORAGE_KEYS.theme, theme);
  applyTheme(theme);
}

function initialTheme() {
  const stored = localStorage.getItem(STORAGE_KEYS.theme);
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function installFeatureLayers() {
  state.map.addSource("atlas-features", {
    type: "geojson",
    data: state.collection,
    promoteId: "feature_id",
    cluster: true,
    clusterMaxZoom: 12,
    clusterRadius: 48,
  });
  state.map.addLayer({
    id: "atlas-clusters",
    type: "circle",
    source: "atlas-features",
    filter: ["has", "point_count"],
    paint: {
      "circle-color": "#6f3028",
      "circle-radius": ["step", ["get", "point_count"], 18, 10, 23, 30, 29],
      "circle-stroke-color": "#d4a84f",
      "circle-stroke-width": 3,
    },
  });
  state.map.addLayer({
    id: "atlas-cluster-count",
    type: "symbol",
    source: "atlas-features",
    filter: ["has", "point_count"],
    layout: { "text-field": ["get", "point_count_abbreviated"], "text-size": 13 },
    paint: { "text-color": "#ffffff" },
  });
  state.map.addLayer({
    id: "atlas-polygons",
    type: "fill",
    source: "atlas-features",
    filter: ["==", ["geometry-type"], "Polygon"],
    paint: {
      "fill-color": ["case", ["boolean", ["feature-state", "selected"], false], "#b45309", "#174d35"],
      "fill-opacity": 0.28,
      "fill-outline-color": "#123d2b",
    },
  });
  state.map.addLayer({
    id: "atlas-lines",
    type: "line",
    source: "atlas-features",
    filter: ["==", ["geometry-type"], "LineString"],
    paint: {
      "line-color": ["case", ["boolean", ["feature-state", "selected"], false], "#b45309", "#174d35"],
      "line-width": ["case", ["boolean", ["feature-state", "selected"], false], 6, 4],
    },
  });
  state.map.addLayer({
    id: "atlas-point-halos",
    type: "circle",
    source: "atlas-features",
    filter: ["!", ["has", "point_count"]],
    paint: {
      "circle-radius": ["case", ["boolean", ["feature-state", "selected"], false], 14, 11],
      "circle-color": "#f4ead2",
      "circle-opacity": 0.92,
      "circle-stroke-color": "#6f3028",
      "circle-stroke-width": 1.5,
    },
  });
  state.map.addLayer({
    id: "atlas-points",
    type: "circle",
    source: "atlas-features",
    filter: ["!", ["has", "point_count"]],
    paint: {
      "circle-radius": ["case", ["boolean", ["feature-state", "selected"], false], 8, 6],
      "circle-color": ["case", ["boolean", ["feature-state", "selected"], false], "#c47a2c", "#6f3028"],
      "circle-stroke-color": "#f4ead2",
      "circle-stroke-width": 1.5,
    },
  });

  state.map.on("click", "atlas-clusters", async (event) => {
    const cluster = event.features?.[0];
    if (!cluster) return;
    const source = state.map.getSource("atlas-features");
    const zoom = await source.getClusterExpansionZoom(cluster.properties.cluster_id);
    state.map.easeTo({ center: cluster.geometry.coordinates, zoom });
  });

  ["atlas-polygons", "atlas-lines", "atlas-points"].forEach((layerId) => {
    state.map.on("mouseenter", layerId, () => { state.map.getCanvas().style.cursor = "pointer"; });
    state.map.on("mouseleave", layerId, () => { state.map.getCanvas().style.cursor = ""; });
    state.map.on("click", layerId, (event) => {
      const rendered = event.features?.[0];
      const feature = rendered ? findFeature(rendered.id) : null;
      if (feature) selectFeature(feature, { focus: true, popup: true, coordinates: event.lngLat });
    });
  });
  applyFeatureStyles();
}

function cacheElements() {
  const ids = {
    searchInput: "feature-search", searchResults: "search-results",
    typeFilter: "type-filter", periodFilter: "period-filter", sourceFilter: "source-filter",
    clearFilters: "clear-filters", libraryButton: "library-button", themeButton: "theme-button",
    mapStatus: "map-status", infoPanel: "info-panel", welcome: "welcome-content",
    libraryContent: "library-content", favoriteList: "favorite-list", recentList: "recent-list",
    featureContent: "feature-content", closePanel: "close-panel", featureType: "feature-type",
    featureTitle: "feature-title", featurePlace: "feature-place", featureTime: "feature-time",
    featureDescription: "feature-description", featureProvider: "feature-provider",
    featureDataset: "feature-dataset", featureCategory: "feature-category",
    geometryConfidence: "geometry-confidence",
    featureConfidence: "feature-confidence", featureSource: "feature-source",
    featureLicense: "feature-license", featureProvenance: "feature-provenance",
    featureCoordinates: "feature-coordinates", navigationNote: "navigation-note",
    sourceIdRow: "source-id-row", sourceId: "source-id",
    sourceCategoryRow: "source-category-row", sourceCategory: "source-category",
    sourceUpdatedRow: "source-updated-row", sourceUpdated: "source-updated",
    navigateButton: "navigate-button", favoriteButton: "favorite-button", whyButton: "why-button",
    whyDialog: "why-dialog", closeWhy: "close-why", whySources: "why-sources",
    whyEstimated: "why-estimated", whyDataSource: "why-data-source",
    emptyState: "empty-state", mapStatusText: "map-status-text",
    centerLocation: "center-location", followLocation: "follow-location",
    locationHeading: "location-heading", locationAccuracy: "location-accuracy",
    demoNotice: "demo-notice", nearestContent: "nearest-content",
    nearestList: "nearest-list",
    datasetStatus: "dataset-status", datasetCount: "dataset-count",
    datasetImport: "dataset-import", datasetSource: "dataset-source",
    layerList: "layer-list", legendList: "legend-list",
    layerZoomInfo: "layer-zoom-info", activeLayerCount: "active-layer-count",
    activeFeatureCount: "active-feature-count", activeProviderCount: "active-provider-count",
    activeLayerStat: "active-layer-stat",
    evidenceCount: "evidence-count", evidenceList: "evidence-list",
    rulesCount: "rules-count", rulesList: "rules-list",
    analysisCount: "analysis-count", analysisList: "analysis-list",
  };
  Object.entries(ids).forEach(([name, id]) => { elements[name] = byId(id); });
}

function installInterfaceEvents() {
  elements.searchInput.addEventListener("input", scheduleSearch);
  elements.searchInput.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeSearch();
    if (event.key === "Enter") elements.searchResults.querySelector(".search-result")?.click();
    if (event.key === "ArrowDown") {
      event.preventDefault();
      elements.searchResults.querySelector(".search-result")?.focus();
    }
  });
  elements.searchResults.addEventListener("keydown", (event) => {
    const results = [...elements.searchResults.querySelectorAll(".search-result")];
    const index = results.indexOf(document.activeElement);
    if (event.key === "ArrowDown" && results[index + 1]) results[index + 1].focus();
    if (event.key === "ArrowUp") (results[index - 1] || elements.searchInput).focus();
    if (event.key === "Escape") {
      closeSearch();
      elements.searchInput.focus();
    }
  });
  [elements.typeFilter, elements.periodFilter, elements.sourceFilter].forEach((filter) => {
    filter.addEventListener("change", runSearch);
  });
  elements.clearFilters.addEventListener("click", () => {
    elements.searchInput.value = "";
    elements.typeFilter.value = "";
    elements.periodFilter.value = "";
    elements.sourceFilter.value = "";
    state.searchActive = false;
    loadViewport();
    closeSearch();
  });
  elements.closePanel.addEventListener("click", closePanel);
  elements.favoriteButton.addEventListener("click", toggleFavorite);
  elements.libraryButton.addEventListener("click", showLibrary);
  elements.themeButton.addEventListener("click", toggleTheme);
  elements.centerLocation.addEventListener("click", centerOnLocation);
  elements.followLocation.addEventListener("click", toggleFollowLocation);
  elements.whyButton.addEventListener("click", () => {
    const feature = findFeature(state.selectedId);
    if (feature) showWhy(feature);
  });
  elements.closeWhy.addEventListener("click", () => elements.whyDialog.close());
  elements.whyDialog.addEventListener("click", (event) => {
    if (event.target === elements.whyDialog) elements.whyDialog.close();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeSearch();
  });
}

async function initialize() {
  cacheElements();
  installInterfaceEvents();
  applyTheme(initialTheme());
  try {
    const response = await fetch("/api/dataset", {
      headers: { Accept: "application/json" },
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const dataset = await response.json();
    renderDatasetSummary(dataset);
    await loadLayers();
    await loadEvidenceRules();
    state.map = new maplibregl.Map({
      container: "map",
      center: [16.5, 62.0],
      zoom: 4.1,
      attributionControl: false,
      style: {
        version: 8,
        sources: {
          osm: {
            type: "raster",
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            maxzoom: 19,
            attribution: "<a href=\"https://www.openstreetmap.org/copyright\" target=\"_blank\" rel=\"noopener noreferrer\">© OpenStreetMap contributors</a>",
          },
        },
        layers: [{ id: "osm", type: "raster", source: "osm" }],
      },
    });
    state.map.addControl(
      new maplibregl.NavigationControl({ showCompass: true, visualizePitch: true }),
      "top-left",
    );
    state.map.addControl(new maplibregl.FullscreenControl(), "top-left");
    state.map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");
    state.map.addControl(
      new maplibregl.AttributionControl({ compact: false }),
      "bottom-right",
    );
    state.map.on("load", () => {
      installFeatureLayers();
      const hasFeatures = dataset.count !== 0;
      elements.emptyState.hidden = hasFeatures;
      elements.infoPanel.hidden = !hasFeatures;
      elements.demoNotice.hidden = !dataset.is_demo;
      loadViewport();
      startAtGrantedLocation();
    });
    state.map.on("moveend", scheduleViewportLoad);
    state.map.on("zoomend", updateZoomInformation);
    state.map.on("error", (event) => {
      elements.mapStatus.hidden = false;
      elements.mapStatus.classList.add("is-error");
      elements.mapStatusText.textContent = event.error?.message?.includes("tile")
        ? "Baskartan kunde inte laddas. Kontrollera internetanslutningen."
        : "Kartan kunde inte ladda alla resurser. Försök att ladda om sidan.";
    });
  } catch (error) {
    elements.mapStatus.classList.add("is-error");
    elements.mapStatusText.textContent = "Lokala platser kunde inte laddas. Kontrollera att servern körs och ladda om sidan.";
    console.error(error);
  }
}

window.addEventListener("DOMContentLoaded", initialize);
