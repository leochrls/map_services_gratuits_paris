(function () {
  const config = window.APP_CONFIG || {};
  const defaultCenter = config.defaultCenter || { lat: 48.8566, lng: 2.3522, zoom: 12 };
  const serviceTypes = config.serviceTypes || [];

  const map = L.map("map").setView([defaultCenter.lat, defaultCenter.lng], defaultCenter.zoom);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors",
    maxZoom: 19,
  }).addTo(map);

  const mapStatus = document.getElementById("mapStatus");
  const nearbyList = document.getElementById("nearbyList");
  const addressForm = document.getElementById("addressForm");
  const addressInput = document.getElementById("addressInput");
  const filterInputs = document.querySelectorAll("input[name='serviceFilters']");

  // Stockage des couches actives
  const serviceLayers = new Map();
  const pendingRequests = new Map();

  const SERVICE_ICONS = {
    defibrillateurs: { color: "#d62828", emoji: "❤️" },
    fontaines: { color: "#588157", emoji: "💧" },
    toilettes: { color: "#1d3557", emoji: "🚻" },
    wifi: { color: "#f4a261", emoji: "📶" },
  };

  let userMarker = null;
  let userRadius = null;
  let currentBBox = null;
  let mapIsReady = false;

  function updateStatus(message) {
    if (mapStatus) mapStatus.textContent = message || "";
  }

  function formatPropertyName(label) {
    return label.replace(/_/g, " ");
  }

  function buildPopup(feature) {
    if (!feature || !feature.properties) {
      return "<p>Données indisponibles</p>";
    }
    const props = feature.properties;

    const rows = Object.entries(props)
      .filter(([key]) => !["service_type", "distance_m"].includes(key))
      .map(([key, value]) => `<div><strong>${formatPropertyName(key)}:</strong> ${value ?? "-"}</div>`)
      .join("");

    const extra = props.distance_m
      ? `<div><em>Distance: ${props.distance_m.toLocaleString()} m</em></div>`
      : "";

    const title = `<h4>${props.service_type ? props.service_type.toUpperCase() : "Service"}</h4>`;
    return `${title}${rows}${extra}`;
  }

  function createServiceIcon(serviceType) {
    const config = SERVICE_ICONS[serviceType] || { color: "#3a3a3a", emoji: "•" };
    return L.divIcon({
      className: "",
      html: `<div class="service-marker service-${serviceType}" style="--marker-color:${config.color}">
                <span>${config.emoji}</span>
             </div>`,
      iconSize: [34, 40],
      iconAnchor: [17, 34],
      popupAnchor: [0, -28],
    });
  }

  // Création d'une couche clusterisée
  function createLayer(features, serviceType) {
    const markerIcon = createServiceIcon(serviceType);

    const geoJsonLayer = L.geoJSON(features, {
      pointToLayer: function (feature, latlng) {
        return L.marker(latlng, { icon: markerIcon });
      },
      onEachFeature: function (feature, layer) {
        layer.bindPopup(buildPopup(feature));
      },
    });

    const clusterGroup = L.markerClusterGroup({
      showCoverageOnHover: false,
      spiderfyOnMaxZoom: true,
      maxClusterRadius: 50,
    });

    clusterGroup.addLayer(geoJsonLayer);
    return clusterGroup;
  }

  function findFilterInput(serviceType) {
    return Array.from(filterInputs).find((input) => input.value === serviceType);
  }

  function isServiceActive(serviceType) {
    const input = findFilterInput(serviceType);
    return !input || input.checked;
  }

  function getActiveServiceTypes() {
    const checkedValues = new Set(
      Array.from(filterInputs)
        .filter((input) => input.checked)
        .map((input) => input.value)
    );
    return serviceTypes.filter((service) => {
      const input = findFilterInput(service);
      if (!input) {
        return true;
      }
      return checkedValues.has(service);
    });
  }

  function formatBounds(bounds) {
    if (!bounds) {
      return null;
    }
    const south = bounds.getSouth();
    const west = bounds.getWest();
    const north = bounds.getNorth();
    const east = bounds.getEast();
    return [south, west, north, east].map((value) => value.toFixed(6)).join(",");
  }

  function updateCurrentBBox() {
    if (!map) {
      return false;
    }
    const formatted = formatBounds(map.getBounds());
    if (!formatted) {
      return false;
    }
    if (formatted !== currentBBox) {
      currentBBox = formatted;
      return true;
    }
    return false;
  }

  function reloadActiveServiceLayers() {
    getActiveServiceTypes().forEach((service) => {
      loadServiceLayer(service, { forceReload: true });
    });
  }

  async function loadServiceLayer(serviceType, options = {}) {
    const { forceReload = false } = options;
    if (!mapIsReady) {
      return;
    }

    const existingLayer = serviceLayers.get(serviceType);
    if (existingLayer && !forceReload) {
      if (!map.hasLayer(existingLayer)) {
        existingLayer.addTo(map);
      }
      return;
    }

    if (!currentBBox) {
      updateCurrentBBox();
    }
    if (!currentBBox) {
      return;
    }

    const requestToken = Symbol(serviceType);
    pendingRequests.set(serviceType, requestToken);
    updateStatus(`Chargement des ${serviceType}...`);

    try {
      const params = new URLSearchParams({
        type: serviceType,
        bbox: currentBBox,
      });

      const response = await fetch(`/api/services?${params.toString()}`);
      const payload = await response.json();

      if (!response.ok) {
        throw new Error(payload.error || "Erreur inconnue");
      }

      if (pendingRequests.get(serviceType) !== requestToken) {
        return;
      }

      if (!isServiceActive(serviceType)) {
        return;
      }

      const layer = createLayer(payload.features || [], serviceType);
      layer.addTo(map);

      if (existingLayer && map.hasLayer(existingLayer)) {
        map.removeLayer(existingLayer);
      }
      serviceLayers.set(serviceType, layer);

      updateStatus("");
    } catch (error) {
      console.error(error);
      if (pendingRequests.get(serviceType) === requestToken) {
        updateStatus(`Impossible de charger ${serviceType}.`);
      }
    } finally {
      if (pendingRequests.get(serviceType) === requestToken) {
        pendingRequests.delete(serviceType);
      }
    }
  }

  function hideServiceLayer(serviceType) {
    const layer = serviceLayers.get(serviceType);
    if (layer) {
      map.removeLayer(layer);
      serviceLayers.delete(serviceType);
    }
    pendingRequests.delete(serviceType);
  }

  function refreshFilters() {
    const activeServices = new Set(getActiveServiceTypes());
    serviceTypes.forEach((service) => {
      if (activeServices.has(service)) {
        loadServiceLayer(service);
      } else {
        hideServiceLayer(service);
      }
    });
  }

  filterInputs.forEach((input) => {
    input.addEventListener("change", refreshFilters);
  });

  async function geocodeAddress(address) {
    updateStatus(`Recherche de "${address}"...`);
    const params = new URLSearchParams({
      q: `Paris ${address}`,
      format: "json",
      limit: "1",
    });

    try {
      const response = await fetch(`https://nominatim.openstreetmap.org/search?${params.toString()}`, {
        headers: { "Accept-Language": "fr", "User-Agent": "paris-services-app" },
      });

      const data = await response.json();
      if (!data.length) {
        updateStatus("Adresse introuvable.");
        return null;
      }

      updateStatus("");
      return { lat: parseFloat(data[0].lat), lng: parseFloat(data[0].lon) };

    } catch (error) {
      console.error(error);
      updateStatus("Erreur lors de la géolocalisation.");
      return null;
    }
  }

  function placeUserMarker(position) {
    if (!userMarker) {
      userMarker = L.marker(position, { title: "Votre adresse" }).addTo(map);
    } else {
      userMarker.setLatLng(position);
    }

    if (!userRadius) {
      userRadius = L.circle(position, { radius: 400, color: "#4361ee", fillOpacity: 0.1 }).addTo(map);
    } else {
      userRadius.setLatLng(position);
    }

    map.setView(position, 15);
  }

  function renderNearby(features) {
    if (!features.length) {
      nearbyList.innerHTML = "<li>Aucun service proche trouvé.</li>";
      return;
    }

    nearbyList.innerHTML = features
      .map((feature) => {
        const props = feature.properties || {};
        return `<li>
          <strong>${props.service_type || "Service"}</strong>
          <div>${props.nom || props.name || props.adresse || "Adresse inconnue"}</div>
          ${props.distance_m ? `<div class="distance">${props.distance_m} m</div>` : ""}
        </li>`;
      })
      .join("");
  }

  async function fetchNearby(position) {
    updateStatus("Recherche des services proches...");

    const params = new URLSearchParams({
      lat: position.lat,
      lng: position.lng,
      limit: "5",
    });

    try {
      const response = await fetch(`/api/nearby?${params.toString()}`);
      const payload = await response.json();

      if (!response.ok) throw new Error(payload.error);

      renderNearby(payload.features || []);
      updateStatus("");

    } catch (error) {
      console.error(error);
      updateStatus("Erreur lors de la récupération des services proches.");
    }
  }

  addressForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const address = addressInput.value.trim();
    if (!address) return;

    const position = await geocodeAddress(address);
    if (!position) return;

    placeUserMarker(position);
    fetchNearby(position);
  });

  map.whenReady(() => {
    mapIsReady = true;
    updateCurrentBBox();
    refreshFilters();

    map.on("moveend", () => {
      if (updateCurrentBBox()) {
        reloadActiveServiceLayers();
      }
    });
  });
})();
