"use strict";

const STORAGE_KEYS = {
  favorites: "magnetatlas.favorites",
  recents: "magnetatlas.recents",
  theme: "magnetatlas.theme",
};

const state = {
  map: null,
  collection: { type: "FeatureCollection", features: [] },
  selectedId: null,
  popup: null,
  searchTimer: null,
  searchController: null,
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
  return state.collection.features.find(
    (feature) => String(feature.id) === String(featureId),
  );
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
    state.map.flyTo({ center: feature.geometry.coordinates, zoom: 14 });
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
  elements.welcome.hidden = true;
  elements.libraryContent.hidden = true;
  elements.featureContent.hidden = false;
  elements.closePanel.hidden = false;
  elements.featureType.textContent = properties.feature_type;
  elements.featureTitle.textContent = properties.title;
  elements.featurePlace.textContent = properties.place || "Platsangivelse saknas";
  elements.featureTime.textContent = timeText(properties.time_span);
  elements.featureDescription.textContent = properties.description || "Beskrivning saknas.";
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
  const card = document.createElement("div");
  card.className = "popup-card";
  const title = document.createElement("strong");
  title.className = "popup-title";
  title.textContent = properties.title;
  card.append(title);
  appendText(card, "popup-meta", `${properties.feature_type} · ${timeText(properties.time_span)}`);
  appendText(card, "popup-history", properties.description || "Kort historik saknas.");
  appendText(card, "popup-meta", `Källa: ${properties.source.name}`);
  appendText(card, "popup-meta", `Licens: ${properties.license?.name || "Okänd"}`);
  appendText(card, "popup-meta", `Confidence: ${confidenceText(properties.confidence)}`);
  const actions = document.createElement("div");
  actions.className = "popup-actions";
  actions.append(
    popupAction("Visa mer", () => showFeature(feature)),
    popupAction("Varför?", () => showWhy(feature)),
  );
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

function selectFeature(feature, { focus = true, popup = false, coordinates = null } = {}) {
  showFeature(feature, { focus });
  if (popup && coordinates) showPopup(feature, coordinates);
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

function renderSearchResults(features) {
  elements.searchResults.replaceChildren();
  if (!features.length) {
    const empty = document.createElement("p");
    empty.className = "search-empty";
    empty.textContent = "Ingen plats hittades i den lokala atlasen.";
    elements.searchResults.append(empty);
  } else {
    features.slice(0, 20).forEach((feature) => {
      const button = document.createElement("button");
      button.className = "search-result";
      button.type = "button";
      button.setAttribute("role", "option");
      const title = document.createElement("strong");
      title.textContent = feature.properties.title;
      const detail = document.createElement("small");
      detail.textContent = feature.properties.place || feature.properties.feature_type;
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
}

async function runSearch() {
  const parameters = searchParameters();
  if (!parameters.toString()) {
    updateVisibleFeatures(state.collection);
    closeSearch();
    return;
  }
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
      renderSearchResults([]);
      console.error(error);
    }
  }
}

function scheduleSearch() {
  window.clearTimeout(state.searchTimer);
  state.searchTimer = window.setTimeout(runSearch, 120);
}

function addOptions(select, values) {
  [...values].sort((left, right) => left.localeCompare(right, "sv-SE")).forEach((value) => {
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
      "circle-color": "#174d35",
      "circle-radius": ["step", ["get", "point_count"], 18, 10, 23, 30, 29],
      "circle-stroke-color": "#fffdf8",
      "circle-stroke-width": 2,
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
    id: "atlas-points",
    type: "circle",
    source: "atlas-features",
    filter: ["!", ["has", "point_count"]],
    paint: {
      "circle-radius": ["case", ["boolean", ["feature-state", "selected"], false], 10, 7],
      "circle-color": ["case", ["boolean", ["feature-state", "selected"], false], "#b45309", "#174d35"],
      "circle-stroke-color": "#fffdf8",
      "circle-stroke-width": 2,
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
    featureDescription: "feature-description", geometryConfidence: "geometry-confidence",
    featureConfidence: "feature-confidence", featureSource: "feature-source",
    featureLicense: "feature-license", navigationNote: "navigation-note",
    navigateButton: "navigate-button", favoriteButton: "favorite-button", whyButton: "why-button",
    whyDialog: "why-dialog", closeWhy: "close-why", whySources: "why-sources",
    whyEstimated: "why-estimated", whyDataSource: "why-data-source",
  };
  Object.entries(ids).forEach(([name, id]) => { elements[name] = byId(id); });
}

function installInterfaceEvents() {
  elements.searchInput.addEventListener("input", scheduleSearch);
  elements.searchInput.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeSearch();
    if (event.key === "Enter") elements.searchResults.querySelector(".search-result")?.click();
  });
  [elements.typeFilter, elements.periodFilter, elements.sourceFilter].forEach((filter) => {
    filter.addEventListener("change", runSearch);
  });
  elements.clearFilters.addEventListener("click", () => {
    elements.searchInput.value = "";
    elements.typeFilter.value = "";
    elements.periodFilter.value = "";
    elements.sourceFilter.value = "";
    updateVisibleFeatures(state.collection);
    closeSearch();
  });
  elements.closePanel.addEventListener("click", closePanel);
  elements.favoriteButton.addEventListener("click", toggleFavorite);
  elements.libraryButton.addEventListener("click", showLibrary);
  elements.themeButton.addEventListener("click", toggleTheme);
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
    const response = await fetch("/api/features", {
      headers: { Accept: "application/geo+json" },
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.collection = await response.json();
    initializeFacets();
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
    state.map.addControl(
      new maplibregl.GeolocateControl({
        positionOptions: { enableHighAccuracy: false },
        trackUserLocation: false,
        showAccuracyCircle: true,
      }),
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
      elements.mapStatus.hidden = true;
      elements.searchInput.focus();
    });
    state.map.on("error", () => {
      elements.mapStatus.textContent = "Kartan kunde inte ladda alla resurser.";
    });
  } catch (error) {
    elements.mapStatus.textContent = "MagnetAtlas kunde inte ladda kartan.";
    console.error(error);
  }
}

window.addEventListener("DOMContentLoaded", initialize);
