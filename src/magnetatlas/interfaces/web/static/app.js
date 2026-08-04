"use strict";

const state = {
  map: null,
  collection: { type: "FeatureCollection", features: [] },
  selectedId: null,
  popup: null,
};

const elements = {};

function byId(id) {
  return document.getElementById(id);
}

function safeExternalLink(container, text, url) {
  container.textContent = "";
  if (!url) {
    container.textContent = text;
    return;
  }
  try {
    const parsed = new URL(url);
    if (parsed.protocol !== "https:" && parsed.protocol !== "http:") {
      container.textContent = text;
      return;
    }
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
  const score = confidence.value === null ? "" : ` (${Math.round(confidence.value * 100)} %)`;
  const rationale = confidence.rationale ? ` – ${confidence.rationale}` : "";
  return `${confidence.label}${score}${rationale}`;
}

function findFeature(featureId) {
  return state.collection.features.find((feature) => String(feature.id) === String(featureId));
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
    state.map.flyTo({ center: feature.geometry.coordinates, zoom: 13 });
    return;
  }
  const bounds = boundsForGeometry(feature.geometry);
  if (bounds) state.map.fitBounds(bounds, { padding: 90, maxZoom: 14 });
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

function showFeature(feature, { focus = false } = {}) {
  const properties = feature.properties;
  elements.welcome.hidden = true;
  elements.featureContent.hidden = false;
  elements.closePanel.hidden = false;
  elements.featureType.textContent = properties.feature_type;
  elements.featureTitle.textContent = properties.title;
  elements.featurePlace.textContent = properties.place || "Platsangivelse saknas";
  elements.featureTime.textContent = timeText(properties.time_span);
  elements.featureDescription.textContent = properties.description || "Beskrivning saknas.";
  elements.geometryConfidence.textContent = confidenceText(properties.geometry_confidence);
  elements.featureConfidence.textContent = confidenceText(properties.confidence);

  const source = properties.source;
  safeExternalLink(elements.featureSource, `${source.name} (${source.id})`, source.url);

  const license = properties.license;
  if (license) {
    safeExternalLink(elements.featureLicense, license.name, license.url);
  } else {
    elements.featureLicense.textContent = "Licensuppgift saknas";
  }

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
  if (focus) focusFeature(feature);
  elements.infoPanel.scrollTop = 0;
}

function showPopup(feature, coordinates) {
  if (state.popup) state.popup.remove();
  const content = document.createElement("div");
  const title = document.createElement("strong");
  title.className = "popup-title";
  title.textContent = feature.properties.title;
  const type = document.createElement("span");
  type.textContent = feature.properties.feature_type;
  const button = document.createElement("button");
  button.className = "popup-button";
  button.type = "button";
  button.textContent = "Visa information";
  button.addEventListener("click", () => showFeature(feature));
  content.append(title, type, button);
  state.popup = new maplibregl.Popup({ closeButton: true })
    .setLngLat(coordinates)
    .setDOMContent(content)
    .addTo(state.map);
}

function selectFeature(feature, { focus = true, popup = false, coordinates = null } = {}) {
  showFeature(feature, { focus });
  if (popup && coordinates) showPopup(feature, coordinates);
  closeSearch();
}

function closePanel() {
  elements.featureContent.hidden = true;
  elements.closePanel.hidden = true;
  elements.welcome.hidden = false;
  if (state.popup) state.popup.remove();
  if (state.selectedId !== null && state.map) {
    state.map.setFeatureState(
      { source: "atlas-features", id: state.selectedId },
      { selected: false },
    );
  }
  state.selectedId = null;
}

function closeSearch() {
  elements.searchResults.hidden = true;
  elements.searchInput.setAttribute("aria-expanded", "false");
}

function renderSearchResults() {
  const terms = elements.searchInput.value.trim().toLocaleLowerCase("sv-SE").split(/\s+/).filter(Boolean);
  elements.searchResults.replaceChildren();
  if (!terms.length) {
    closeSearch();
    return;
  }
  const matches = state.collection.features.filter((feature) => {
    const properties = feature.properties;
    const text = [properties.title, properties.place, properties.feature_type, properties.description]
      .filter(Boolean)
      .join(" ")
      .toLocaleLowerCase("sv-SE");
    return terms.every((term) => text.includes(term));
  }).slice(0, 20);

  if (!matches.length) {
    const empty = document.createElement("p");
    empty.className = "search-empty";
    empty.textContent = "Ingen plats hittades i den lokala atlasen.";
    elements.searchResults.append(empty);
  } else {
    matches.forEach((feature) => {
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

function installFeatureLayers() {
  state.map.addSource("atlas-features", {
    type: "geojson",
    data: state.collection,
    promoteId: "feature_id",
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
    filter: ["==", ["geometry-type"], "Point"],
    paint: {
      "circle-radius": ["case", ["boolean", ["feature-state", "selected"], false], 10, 7],
      "circle-color": ["case", ["boolean", ["feature-state", "selected"], false], "#b45309", "#174d35"],
      "circle-stroke-color": "#fffdf8",
      "circle-stroke-width": 2,
    },
  });

  ["atlas-polygons", "atlas-lines", "atlas-points"].forEach((layerId) => {
    state.map.on("mouseenter", layerId, () => { state.map.getCanvas().style.cursor = "pointer"; });
    state.map.on("mouseleave", layerId, () => { state.map.getCanvas().style.cursor = ""; });
    state.map.on("click", layerId, (event) => {
      const rendered = event.features && event.features[0];
      const feature = rendered ? findFeature(rendered.id) : null;
      if (feature) selectFeature(feature, { focus: false, popup: true, coordinates: event.lngLat });
    });
  });
}

async function initialize() {
  Object.assign(elements, {
    searchInput: byId("feature-search"), searchResults: byId("search-results"),
    mapStatus: byId("map-status"), infoPanel: byId("info-panel"),
    welcome: byId("welcome-content"), featureContent: byId("feature-content"),
    closePanel: byId("close-panel"), featureType: byId("feature-type"),
    featureTitle: byId("feature-title"), featurePlace: byId("feature-place"),
    featureTime: byId("feature-time"), featureDescription: byId("feature-description"),
    geometryConfidence: byId("geometry-confidence"), featureConfidence: byId("feature-confidence"),
    featureSource: byId("feature-source"), featureLicense: byId("feature-license"),
    navigationNote: byId("navigation-note"), navigateButton: byId("navigate-button"),
  });
  elements.searchInput.addEventListener("input", renderSearchResults);
  elements.searchInput.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeSearch();
    if (event.key === "Enter") {
      const first = elements.searchResults.querySelector(".search-result");
      if (first) first.click();
    }
  });
  elements.closePanel.addEventListener("click", closePanel);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") { closeSearch(); if (!elements.featureContent.hidden) closePanel(); }
  });

  try {
    const response = await fetch("/api/features", { headers: { Accept: "application/geo+json" } });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.collection = await response.json();
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
    state.map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-left");
    state.map.addControl(new maplibregl.AttributionControl({ compact: false }), "bottom-right");
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
