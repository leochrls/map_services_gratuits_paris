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

  const serviceLayers = new Map();
  const SERVICE_ICONS = {
    defibrillateurs: { color: "#d62828", emoji: "❤️" },
    fontaines: { color: "#588157", emoji: "💧" },
    toilettes: { color: "#1d3557", emoji: "🚻" },
    wifi: { color: "#f4a261", emoji: "📶" },
  };

  let userMarker = null;
  let userRadius = null;

  function updateStatus(message) {
    if (mapStatus) {
      mapStatus.textContent = message || "";
    }
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
    const extra =
      props.distance_m !== undefined ? `<div><em>Distance: ${props.distance_m.toLocaleString()} m</em></div>` : "";
    const title = `<h4>${props.service_type ? props.service_type.toUpperCase() : "Service"}</h4>`;
    return `${title}${rows}${extra}`;
  }

  function createServiceIcon(serviceType) {
    const config = SERVICE_ICONS[serviceType] || { color: "#3a3a3a", emoji: "•" };
    const className = `service-marker service-${serviceType}`;
    return L.divIcon({
      className: "",
      html: `<div class="${className}" style="--marker-color:${config.color}">
                <span>${config.emoji}</span>
             </div>`,
      iconSize: [34, 40],
      iconAnchor: [17, 34],
      popupAnchor: [0, -28],
    });
  }

  function createLayer(features, serviceType) {
    const markerIcon = createServiceIcon(serviceType);
    return L.geoJSON(features, {
      pointToLayer: function (feature, latlng) {
        return L.marker(latlng, { icon: markerIcon });
      },
      onEachFeature: function (feature, layer) {
        layer.bindPopup(buildPopup(feature));
      },
    });
  }

  async function loadServiceLayer(serviceType) {
    if (serviceLayers.has(serviceType)) {
      const existing = serviceLayers.get(serviceType);
      if (!map.hasLayer(existing)) {
        existing.addTo(map);
      }
      return;
    }
    updateStatus(`Chargement des ${serviceType}...`);
    try {
      const response = await fetch(`/api/services?type=${encodeURIComponent(serviceType)}`);
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.error || "Erreur inconnue");
      }
      const layer = createLayer(payload.features || [], serviceType);
      layer.addTo(map);
      serviceLayers.set(serviceType, layer);
      updateStatus("");
    } catch (error) {
      console.error(error);
      updateStatus(`Impossible de charger ${serviceType}.`);
    }
  }

  function hideServiceLayer(serviceType) {
    const layer = serviceLayers.get(serviceType);
    if (layer && map.hasLayer(layer)) {
      map.removeLayer(layer);
    }
  }

  function refreshFilters() {
    filterInputs.forEach((input) => {
      if (input.checked) {
        loadServiceLayer(input.value);
      } else {
        hideServiceLayer(input.value);
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
    const url = `https://nominatim.openstreetmap.org/search?${params.toString()}`;
    try {
      const response = await fetch(url, {
        headers: { "Accept-Language": "fr", "User-Agent": "paris-services-app" },
      });
      const data = await response.json();
      if (!data || data.length === 0) {
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
    if (userMarker) {
      userMarker.setLatLng(position);
    } else {
      userMarker = L.marker(position, { title: "Votre adresse" }).addTo(map);
    }

    if (userRadius) {
      userRadius.setLatLng(position);
    } else {
      userRadius = L.circle(position, { radius: 400, color: "#4361ee", fillOpacity: 0.1 }).addTo(map);
    }
    map.setView(position, 15);
  }

  function renderNearby(features) {
    if (!Array.isArray(features) || features.length === 0) {
      nearbyList.innerHTML = "<li>Aucun service proche trouvé.</li>";
      return;
    }
    nearbyList.innerHTML = features
      .map((feature) => {
        const props = feature.properties || {};
        return `<li>
            <strong>${props.service_type || "Service"}</strong>
            <div>${props.nom || props.name || props.adresse || "Adresse inconnue"}</div>
            ${
              props.distance_m
                ? `<div class="distance">${props.distance_m.toLocaleString()} m</div>`
                : ""
            }
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
      if (!response.ok) {
        throw new Error(payload.error || "Impossible de récupérer les services.");
      }
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
    if (!address) {
      return;
    }
    const position = await geocodeAddress(address);
    if (!position) {
      return;
    }
    placeUserMarker(position);
    fetchNearby(position);
  });

  // Initial load
  serviceTypes.forEach((service) => {
    const input = Array.from(filterInputs).find((element) => element.value === service);
    if (!input || input.checked) {
      loadServiceLayer(service);
    }
  });
})();
