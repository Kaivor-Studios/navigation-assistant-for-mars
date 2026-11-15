/* Marswalk — planetary field atlas.
   Map imagery is served by NASA/JPL Mars Trek WMTS. The default view is the
   Viking MDIM 2.1 global colour mosaic; MOLA and other products are optional.
   Route distance is a spherical Mars surface-distance estimate only. */

(() => {
  "use strict";

  const MARS_A = 3396190;
  const MARS_B = 3376200;
  const MARS_RADIUS_KM = 3389.5;
  const TILE_ROOT = "https://trek.nasa.gov/tiles/Mars/EQ";
  const CAPABILITIES_ROOT = "https://api.nasa.gov/mars-wmts/catalog";
  const $ = (id) => document.getElementById(id);

  const BASE_LAYERS = [
    {
      id: "viking",
      name: "Viking colour mosaic",
      shortName: "Viking colour",
      description: "Global visible-image mosaic · 231 m/px at the equator",
      tileId: "Mars_Viking_MDIM21_ClrMosaic_global_232m",
      maxLevel: 7,
      format: "jpg",
      fallbackUrl: "https://tiles.arcgis.com/tiles/lqRTrQp2HrfnJt8U/arcgis/rest/services/mars_viking_mosaic/MapServer/tile/{z}/{y}/{x}",
      swatch: "viking",
      attribution: "NASA / JPL / USGS",
      sourceUrl: "https://astrogeology.usgs.gov/search/map/Mars/Viking/MDIM21/Mars_Viking_MDIM21_ClrMosaic_global_232m",
      sourceLabel: "USGS product page"
    },
    {
      id: "mola-colour",
      name: "MOLA colour hillshade",
      shortName: "MOLA colour relief",
      description: "Elevation and shaded relief · global mosaic",
      tileId: "Mars_MGS_MOLA_ClrShade_merge_global_463m",
      maxLevel: 8,
      format: "jpg",
      swatch: "mola",
      attribution: "NASA / JPL · MGS MOLA",
      sourceUrl: "https://pds-geosciences.wustl.edu/missions/mgs/megdr.html",
      sourceLabel: "MOLA PDS archive"
    }
  ];

  // These products are listed by Mars Trek under its equirectangular services.
  // They share the Mars 2000 geographic/equirectangular grid used by the globe.
  const OVERLAY_LAYERS = [
    {
      id: "mola-roughness",
      name: "MOLA surface roughness",
      group: "Terrain",
      description: "Global surface roughness observations",
      tileId: "mola_roughness",
      maxLevel: 8,
      format: "jpg",
      swatch: "roughness",
      sourceUrl: "https://pds-geosciences.wustl.edu/missions/mgs/megdr.html",
      sourceLabel: "MOLA PDS archive"
    },
    {
      id: "moc-atlas",
      name: "MGS MOC atlas mosaic",
      group: "Surface imagery",
      description: "Mars Orbiter Camera global colour mosaic",
      tileId: "msss_atlas_simp_clon",
      maxLevel: 7,
      format: "jpg",
      swatch: "atlas",
      sourceUrl: "https://pds-imaging.jpl.nasa.gov/",
      sourceLabel: "PDS Imaging Node"
    },
    {
      id: "hrsc-colour",
      name: "MOLA + HRSC colour blend",
      group: "Terrain",
      description: "Global colour hillshade blend · MOLA / Mars Express HRSC",
      tileId: "Mars_MOLA_blend200ppx_HRSC_ClrShade_clon0dd_200mpp_lzw",
      maxLevel: 8,
      format: "jpg",
      swatch: "hillshade",
      sourceUrl: "https://www.cosmos.esa.int/web/psa/mars-express",
      sourceLabel: "ESA Mars Express archive"
    },
    {
      id: "hrsc-shade",
      name: "MOLA + HRSC hillshade",
      group: "Terrain",
      description: "Global shaded-relief blend · MOLA / Mars Express HRSC",
      tileId: "Mars_MOLA_blend200ppx_HRSC_Shade_clon0dd_200mpp_lzw",
      maxLevel: 8,
      format: "jpg",
      swatch: "hillshade",
      sourceUrl: "https://www.cosmos.esa.int/web/psa/mars-express",
      sourceLabel: "ESA Mars Express archive"
    }
  ];

  const DATA_SOURCES = [
    {
      title: "Mars Trek map services",
      description: "NASA/JPL's browsable map catalogue, including WMTS layer capabilities, service metadata and previews.",
      links: [
        { label: "Browse Mars layers", url: "https://trek.nasa.gov/tiles/apidoc/trekAPI.html?body=mars" },
        { label: "Viking WMTS capabilities", url: `${CAPABILITIES_ROOT}/Mars_Viking_MDIM21_ClrMosaic_global_232m/1.0.0/WMTSCapabilities.xml` },
        { label: "MOLA WMTS capabilities", url: `${CAPABILITIES_ROOT}/Mars_MGS_MOLA_ClrShade_merge_global_463m/1.0.0/WMTSCapabilities.xml` }
      ]
    },
    {
      title: "Viking MDIM 2.1 global colour mosaic",
      description: "231 m/pixel global mosaic assembled from Viking colour imagery and the USGS MDIM 2.1 basemap.",
      links: [
        { label: "USGS product page", url: "https://astrogeology.usgs.gov/search/map/Mars/Viking/MDIM21/Mars_Viking_MDIM21_ClrMosaic_global_232m" },
        { label: "ArcGIS map service", url: "https://tiles.arcgis.com/tiles/lqRTrQp2HrfnJt8U/arcgis/rest/services/mars_viking_mosaic/MapServer" },
        { label: "NASA/JPL tile service", url: `${TILE_ROOT}/Mars_Viking_MDIM21_ClrMosaic_global_232m/1.0.0/default/default028mm/0/0/0.jpg` }
      ]
    },
    {
      title: "MOLA elevation data",
      description: "Mars Orbiter Laser Altimeter gridded elevation data. Source products are archived separately from the map tiles.",
      links: [
        { label: "PDS MOLA archive", url: "https://pds-geosciences.wustl.edu/missions/mgs/megdr.html" },
        { label: "MOLA tile capabilities", url: `${CAPABILITIES_ROOT}/Mars_MGS_MOLA_ClrShade_merge_global_463m/1.0.0/WMTSCapabilities.xml` }
      ]
    },
    {
      title: "USGS global geologic map",
      description: "Standardized global geological map of Mars. The source map is a separate GIS product, not an imagery overlay in this build.",
      links: [
        { label: "USGS map and downloads", url: "https://www.usgs.gov/maps/geologic-map-mars" },
        { label: "USGS Astrogeology", url: "https://astrogeology.usgs.gov/" }
      ]
    },
    {
      title: "THEMIS infrared observations",
      description: "Thermal Emission Imaging System observations. Several products use polar or regional map projections and are not forced onto the equirectangular globe as if they were compatible.",
      links: [
        { label: "THEMIS data portal", url: "https://themis.asu.edu/" },
        { label: "Mars Trek service catalogue", url: "https://trek.nasa.gov/tiles/apidoc/trekAPI.html?body=mars" }
      ]
    },
    {
      title: "HiRISE and rover imagery",
      description: "High-resolution regional images and rover raw images, with their own footprint and location metadata.",
      links: [
        { label: "HiRISE image archive", url: "https://hirise.lpl.arizona.edu/" },
        { label: "Perseverance raw images", url: "https://mars.nasa.gov/mars2020/multimedia/raw-images/" },
        { label: "Curiosity raw images", url: "https://mars.nasa.gov/msl/multimedia/raw/" }
      ]
    }
  ];

  const places = {
    gale: { name: "Gale Crater", lat: -5.4, lon: 137.8, detail: "Curiosity exploration region", note: "Gale Crater is the exploration region of NASA's Curiosity rover. This marker is a regional reference, not a live rover position.", height: 780000 },
    jezero: { name: "Jezero Crater", lat: 18.4, lon: 77.7, detail: "Perseverance exploration region", note: "Jezero Crater is the exploration region of NASA's Perseverance rover. This marker is a regional reference, not a live rover position.", height: 470000 },
    olympus: { name: "Olympus Mons", lat: 18.7, lon: -133.8, detail: "Shield volcano", note: "Olympus Mons is a major Martian shield volcano. The marker indicates the named feature's approximate location.", height: 850000 },
    valles: { name: "Valles Marineris", lat: -13.9, lon: -59.2, detail: "Canyon system", note: "Valles Marineris is an extensive canyon system near the Martian equator.", height: 1100000 },
    eberswalde: { name: "Eberswalde Crater", lat: -23.9, lon: 326.8, detail: "Ancient delta deposit", note: "Eberswalde contains a well-preserved ancient delta deposit. Longitude is normalized to east-positive values.", height: 600000 }
  };

  let CesiumLib = null;
  let MARS = null;
  let viewer = null;
  let baseLayer = null;
  let baseLayerId = "viking";
  let overlays = new Map();
  let customLayers = [];
  let clickHandler = null;
  let selectedPoint = null;
  let routePoints = [];
  let routeEntities = [];
  let siteEntities = [];
  let routeModeActive = false;
  let sitesVisible = true;
  let baseTileErrors = 0;
  let usingFallbackBasemap = false;

  const ui = {
    loading: $("map-loading"), error: $("map-error"), errorTitle: $("map-error-title"), errorMessage: $("map-error-message"), errorDetail: $("map-error-detail"),
    connectionDot: $("connection-dot"), connectionLabel: $("connection-label"), region: $("region-label"), coordinate: $("coordinate-readout"),
    inspector: $("inspector-panel"), inspectorTitle: $("inspector-title"), inspectorNote: $("inspector-note"), selectedCoordinates: $("selected-coordinates"), selectedLat: $("selected-lat"), selectedLon: $("selected-lon"),
    routePanel: $("route-panel"), routeMode: $("route-mode"), routeInstruction: $("route-instruction"), routeDistance: $("route-distance"), routePoints: $("route-points"), waypointList: $("waypoint-list"), exportRoute: $("export-route")
  };

  function setConnectionState(state, message) {
    ui.connectionDot.classList.remove("live", "error");
    if (state === "live") {
      ui.connectionDot.classList.add("live");
      ui.connectionLabel.textContent = message || "NASA / JPL imagery connected";
    } else if (state === "error") {
      ui.connectionDot.classList.add("error");
      ui.connectionLabel.textContent = message || "Map service unavailable";
    } else {
      ui.connectionLabel.textContent = message || "Connecting to Mars Trek";
    }
  }

  function showMapError(title, message, detail = "") {
    ui.loading.classList.add("hidden");
    ui.errorTitle.textContent = title;
    ui.errorMessage.textContent = message;
    ui.errorDetail.textContent = detail;
    ui.errorDetail.classList.toggle("hidden", !detail);
    ui.error.classList.remove("hidden");
    setConnectionState("error", "Map unavailable");
  }

  function hideMapError() { ui.error.classList.add("hidden"); }

  function seededRandom(seed) {
    let value = seed >>> 0;
    return () => {
      value = (value * 1664525 + 1013904223) >>> 0;
      return value / 4294967296;
    };
  }

  // Generate a small, local six-face star cube. A shared 3D point distribution
  // is projected onto the six faces, so the sky is present in every direction.
  function createStarSkyBox(C) {
    const size = 768;
    const faces = {
      positiveX: document.createElement("canvas"), negativeX: document.createElement("canvas"),
      positiveY: document.createElement("canvas"), negativeY: document.createElement("canvas"),
      positiveZ: document.createElement("canvas"), negativeZ: document.createElement("canvas")
    };
    const contexts = {};
    Object.entries(faces).forEach(([name, canvas]) => {
      canvas.width = size;
      canvas.height = size;
      const ctx = canvas.getContext("2d");
      ctx.fillStyle = "#03070b";
      ctx.fillRect(0, 0, size, size);
      contexts[name] = ctx;
    });

    const rand = seededRandom(739102);
    const count = 7200;
    for (let i = 0; i < count; i += 1) {
      const z = rand() * 2 - 1;
      const theta = rand() * Math.PI * 2;
      const radius = Math.sqrt(1 - z * z);
      const x = radius * Math.cos(theta);
      const y = radius * Math.sin(theta);
      const ax = Math.abs(x), ay = Math.abs(y), az = Math.abs(z);
      let face, u, v, dominant;
      if (ax >= ay && ax >= az) {
        dominant = ax;
        if (x > 0) { face = "positiveX"; u = -z / dominant; v = -y / dominant; }
        else { face = "negativeX"; u = z / dominant; v = -y / dominant; }
      } else if (ay >= ax && ay >= az) {
        dominant = ay;
        if (y > 0) { face = "positiveY"; u = x / dominant; v = z / dominant; }
        else { face = "negativeY"; u = x / dominant; v = -z / dominant; }
      } else {
        dominant = az;
        if (z > 0) { face = "positiveZ"; u = x / dominant; v = -y / dominant; }
        else { face = "negativeZ"; u = -x / dominant; v = -y / dominant; }
      }
      const px = (u + 1) * .5 * size;
      const py = (v + 1) * .5 * size;
      const magnitude = rand();
      const r = magnitude > .994 ? 1.75 : magnitude > .95 ? 1.15 : .55 + rand() * .45;
      const alpha = magnitude > .994 ? .95 : magnitude > .95 ? .7 : .22 + rand() * .25;
      const tint = rand();
      const color = tint > .93 ? `rgba(194,211,238,${alpha})` : tint < .04 ? `rgba(241,211,178,${alpha})` : `rgba(235,239,242,${alpha})`;
      const ctx = contexts[face];
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(px, py, r, 0, Math.PI * 2);
      ctx.fill();
      if (r > 1.5) {
        ctx.strokeStyle = `rgba(235,239,242,${alpha * .28})`;
        ctx.lineWidth = .45;
        ctx.beginPath();
        ctx.moveTo(px - 3.8, py); ctx.lineTo(px + 3.8, py);
        ctx.moveTo(px, py - 3.8); ctx.lineTo(px, py + 3.8);
        ctx.stroke();
      }
    }

    const sources = {};
    Object.entries(faces).forEach(([name, canvas]) => { sources[name] = canvas.toDataURL("image/png"); });
    return new C.SkyBox({ sources });
  }

  function getTileUrl(layer, useFallback = false) {
    if (useFallback && layer.fallbackUrl) return layer.fallbackUrl;
    if (layer.customUrl) return layer.customUrl;
    return `${TILE_ROOT}/${layer.tileId}/1.0.0/default/default028mm/{z}/{y}/{x}.${layer.format || "jpg"}`;
  }

  function createMarsProvider(layer, useFallback = false) {
    const tilingScheme = new CesiumLib.GeographicTilingScheme({ ellipsoid: MARS });
    return new CesiumLib.UrlTemplateImageryProvider({
      url: getTileUrl(layer, useFallback),
      tilingScheme,
      minimumLevel: 0,
      maximumLevel: Number(layer.maxLevel || 8),
      rectangle: CesiumLib.Rectangle.fromDegrees(-180, -89.999, 180, 89.999),
      credit: new CesiumLib.Credit(layer.attribution || `NASA / JPL · ${layer.name}`),
      tileWidth: 256,
      tileHeight: 256
    });
  }

  function createMarsViewer() {
    MARS = new CesiumLib.Ellipsoid(MARS_A, MARS_A, MARS_B);
    viewer = new CesiumLib.Viewer("cesiumContainer", {
      animation: false,
      timeline: false,
      baseLayerPicker: false,
      geocoder: false,
      homeButton: false,
      sceneModePicker: false,
      navigationHelpButton: false,
      fullscreenButton: false,
      infoBox: false,
      selectionIndicator: false,
      shouldAnimate: false,
      skyBox: false,
      skyAtmosphere: false,
      baseLayer: false,
      scene3DOnly: true,
      requestRenderMode: false,
      contextOptions: { webgl: { alpha: false, antialias: true, powerPreference: "high-performance", preserveDrawingBuffer: true } },
      globe: new CesiumLib.Globe(MARS)
    });

    const scene = viewer.scene;
    scene.logarithmicDepthBuffer = true;
    scene.backgroundColor = CesiumLib.Color.fromCssColorString("#02060b");
    scene.skyBox = createStarSkyBox(CesiumLib);
    scene.skyBox.show = true;
    scene.globe.baseColor = CesiumLib.Color.fromCssColorString("#9a7b60");
    scene.globe.enableLighting = true;
    scene.globe.showGroundAtmosphere = true;
    scene.globe.showWaterEffect = false;
    scene.globe.depthTestAgainstTerrain = false;

scene.globe.maximumScreenSpaceError = 3.0;

scene.skyAtmosphere = new CesiumLib.SkyAtmosphere(MARS);
scene.skyAtmosphere.hueShift = 0.0;
scene.skyAtmosphere.saturationShift = 0.0;
scene.skyAtmosphere.brightnessShift = 0.0;

if (scene.sun) scene.sun.show = false;
if (scene.moon) scene.moon.show = false;

scene.fog.enabled = false;


const controls = scene.screenSpaceCameraController;

// Native camera controls
controls.enableZoom = true;
controls.enableRotate = true;
controls.enableTilt = true;
controls.enableTranslate = true;

// Use Cesium's built-in wheel and pinch support
controls.zoomEventTypes = [
    CesiumLib.CameraEventType.WHEEL,
    CesiumLib.CameraEventType.PINCH
];

// Moderate zoom speed
controls.zoomFactor = 5.0;

// Reduce excessive camera momentum
controls.inertiaZoom = 0.65;
controls.inertiaSpin = 0.84;
controls.inertiaTranslate = 0.84;

// Enable collision protection
controls.enableCollisionDetection = true;

// Prevent extreme close-ups for now
controls.minimumZoomDistance = 12000;
controls.maximumZoomDistance = 50000000;

// Keep camera movement controlled
controls.maximumMovementRatio = 0.05;

// Do not let camera tilt underneath the globe
controls.maximumTiltAngle = Math.PI / 2;

// Improve planetary depth precision
scene.logarithmicDepthBuffer = true;

scene.globe.maximumScreenSpaceError = 2.0;

viewer.resolutionScale = 1.0;

    addBaseLayer("viking");
    addMissionSites();
    installMapInteractions();
    // Real MOLA terrain from the NAM backend (custom heightmap provider).
    // Falls back to flat ellipsoid tiles if the backend is offline.
    try {
      scene.globe.terrainProvider = NAM.createMolaTerrainProvider();
    } catch (error) { console.warn("MOLA terrain unavailable:", error); }
    viewer.camera.moveEnd.addEventListener(updateCoordinateHint);
    viewer.camera.setView({
      destination: CesiumLib.Cartesian3.fromDegrees(18, 14, 7400000, MARS),
      orientation: { heading: CesiumLib.Math.toRadians(-12), pitch: CesiumLib.Math.toRadians(-82), roll: 0 }
    });
    installTrackpadPinchZoom();
    updateCoordinateHint();
    probeBaseLayer();
    // The globe is live — retire the loading badge so it never blocks clicks.
    ui.loading.classList.add("hidden");
  }
// Laptop trackpad pinch-to-zoom
function installTrackpadPinchZoom() {
    const canvas = viewer.canvas;

    let queuedDeltaY = 0;
    let frameRequested = false;

    function applyZoom() {
        frameRequested = false;

        if (!viewer || viewer.isDestroyed()) {
            queuedDeltaY = 0;
            return;
        }

        const deltaY = queuedDeltaY;
        queuedDeltaY = 0;

        if (Math.abs(deltaY) < 0.01) return;

        const camera = viewer.camera;
        const currentHeight = camera.positionCartographic.height;

        // Controls how much each pinch movement zooms.
        const scale = Math.exp(deltaY * 0.0024);

        const nextHeight = CesiumLib.Math.clamp(
            currentHeight * scale,
            1000,
            50000000
        );

        const distance = Math.abs(nextHeight - currentHeight);

        if (distance < 0.5) return;

        if (nextHeight < currentHeight) {
            camera.zoomIn(distance);
        } else {
            camera.zoomOut(distance);
        }
    }

    window.addEventListener("wheel", (event) => {

        // Only intercept trackpad-style pinch zoom.
        if (event.target !== canvas) return;

        if (!event.ctrlKey && !event.metaKey) return;

        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();

        const unit =
            event.deltaMode === 1 ? 16 :
            event.deltaMode === 2 ? window.innerHeight : 1;

        queuedDeltaY += event.deltaY * unit;

        if (!frameRequested) {
            frameRequested = true;
            window.requestAnimationFrame(applyZoom);
        }

    }, {
        capture: true,
        passive: false
    });
}
  function probeBaseLayer(useFallback = usingFallbackBasemap) {
    const layer = BASE_LAYERS.find((item) => item.id === baseLayerId);
    const image = new Image();
    image.crossOrigin = "anonymous";
    image.onload = () => {
      ui.loading.classList.add("hidden");
      hideMapError();
      setConnectionState("live", useFallback ? "Viking mosaic connected · Esri cache" : "NASA / JPL imagery connected");
    };
    image.onerror = () => {
      if (!useFallback && layer.fallbackUrl) {
        addBaseLayer(layer.id, true);
        setConnectionState("loading", "Trying alternate Viking mosaic service");
        probeBaseLayer(true);
        return;
      }
      ui.loading.classList.add("hidden");
      setConnectionState("error", "Viking mosaic service did not respond");
      ui.coordinate.textContent = "Surface imagery unavailable · check the data catalogue";
    };
    image.src = useFallback ? getTileUrl(layer, true).replace("{z}", "0").replace("{y}", "0").replace("{x}", "0") : `${TILE_ROOT}/${layer.tileId}/1.0.0/default/default028mm/0/0/0.${layer.format}`;
  }

  function addBaseLayer(id, useFallback = false) {
    const layer = BASE_LAYERS.find((item) => item.id === id);
    if (!layer || !viewer) return;
    const provider = createMarsProvider(layer, useFallback);
    if (baseLayer) viewer.imageryLayers.remove(baseLayer, true);
    baseLayer = viewer.imageryLayers.addImageryProvider(provider, 0);
    baseLayer.alpha = 1;
    baseLayerId = id;
    usingFallbackBasemap = useFallback;
    const credit = $("map-credit");
    credit.textContent = useFallback ? `${layer.name} · USGS / Esri cached tiles` : `${layer.name} · ${layer.attribution}`;
    $("active-base-label").textContent = layer.shortName;
    renderLayerCatalogue();
    provider.errorEvent.addEventListener((error) => {
      baseTileErrors += 1;
      console.warn(`Marswalk base layer ${layer.name} tile error:`, error);
      if (baseTileErrors >= 4 && !usingFallbackBasemap && layer.fallbackUrl) {
        console.warn("Primary NASA Viking tile service is failing; switching to the same public mosaic through its USGS/Esri cached map service.");
        baseTileErrors = 0;
        addBaseLayer(id, true);
        setConnectionState("loading", "Trying alternate Viking mosaic service");
        probeBaseLayer(true);
      } else if (baseTileErrors >= 4) {
        setConnectionState("error", "Some base map tiles failed");
      }
    });
  }

  function addOverlayLayer(id) {
    const layer = [...OVERLAY_LAYERS, ...customLayers].find((item) => item.id === id);
    if (!layer || !viewer || overlays.has(id)) return;
    const provider = createMarsProvider(layer);
    const imagery = viewer.imageryLayers.addImageryProvider(provider);
    imagery.alpha = .68;
    overlays.set(id, { layer, imagery });
    provider.errorEvent.addEventListener((error) => {
      console.warn(`Marswalk overlay ${layer.name} tile error:`, error);
    });
    renderLayerCatalogue();
  }

  function removeOverlayLayer(id) {
    const item = overlays.get(id);
    if (!item || !viewer) return;
    viewer.imageryLayers.remove(item.imagery, true);
    overlays.delete(id);
    renderLayerCatalogue();
  }

  function layerCapabilitiesUrl(layer) {
    if (!layer.tileId) return null;
    return `${CAPABILITIES_ROOT}/${layer.tileId}/1.0.0/WMTSCapabilities.xml`;
  }

  function renderLayerCatalogue(filter = "") {
    const query = filter.trim().toLowerCase();
    const baseList = $("base-layer-list");
    const overlayList = $("overlay-layer-list");
    baseList.replaceChildren();
    overlayList.replaceChildren();

    BASE_LAYERS.forEach((layer) => {
      const card = document.createElement("div");
      card.className = `base-layer-card${baseLayerId === layer.id ? " is-active" : ""}`;
      const swatch = document.createElement("span");
      swatch.className = `layer-swatch ${layer.swatch}`;
      const copy = document.createElement("span");
      copy.className = "layer-copy";
      const name = document.createElement("strong"); name.textContent = layer.name;
      const desc = document.createElement("small"); desc.textContent = layer.description;
      copy.append(name, desc);
      const sourceLink = document.createElement("a");
      sourceLink.className = "layer-source-link";
      sourceLink.href = layerCapabilitiesUrl(layer) || layer.sourceUrl;
      sourceLink.target = "_blank"; sourceLink.rel = "noreferrer";
      sourceLink.textContent = "WMTS service ↗";
      copy.append(sourceLink);
      if (layer.sourceUrl) {
        const productLink = document.createElement("a");
        productLink.className = "layer-source-link";
        productLink.href = layer.sourceUrl; productLink.target = "_blank"; productLink.rel = "noreferrer";
        productLink.textContent = `${layer.sourceLabel || "Source product"} ↗`;
        copy.append(productLink);
      }
      const action = document.createElement("button");
      action.className = "layer-select";
      action.type = "button";
      action.textContent = baseLayerId === layer.id ? "Selected" : "Use map";
      action.addEventListener("click", () => {
        baseTileErrors = 0;
        addBaseLayer(layer.id);
        setConnectionState("loading", "Loading " + layer.shortName);
        probeBaseLayer(false);
      });
      card.append(swatch, copy, action);
      baseList.append(card);
    });

    const candidates = [...OVERLAY_LAYERS, ...customLayers].filter((layer) => {
      const text = `${layer.name} ${layer.group || ""} ${layer.description}`.toLowerCase();
      return text.includes(query);
    });
    if (!candidates.length) {
      const empty = document.createElement("p");
      empty.className = "layer-empty";
      empty.textContent = "No layers match that search.";
      overlayList.append(empty);
    }

    candidates.forEach((layer) => {
      const active = overlays.has(layer.id);
      const card = document.createElement("div");
      card.className = "overlay-layer-card";
      const swatch = document.createElement("span"); swatch.className = `layer-swatch ${layer.swatch || "mola"}`;
      const copy = document.createElement("span"); copy.className = "layer-copy";
      const name = document.createElement("strong"); name.textContent = layer.name;
      const desc = document.createElement("small"); desc.textContent = `${layer.group || "Custom service"} · ${layer.description}`;
      copy.append(name, desc);
      if (layerCapabilitiesUrl(layer)) {
        const sourceLink = document.createElement("a");
        sourceLink.className = "layer-source-link";
        sourceLink.href = layerCapabilitiesUrl(layer);
        sourceLink.target = "_blank"; sourceLink.rel = "noreferrer";
        sourceLink.textContent = "WMTS service ↗";
        copy.append(sourceLink);
      }
      if (layer.sourceUrl) {
        const productLink = document.createElement("a");
        productLink.className = "layer-source-link";
        productLink.href = layer.sourceUrl; productLink.target = "_blank"; productLink.rel = "noreferrer";
        productLink.textContent = `${layer.sourceLabel || "Source product"} ↗`;
        copy.append(productLink);
      }
      const action = document.createElement("button");
      action.type = "button";
      action.className = "layer-add";
      action.textContent = active ? "Remove" : "Add";
      action.setAttribute("aria-pressed", String(active));
      action.addEventListener("click", () => active ? removeOverlayLayer(layer.id) : addOverlayLayer(layer.id));
      card.append(swatch, copy, action);
      overlayList.append(card);

      if (active) {
        const opacity = document.createElement("label");
        opacity.className = "layer-opacity";
        opacity.innerHTML = `<span>Opacity</span>`;
        const range = document.createElement("input");
        range.type = "range"; range.min = "0"; range.max = "100"; range.value = String(Math.round(overlays.get(layer.id).imagery.alpha * 100));
        range.setAttribute("aria-label", `${layer.name} opacity`);
        range.addEventListener("input", () => { const activeLayer = overlays.get(layer.id); if (activeLayer) activeLayer.imagery.alpha = Number(range.value) / 100; });
        opacity.append(range);
        overlayList.append(opacity);
      }
    });
    $("overlay-count").textContent = `${overlays.size} active`;
  }

  function renderDataSources() {
    const container = $("data-source-list");
    container.replaceChildren();
    DATA_SOURCES.forEach((source) => {
      const card = document.createElement("section"); card.className = "data-source-card";
      const title = document.createElement("h3"); title.textContent = source.title;
      const desc = document.createElement("p"); desc.textContent = source.description;
      const links = document.createElement("div"); links.className = "data-source-links";
      source.links.forEach((item) => {
        const link = document.createElement("a"); link.href = item.url; link.target = "_blank"; link.rel = "noreferrer"; link.textContent = item.label + " ↗";
        links.append(link);
      });
      card.append(title, desc, links);
      container.append(card);
    });
    const note = document.createElement("p");
    note.className = "data-note";
    note.textContent = "Map tiles are streamed for visualisation. A WMTS capabilities document describes the service; it is not the same as downloading the original raster product. Use the archive or product links for source data downloads.";
    container.append(note);
  }

  function renderPlaces() {
    const list = $("place-list");
    list.replaceChildren();
    Object.entries(places).forEach(([id, place]) => {
      const button = document.createElement("button");
      button.type = "button"; button.className = "place-row";
      const marker = document.createElement("span"); marker.className = `place-marker${id === "olympus" ? " volcano" : ""}`;
      const copy = document.createElement("span");
      const name = document.createElement("strong"); name.textContent = place.name;
      const detail = document.createElement("small"); detail.textContent = place.detail;
      copy.append(name, detail);
      const arrow = document.createElement("span"); arrow.className = "place-arrow"; arrow.textContent = "↗";
      button.append(marker, copy, arrow);
      button.addEventListener("click", () => flyToPlace(id));
      list.append(button);
    });
  }

  function addMissionSites() {
    siteEntities = Object.entries(places).map(([id, place]) => viewer.entities.add({
      id: `site-${id}`,
      name: place.name,
      position: CesiumLib.Cartesian3.fromDegrees(normalizeLongitude(place.lon), place.lat, 0, MARS),
      point: {
        pixelSize: 7,
        color: CesiumLib.Color.fromCssColorString("#d29a78"),
        outlineColor: CesiumLib.Color.fromCssColorString("#302c26"),
        outlineWidth: 1.3,
        heightReference: CesiumLib.HeightReference.NONE,
        disableDepthTestDistance: 350000
      },
      label: {
        text: place.name,
        font: "11px Inter, Arial, sans-serif",
        fillColor: CesiumLib.Color.fromCssColorString("#f1eee5"),
        outlineColor: CesiumLib.Color.fromCssColorString("#151817"),
        outlineWidth: 3,
        style: CesiumLib.LabelStyle.FILL_AND_OUTLINE,
        pixelOffset: new CesiumLib.Cartesian2(9, -9),
        distanceDisplayCondition: new CesiumLib.DistanceDisplayCondition(0, 5400000),
        disableDepthTestDistance: 350000
      },
      properties: { placeId: id }
    }));
  }

  function pickCartographic(position) {
    // Terrain-aware picking: ray-pick the terrain surface first (the globe
    // now renders real MOLA elevation), falling back to the ellipsoid.
    try {
      const ray = viewer.camera.getPickRay(position);
      if (ray) {
        const cart = viewer.scene.globe.pick(ray, viewer.scene);
        if (cart) return CesiumLib.Cartographic.fromCartesian(cart, MARS);
      }
    } catch (error) { /* fall through to ellipsoid pick */ }
    const cartesian = viewer.camera.pickEllipsoid(position, MARS);
    if (!cartesian) return null;
    return CesiumLib.Cartographic.fromCartesian(cartesian, MARS);
  }

  function installMapInteractions() {
    clickHandler = new CesiumLib.ScreenSpaceEventHandler(viewer.scene.canvas);
    clickHandler.setInputAction((movement) => {
      const point = pickCartographic(movement.endPosition);
      if (!point) return;
      ui.coordinate.textContent = `${formatLatitude(CesiumLib.Math.toDegrees(point.latitude))}  ·  ${formatLongitude(CesiumLib.Math.toDegrees(point.longitude))}`;
    }, CesiumLib.ScreenSpaceEventType.MOUSE_MOVE);

    clickHandler.setInputAction((movement) => {
      const point = pickCartographic(movement.position);
      if (!point) return;
      const lat = CesiumLib.Math.toDegrees(point.latitude);
      const lon = normalizeLongitude(CesiumLib.Math.toDegrees(point.longitude));
      const picked = viewer.scene.pick(movement.position);
      const siteId = picked && picked.id && picked.id.properties && picked.id.properties.placeId ? picked.id.properties.placeId.getValue() : null;
      if (routeModeActive) addRoutePoint(lat, lon);
      else selectLocation(lat, lon, siteId);
    }, CesiumLib.ScreenSpaceEventType.LEFT_CLICK);

    clickHandler.setInputAction(() => { if (routeModeActive) toggleRouteMode(false); }, CesiumLib.ScreenSpaceEventType.RIGHT_CLICK);
  }

  function selectLocation(lat, lon, siteId = null) {
    selectedPoint = { lat, lon };
    const place = siteId ? places[siteId] : null;
    ui.inspectorTitle.textContent = place ? place.name : "Selected location";
    ui.selectedCoordinates.textContent = `${formatLatitude(lat)}  ·  ${formatLongitude(lon)}`;
    ui.selectedLat.textContent = formatLatitude(lat);
    ui.selectedLon.textContent = formatLongitude(lon);
    ui.inspectorNote.textContent = place ? place.note : "Coordinates selected on the currently visible imagery. No elevation or hazard values are inferred from the image.";
    ui.inspector.classList.remove("hidden");
    namEnrichInspector(lat, lon, siteId);
  }

  function clearSelection() { selectedPoint = null; ui.inspector.classList.add("hidden"); }

  function addRoutePoint(lat, lon) {
    routePoints.push({ lat, lon });
    redrawRoute();
    renderRouteStats();
    ui.routeInstruction.textContent = routePoints.length < 2 ? "Add another point to extend the traverse. Right-click to finish." : "Add more points or right-click to finish.";
  }

  function redrawRoute() {
    routeEntities.forEach((entity) => viewer.entities.remove(entity));
    routeEntities = [];
    if (!routePoints.length) return;
    routePoints.forEach((point, index) => {
      routeEntities.push(viewer.entities.add({
        position: CesiumLib.Cartesian3.fromDegrees(point.lon, point.lat, 100, MARS),
        point: { pixelSize: index === 0 ? 9 : 7, color: index === 0 ? CesiumLib.Color.fromCssColorString("#e1b38e") : CesiumLib.Color.fromCssColorString("#a8c0a9"), outlineColor: CesiumLib.Color.fromCssColorString("#151a17"), outlineWidth: 1.5, disableDepthTestDistance: 350000 },
        label: { text: String(index + 1), font: "10px Inter, Arial, sans-serif", fillColor: CesiumLib.Color.WHITE, outlineColor: CesiumLib.Color.fromCssColorString("#172019"), outlineWidth: 3, style: CesiumLib.LabelStyle.FILL_AND_OUTLINE, pixelOffset: new CesiumLib.Cartesian2(0, -13), disableDepthTestDistance: 350000 }
      }));
    });
    if (routePoints.length > 1) {
      const coordinates = routePoints.flatMap((point) => [point.lon, point.lat, 100]);
      routeEntities.push(viewer.entities.add({ polyline: { positions: CesiumLib.Cartesian3.fromDegreesArrayHeights(coordinates, MARS), width: 2.5, material: new CesiumLib.ColorMaterialProperty(CesiumLib.Color.fromCssColorString("#c3d5bb")), arcType: CesiumLib.ArcType.GEODESIC, clampToGround: false } }));
    }
  }

  function renderRouteStats() {
    const distance = routePoints.slice(1).reduce((sum, point, index) => sum + haversineKm(routePoints[index], point), 0);
    ui.routeDistance.innerHTML = `${distance.toFixed(1)} <small>km</small>`;
    ui.routePoints.textContent = String(routePoints.length);
    ui.exportRoute.disabled = routePoints.length < 2;
    if (!routePoints.length) {
      ui.waypointList.innerHTML = '<span class="empty-waypoints">No waypoints yet</span>';
      return;
    }
    ui.waypointList.replaceChildren();
    routePoints.forEach((point, index) => {
      const row = document.createElement("div"); row.className = "waypoint-item";
      const label = document.createElement("span"); label.textContent = `${index + 1}. ${formatLatitude(point.lat)}, ${formatLongitude(point.lon)}`;
      const remove = document.createElement("button"); remove.type = "button"; remove.textContent = "×"; remove.setAttribute("aria-label", `Remove waypoint ${index + 1}`);
      remove.addEventListener("click", () => { routePoints.splice(index, 1); redrawRoute(); renderRouteStats(); });
      row.append(label, remove); ui.waypointList.append(row);
    });
  }

  function haversineKm(a, b) {
    const radians = Math.PI / 180;
    const lat1 = a.lat * radians, lat2 = b.lat * radians;
    const dLat = (b.lat - a.lat) * radians, dLon = (b.lon - a.lon) * radians;
    const h = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
    return 2 * MARS_RADIUS_KM * Math.asin(Math.min(1, Math.sqrt(h)));
  }

  function toggleRouteMode(force) {
    routeModeActive = typeof force === "boolean" ? force : !routeModeActive;
    ui.routeMode.setAttribute("aria-pressed", String(routeModeActive));
    ui.routePanel.classList.remove("hidden");
    ui.routeInstruction.textContent = routeModeActive ? "Click the surface to add waypoints. Right-click to finish." : (routePoints.length ? "Traverse saved in this session. Continue editing or export it." : "No waypoints yet.");
    if (!routeModeActive && !routePoints.length) ui.routePanel.classList.add("hidden");
  }

  function clearRoute() {
    routePoints = []; redrawRoute(); renderRouteStats(); toggleRouteMode(false); ui.routePanel.classList.add("hidden");
  }

  function exportRouteGeoJSON() {
    if (routePoints.length < 2) return;
    const distance = routePoints.slice(1).reduce((sum, point, index) => sum + haversineKm(routePoints[index], point), 0);
    const feature = { type: "Feature", properties: { name: "Marswalk proposed traverse", body: "Mars", coordinateReference: "Mars 2000 / geodetic latitude, east-positive longitude", distanceKm: Number(distance.toFixed(3)), distanceNote: "Spherical surface-distance estimate; does not account for terrain, slope or obstacles." }, geometry: { type: "LineString", coordinates: routePoints.map((point) => [point.lon, point.lat]) } };
    downloadBlob(new Blob([JSON.stringify(feature, null, 2)], { type: "application/geo+json" }), "marswalk-traverse.geojson");
  }

  function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = filename; document.body.append(anchor); anchor.click(); anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1500);
  }

  function saveMapImage() {
    if (!viewer) return;
    try {
      viewer.render();
      viewer.scene.canvas.toBlob((blob) => {
        if (!blob) { window.alert("The browser could not capture the map. Try again after the globe finishes rendering."); return; }
        downloadBlob(blob, "marswalk-map-view.png");
      }, "image/png");
    } catch (error) {
      console.warn("Map image export failed:", error);
      window.alert("The map image could not be exported in this browser.");
    }
  }

  function flyToPlace(id) {
    const place = places[id];
    if (!place || !viewer) return;
    ui.coordinate.textContent = place.name;
    closePanel("places-panel");
    viewer.camera.flyTo({ destination: CesiumLib.Cartesian3.fromDegrees(normalizeLongitude(place.lon), place.lat, place.height, MARS), orientation: { heading: 0, pitch: CesiumLib.Math.toRadians(-48), roll: 0 }, duration: 2.0, complete: () => selectLocation(place.lat, normalizeLongitude(place.lon), id) });
  }

  function flyHome() {
    if (!viewer) return;
    closeAllPanels(); clearSelection();
    viewer.camera.flyTo({ destination: CesiumLib.Cartesian3.fromDegrees(18, 14, 7400000, MARS), orientation: { heading: CesiumLib.Math.toRadians(-12), pitch: CesiumLib.Math.toRadians(-82), roll: 0 }, duration: 1.8 });
  }

  function normalizeLongitude(lon) { return ((lon + 180) % 360 + 360) % 360 - 180; }
  function formatLatitude(lat) { return `${Math.abs(lat).toFixed(3)}° ${lat >= 0 ? "N" : "S"}`; }
  function formatLongitude(lon) { return `${Math.abs(lon).toFixed(3)}° ${lon >= 0 ? "E" : "W"}`; }

  function updateCoordinateHint() {
    if (!viewer || selectedPoint) return;
    ui.coordinate.textContent = "Mars  ·  move over the surface for coordinates";
  }

  function searchLocation(query) {
    const normalized = query.trim().toLowerCase();
    if (!normalized || !viewer) return;
    const match = Object.entries(places).find(([id, place]) => id.includes(normalized) || place.name.toLowerCase().includes(normalized));
    if (match) { namHideSearchResults(); flyToPlace(match[0]); closePanel("search-panel"); return; }
    const coordinates = normalized.match(/^\s*(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)\s*$/);
    if (coordinates) {
      const lat = Number(coordinates[1]), lon = normalizeLongitude(Number(coordinates[2]));
      if (Math.abs(lat) <= 90) {
        namHideSearchResults();
        closePanel("search-panel");
        viewer.camera.flyTo({ destination: CesiumLib.Cartesian3.fromDegrees(lon, lat, 690000, MARS), orientation: { heading: 0, pitch: CesiumLib.Math.toRadians(-48), roll: 0 }, duration: 1.7, complete: () => selectLocation(lat, lon) });
      }
      return;
    }
    namGazetteerSearch(query.trim());
  }

  function namHideSearchResults() {
    const box = $("search-results");
    if (box) { box.classList.add("hidden"); box.replaceChildren(); }
  }

  function openPanel(id) {
    closeAllPanels(id);
    const panel = $(id);
    panel.classList.remove("hidden");
    const buttonId = { "layers-panel": "layers-toggle", "data-panel": "data-toggle", "places-panel": "places-toggle", "search-panel": "search-toggle" }[id];
    if (buttonId) $(buttonId).setAttribute("aria-expanded", "true");
    if (id === "search-panel") window.setTimeout(() => $("location-search").focus(), 30);
  }

  function closePanel(id) {
    const panel = $(id); if (!panel) return;
    panel.classList.add("hidden");
    const buttonId = { "layers-panel": "layers-toggle", "data-panel": "data-toggle", "places-panel": "places-toggle", "search-panel": "search-toggle" }[id];
    if (buttonId) $(buttonId).setAttribute("aria-expanded", "false");
  }

  function closeAllPanels(except = null) {
    ["layers-panel", "data-panel", "places-panel", "search-panel"].forEach((id) => { if (id !== except) closePanel(id); });
  }

  function togglePanel(id) {
    if ($(id).classList.contains("hidden")) openPanel(id); else closePanel(id);
  }

  function addCustomLayer(event) {
    event.preventDefault();
    const name = $("custom-layer-name").value.trim();
    let url = $("custom-layer-url").value.trim();
    if (!name || !url) return;
    if (url.includes("{TileMatrix}")) url = url.replaceAll("{TileMatrix}", "{z}").replaceAll("{TileRow}", "{y}").replaceAll("{TileCol}", "{x}");
    if (!url.includes("{z}") || !url.includes("{y}") || !url.includes("{x}")) {
      window.alert("Use a tile URL template containing {z}, {y} and {x} (or WMTS {TileMatrix}, {TileRow} and {TileCol})."); return;
    }
    try {
      const parsed = new URL(url.replaceAll("{z}", "0").replaceAll("{y}", "0").replaceAll("{x}", "0"));
      if (parsed.protocol !== "https:") throw new Error("Use an HTTPS tile URL.");
    } catch (error) { window.alert(error.message || "That tile URL is not valid."); return; }
    const id = `custom-${Date.now()}`;
    customLayers.push({ id, name, group: "Custom service", description: "User-added XYZ tile service", customUrl: url, maxLevel: 8, attribution: name, swatch: "mola" });
    $("custom-layer-form").reset();
    addOverlayLayer(id);
    renderLayerCatalogue($("layer-filter").value);
  }

  function wireEvents() {
    $("search-toggle").addEventListener("click", () => togglePanel("search-panel"));
    $("layers-toggle").addEventListener("click", () => togglePanel("layers-panel"));
    $("data-toggle").addEventListener("click", () => togglePanel("data-panel"));
    $("places-toggle").addEventListener("click", () => togglePanel("places-panel"));
    $("home-view").addEventListener("click", flyHome);
    $("zoom-in").addEventListener("click", () => { if (viewer) viewer.camera.zoomIn(Math.max(viewer.camera.positionCartographic.height * .22, .30)); });
    $("zoom-out").addEventListener("click", () => { if (viewer) viewer.camera.zoomOut(Math.max(viewer.camera.positionCartographic.height * .22, .30)); });
    $("download-view").addEventListener("click", saveMapImage);
    $("about-toggle").addEventListener("click", () => $("notice-dialog").showModal());
    ui.routeMode.addEventListener("click", () => { toggleRouteMode(); openPanel("route-panel"); });
    $("close-route").addEventListener("click", () => {
      toggleRouteMode(false);
      if (routePoints.length) ui.routePanel.classList.add("hidden");
    });
    $("clear-route").addEventListener("click", clearRoute);
    ui.exportRoute.addEventListener("click", exportRouteGeoJSON);
    $("clear-selection").addEventListener("click", clearSelection);
    $("add-waypoint").addEventListener("click", () => { if (!selectedPoint) return; addRoutePoint(selectedPoint.lat, selectedPoint.lon); openPanel("route-panel"); toggleRouteMode(false); });
    $("retry-map").addEventListener("click", () => window.location.reload());
    $("search-panel").addEventListener("submit", (event) => { event.preventDefault(); searchLocation($("location-search").value); });
    $("layer-filter").addEventListener("input", () => renderLayerCatalogue($("layer-filter").value));
    $("custom-layer-form").addEventListener("submit", addCustomLayer);
    document.querySelectorAll("[data-close]").forEach((button) => button.addEventListener("click", () => closePanel(button.dataset.close)));
    const notice = $("notice-dialog");
    $("close-notice").addEventListener("click", () => notice.close());
    document.addEventListener("keydown", (event) => { if (event.key === "Escape") closeAllPanels(); });
    document.addEventListener("pointerdown", (event) => {
      if (event.target.closest(".floating-panel, .floating-search, .top-tools, .tool-rail, .zoom-tools")) return;
      closeAllPanels();
    });
  }

  function init() {
    wireEvents();
    renderDataSources();
    renderPlaces();
    renderLayerCatalogue();
    initNam();
    if (!window.Cesium) {
      showMapError("The globe library did not load", "CesiumJS could not be downloaded. Check your internet connection or the Cesium CDN, then reload.", "https://cesium.com/downloads/cesiumjs/releases/1.145/Build/Cesium/Cesium.js");
      return;
    }
    CesiumLib = window.Cesium;
    try {
      createMarsViewer();
    } catch (error) {
      console.error("Marswalk globe initialization failed:", error);
      showMapError("Mars could not be displayed", "The 3D globe did not initialize. The technical detail is shown below.", `${error.name || "Error"}: ${error.message || String(error)}`);
    }
  }

  /* =======================================================================
     NAM backend integration (v2)
     Connects the Marswalk globe to the NAM FastAPI backend:
       - point-inspection enrichment (elevation, hazard, shelters, water,
         radiation, rover POV)
       - A* route planning on the MOLA grid
       - IAU gazetteer search (102 features)
       - Walk View: first-person ground-level exploration + rover POV
       - AI assistant chat (SSE streaming, tool activity, fly-to)
       - storm simulation overlays + simulated presence (WebSocket)
       - real MOLA terrain on the globe (custom heightmap terrain provider)
     All scientific values carry provenance from the backend; simulated
     values are labelled [SIM].
     ======================================================================= */

  const NAM = (() => {
    const API = window.location.origin.startsWith("http") && !window.location.origin.includes(":8080")
      ? window.location.origin
      : "http://localhost:8000";
    let backendOnline = false;
    let enrichToken = 0;

    /* ---------- tiny fetch helpers ---------- */
    async function api(path, options) {
      const resp = await fetch(`${API}${path}`, options);
      if (!resp.ok) {
        const detail = await resp.json().catch(() => ({}));
        throw new Error(detail.detail ? (typeof detail.detail === "string" ? detail.detail : JSON.stringify(detail.detail)) : `${resp.status}`);
      }
      return resp.json();
    }
    const get = (path) => api(path);
    const post = (path, body) => api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });

    async function checkHealth() {
      try {
        const h = await get("/health");
        backendOnline = true;
        setNamStatus(true, `NAM backend v${h.version || "2"} online`);
        return true;
      } catch (error) {
        backendOnline = false;
        setNamStatus(false, "NAM backend offline — start it with: uvicorn app.main:app");
        return false;
      }
    }

    function setNamStatus(online, message) {
      const dot = $("nam-dot");
      const label = $("nam-label");
      if (!dot || !label) return;
      dot.classList.toggle("ok", online);
      dot.classList.toggle("bad", !online);
      label.textContent = message;
      label.title = online ? "NAM backend serving MOLA terrain, hazards, routing, assistant" : "Start the NAM backend: cd nam-backend && uvicorn app.main:app --port 8000";
    }

    /* =====================================================================
       P1 — inspector enrichment
       ===================================================================== */
    async function enrichInspector(lat, lon, siteId) {
      const token = ++enrichToken;
      const box = $("nam-readout");
      if (!box) return;
      box.classList.remove("hidden");
      // reset UI while loading
      $("nam-elev").textContent = "…"; $("nam-slope").textContent = "…";
      $("nam-rough").textContent = "…"; $("nam-pressure").textContent = "…";
      $("nam-rad").textContent = "…"; $("nam-hazard").textContent = "…";
      $("nam-hazard").className = "";
      $("nam-notes").replaceChildren();
      $("nam-shelters").replaceChildren(); $("nam-shelter-count").textContent = "…";
      $("nam-water").replaceChildren(); $("nam-water-count").textContent = "…";
      $("nam-pov").classList.add("hidden");
      $("nam-provenance").textContent = "Querying the NAM backend…";
      const lon360 = normalizeLongitude(lon) < 0 ? normalizeLongitude(lon) + 360 : normalizeLongitude(lon);

      if (!backendOnline) await checkHealth();

      const done = (fn) => { if (token === enrichToken) fn(); };
      const fail = (id, msg) => { const el = $(id); if (el) el.textContent = "—"; };

      // elevation + hazard + radiation in parallel
      get(`/api/v1/elevation?lat=${lat}&lon=${lon360}`).then((d) => done(() => {
        $("nam-elev").textContent = `${d.elev_m.toLocaleString()} m`;
        $("nam-slope").textContent = d.slope_deg == null ? "—" : `${d.slope_deg}°`;
        $("nam-rough").textContent = d.roughness_m == null ? "—" : `${d.roughness_m} m`;
        $("nam-pressure").textContent = `${d.pressure_mbar} mbar`;
      })).catch(() => { done(() => { fail("nam-elev"); fail("nam-slope"); fail("nam-rough"); fail("nam-pressure"); }); });

      get(`/api/v1/hazard?lat=${lat}&lon=${lon360}`).then((d) => done(() => {
        const el = $("nam-hazard");
        el.textContent = `${d.hazard_class} · ${d.hazard_score}`;
        el.className = `hazard-${d.hazard_class}`;
        const notes = $("nam-notes");
        notes.replaceChildren();
        (d.notes || []).slice(0, 3).forEach((n) => {
          const li = document.createElement("div");
          li.textContent = `• ${n}`;
          notes.append(li);
        });
      })).catch(() => done(() => fail("nam-hazard")));

      get(`/api/v1/radiation?lat=${lat}&lon=${lon360}`).then((d) => done(() => {
        $("nam-rad").textContent = `${d.dose_mSv_per_day} mSv/day`;
      })).catch(() => done(() => fail("nam-rad")));

      get(`/api/v1/shelters?lat=${lat}&lon=${lon360}&max_radius_km=900&limit=4`).then((d) => done(() => {
        $("nam-shelter-count").textContent = String(d.count);
        const host = $("nam-shelters");
        host.replaceChildren();
        (d.shelters || []).forEach((s) => {
          const row = document.createElement("div");
          row.className = "nam-detail-row";
          const nm = document.createElement("span"); nm.className = "nm"; nm.textContent = s.name;
          const mt = document.createElement("span"); mt.className = "mt";
          mt.textContent = `${s.kind} · ${s.distance_km} km · idx ${s.scores.sheltering_index}`;
          row.append(nm, mt);
          host.append(row);
        });
        if (!d.count) host.innerHTML = '<div class="nam-detail-row"><span class="nm">None within 900 km</span></div>';
      })).catch(() => done(() => { $("nam-shelter-count").textContent = "—"; }));

      get(`/api/v1/water?lat=${lat}&lon=${lon360}&max_radius_km=600&limit=3`).then((d) => done(() => {
        $("nam-water-count").textContent = String(d.count);
        const host = $("nam-water");
        host.replaceChildren();
        (d.water_candidates || []).forEach((w) => {
          const row = document.createElement("div");
          row.className = "nam-detail-row";
          const nm = document.createElement("span"); nm.className = "nm"; nm.textContent = `${w.label} (${w.lat.toFixed(1)}°, ${w.lon.toFixed(1)}°)`;
          const mt = document.createElement("span"); mt.className = "mt"; mt.textContent = `${w.ice_certainty} · depth ~${w.est_depth_to_ice_m} m`;
          row.append(nm, mt);
          host.append(row);
        });
        if (!d.count) host.innerHTML = '<div class="nam-detail-row"><span class="nm">None within 600 km</span></div>';
      })).catch(() => done(() => { $("nam-water-count").textContent = "—"; }));

      get(`/api/v1/walk/pov?lat=${lat}&lon=${lon360}&max_radius_km=150`).then((d) => done(() => {
        if (!d.found || !d.pov) return;
        const p = d.pov;
        $("nam-pov").classList.remove("hidden");
        $("nam-pov-dist").textContent = `${d.distance_km} km away`;
        const img = $("nam-pov-img");
        img.src = p.thumb_url; img.alt = p.caption;
        img.onerror = () => { $("nam-pov").classList.add("hidden"); };
        $("nam-pov-caption").textContent = p.caption;
        $("nam-pov-credit").textContent = `${p.mission} · ${p.instrument} · sol ${p.sol} · ${p.credit}`;
      })).catch(() => {});

      done(() => {
        $("nam-provenance").textContent = "Elevation/roughness: MOLA MEGDR 4 px/deg (NASA PDS) · Radiation: RAD/Curiosity baseline (Hassler 2014) · Shelters: Cushing 2007 + USGS SIM 3292 · Water: SWIM proxy (Morgan 2021) · all values advisory";
        $("nam-badge").textContent = siteId && places[siteId] ? places[siteId].name : "MOLA";
      });
    }

    /* =====================================================================
       P2 — A* route planning
       ===================================================================== */
    let astarEntity = null;
    let planning = false;

    async function planRouteAStar() {
      if (!viewer || !routePoints || planning) return;
      if (routePoints.length < 2) {
        const note = $("astar-note");
        note.classList.remove("hidden");
        note.textContent = "Add at least two waypoints first (click the surface while traverse mode is active).";
        return;
      }
      planning = true;
      const button = $("plan-route");
      button.disabled = true;
      button.textContent = "Planning…";
      const lon360 = (p) => (normalizeLongitude(p.lon) < 0 ? normalizeLongitude(p.lon) + 360 : normalizeLongitude(p.lon));
      const start = routePoints[0];
      const end = routePoints[routePoints.length - 1];
      const preset = $("route-preset").value || "balanced";
      try {
        const d = await post("/api/v1/route", {
          start_lat: start.lat, start_lon: lon360(start),
          end_lat: end.lat, end_lon: lon360(end),
          preset
        });
        if (astarEntity) { viewer.entities.remove(astarEntity); astarEntity = null; }
        const note = $("astar-note");
        note.classList.remove("hidden");
        if (!d.ok) {
          note.textContent = `A* could not find a path: ${(d.notes || []).join(" ")}`;
          $("astar-metrics").classList.add("hidden");
          return;
        }
        // draw planned path
        const coords = d.waypoints.map((w) => [normalizeLongitude(w.lon), w.lat, 2000]);
        astarEntity = viewer.entities.add({
          polyline: {
            positions: CesiumLib.Cartesian3.fromDegreesArrayHeights(coords.flat(), MARS),
            width: 4,
            material: new CesiumLib.ColorMaterialProperty(CesiumLib.Color.fromCssColorString("#e8834a")),
            arcType: CesiumLib.ArcType.NONE
          }
        });
        const s = d.stats || {};
        $("astar-length").innerHTML = `${(s.length_km || 0).toFixed(1)} <small>km</small>`;
        $("astar-slope").textContent = `${s.max_slope_deg ?? "—"}°`;
        $("astar-sols").textContent = `${s.est_sols ?? "—"} sols`;
        $("astar-metrics").classList.remove("hidden");
        note.textContent = `A* path over ${d.path_cells} MOLA cells (${preset} preset). ${s.ascent_m || 0} m ascent, ${s.descent_m || 0} m descent. Advisory only — regional MOLA slopes (~15 km cells) cannot resolve meter-scale obstacles.`;
        ui.routeInstruction.textContent = "A* planned route drawn in orange. Manual sketch retained beneath.";
      } catch (error) {
        const note = $("astar-note");
        note.classList.remove("hidden");
        note.textContent = `Route planning failed: ${error.message}. Is the NAM backend running?`;
      } finally {
        planning = false;
        button.disabled = false;
        button.textContent = "Plan walkable route (A*)";
      }
    }

    function clearAStarRoute() {
      if (astarEntity) { viewer.entities.remove(astarEntity); astarEntity = null; }
      $("astar-metrics").classList.add("hidden");
      $("astar-note").classList.add("hidden");
    }

    /* =====================================================================
       P3 — gazetteer search
       ===================================================================== */
    async function gazetteerSearch(query) {
      const box = $("search-results");
      if (!box) return;
      box.classList.remove("hidden");
      box.innerHTML = '<div class="sr-empty">Searching the IAU gazetteer…</div>';
      try {
        const d = await get(`/api/v1/gazetteer?q=${encodeURIComponent(query)}&limit=6`);
        box.replaceChildren();
        if (!d.count) {
          box.innerHTML = '<div class="sr-empty">No matching feature in the 102-entry IAU gazetteer. Try coordinates.</div>';
          return;
        }
        d.features.forEach((f) => {
          const row = document.createElement("button");
          row.type = "button"; row.className = "sr-row";
          const t = document.createElement("span"); t.className = "t"; t.textContent = f.name;
          const m = document.createElement("span"); m.className = "m"; m.textContent = `${f.type} · ${f.lat}°, ${f.lon}°`;
          row.append(t, m);
          row.addEventListener("click", () => {
            namHideSearchResults();
            closePanel("search-panel");
            viewer.camera.flyTo({
              destination: CesiumLib.Cartesian3.fromDegrees(normalizeLongitude(f.lon), f.lat, 620000, MARS),
              orientation: { heading: 0, pitch: CesiumLib.Math.toRadians(-48), roll: 0 },
              duration: 1.8,
              complete: () => selectLocation(f.lat, normalizeLongitude(f.lon))
            });
          });
          box.append(row);
        });
      } catch (error) {
        box.innerHTML = `<div class="sr-empty">Gazetteer search failed (${error.message}). Is the NAM backend running?</div>`;
      }
    }

    /* =====================================================================
       P4 — Walk View (Mars Street View)
       ===================================================================== */
    const walk = {
      active: false, lat: 0, lon: 0, heading: 0, pitch: 0, eyeHeight: 1.7,
      patch: null, keys: {}, drag: null, raf: null, savedCamera: null, hudThrottle: 0
    };

    async function enterWalkView(lat, lon) {
      if (!viewer || walk.active) return;
      if (!backendOnline && !(await checkHealth())) {
        ui.coordinate.textContent = "Walk View needs the NAM backend (uvicorn app.main:app)";
        return;
      }
      const lon360 = normalizeLongitude(lon) < 0 ? normalizeLongitude(lon) + 360 : normalizeLongitude(lon);
      closeAllPanels();
      clearSelection();
      try {
        const [init, patch] = await Promise.all([
          get(`/api/v1/walk/init?lat=${lat}&lon=${lon360}&heading_deg=0`),
          get(`/api/v1/walk/terrain?lat=${lat}&lon=${lon360}&radius_m=800&resolution_m=20`)
        ]);
        walk.active = true;
        walk.lat = lat; walk.lon = normalizeLongitude(lon);
        walk.heading = init.heading_deg || 0; walk.pitch = 0;
        walk.eyeHeight = init.eye_height_m || 1.7;
        walk.patch = patch;
        // Save the pre-walk camera so Exit restores it (camera.position always exists)
        walk.savedCamera = {
          position: viewer.camera.position.clone(),
          orientation: { heading: viewer.camera.heading, pitch: viewer.camera.pitch, roll: viewer.camera.roll }
        };

        // switch camera to first-person
        const controls = viewer.scene.screenSpaceCameraController;
        controls.enableRotate = false; controls.enableTranslate = false;
        controls.enableTilt = false; controls.enableZoom = false;
        controls.enableLook = false;
        controls.minimumZoomDistance = 0;
        updateWalkCamera();

        // HUD
        document.body.classList.add("walk-mode-active");
        $("walk-hud").classList.remove("hidden");
        updateWalkHud(true);

        // POV panel
        if (init.nearby_pov && init.nearby_pov.found && init.nearby_pov.pov) {
          const p = init.nearby_pov.pov;
          $("walk-pov").classList.remove("hidden");
          const img = $("walk-pov-img");
          img.src = p.thumb_url; img.alt = p.caption;
          img.onerror = () => $("walk-pov").classList.add("hidden");
          $("walk-pov-title").textContent = `${p.mission} · ${p.instrument}`;
          $("walk-pov-caption").textContent = p.caption;
          $("walk-pov-credit").textContent = `sol ${p.sol} · ${p.credit} · ${init.nearby_pov.distance_km} km away`;
        } else {
          $("walk-pov").classList.add("hidden");
        }

        installWalkControls();
        walkLoop();
        ui.coordinate.textContent = "Walk View — ground level";
      } catch (error) {
        ui.coordinate.textContent = `Walk View failed: ${error.message}`;
        exitWalkView();
      }
    }

    function patchHeight(lat, lon) {
      const p = walk.patch;
      if (!p) return null;
      const ex = p.extent;
      const nLat = p.grid_shape[0], nLon = p.grid_shape[1];
      const fx = (lon - ex.lon_min) / (ex.lon_max - ex.lon_min) * (nLon - 1);
      const fy = (ex.lat_max - lat) / (ex.lat_max - ex.lat_min) * (nLat - 1);
      if (fx < 0 || fy < 0 || fx > nLon - 1 || fy > nLat - 1) return null; // outside patch
      const x0 = Math.floor(fx), y0 = Math.floor(fy);
      const x1 = Math.min(nLon - 1, x0 + 1), y1 = Math.min(nLat - 1, y0 + 1);
      const tx = fx - x0, ty = fy - y0;
      const H = p.heights_m;
      const h00 = H[y0 * nLon + x0], h01 = H[y0 * nLon + x1], h10 = H[y1 * nLon + x0], h11 = H[y1 * nLon + x1];
      return (h00 * (1 - tx) + h01 * tx) * (1 - ty) + (h10 * (1 - tx) + h11 * tx) * ty;
    }

    function patchSlope(lat, lon) {
      const d = 8; // meters
      const mPerDegLat = 59185;
      const mPerDegLon = mPerDegLat * Math.max(0.05, Math.cos(lat * Math.PI / 180));
      const e0 = patchHeight(lat, lon);
      const en = patchHeight(lat + d / mPerDegLat, lon);
      const es = patchHeight(lat - d / mPerDegLat, lon);
      const ee = patchHeight(lat, lon + d / mPerDegLon);
      const ew = patchHeight(lat, lon - d / mPerDegLon);
      if (e0 == null || en == null || es == null || ee == null || ew == null) return null;
      const dzN = (en - es) / (2 * d), dzE = (ee - ew) / (2 * d);
      return Math.atan(Math.sqrt(dzN * dzN + dzE * dzE)) * 180 / Math.PI;
    }

    async function refreshPatch() {
      const lon360 = walk.lon < 0 ? walk.lon + 360 : walk.lon;
      try {
        walk.patch = await get(`/api/v1/walk/terrain?lat=${walk.lat}&lon=${lon360}&radius_m=800&resolution_m=20`);
      } catch (error) { /* keep old patch */ }
    }

    function updateWalkCamera() {
      const h = patchHeight(walk.lat, walk.lon);
      const eye = (h == null ? 0 : h) + walk.eyeHeight + 1.1; // 1.1 m clearance above sampled terrain
      viewer.camera.setView({
        destination: CesiumLib.Cartesian3.fromDegrees(walk.lon, walk.lat, eye, MARS),
        orientation: {
          heading: CesiumLib.Math.toRadians(walk.heading),
          pitch: CesiumLib.Math.toRadians(walk.pitch),
          roll: 0
        }
      });
    }

    function walkLoop() {
      if (!walk.active) return;
      const step = 4; // meters per frame
      const rad = Math.PI / 180;
      let moved = false;
      const fwd = (walk.keys.w ? 1 : 0) - (walk.keys.s ? 1 : 0);
      const strafe = (walk.keys.d ? 1 : 0) - (walk.keys.a ? 1 : 0);
      if (fwd || strafe) {
        const dir = walk.heading + Math.atan2(strafe, fwd) * 180 / Math.PI;
        walk.lat += Math.cos(dir * rad) * step / mPerDegLat();
        walk.lon += Math.sin(dir * rad) * step / mPerDegLon();
        moved = true;
      }
      if (moved) {
        // wrap longitude into -180..180
        walk.lon = normalizeLongitude(walk.lon);
        walk.lat = Math.max(-89.9, Math.min(89.9, walk.lat));
        const ex = walk.patch && walk.patch.extent;
        if (!ex || walk.lat < ex.lat_min + 0.001 || walk.lat > ex.lat_max - 0.001 ||
            walk.lon < ex.lon_min + 0.001 || walk.lon > ex.lon_max - 0.001) refreshPatch();
        updateWalkCamera();
      }
      const now = performance.now();
      if (now - walk.hudThrottle > 120) { walk.hudThrottle = now; updateWalkHud(false); }
      walk.raf = requestAnimationFrame(walkLoop);
    }

    function mPerDegLat() { return 59185; }
    function mPerDegLon() { return 59185 * Math.max(0.05, Math.cos(walk.lat * Math.PI / 180)); }

    function updateWalkHud(force) {
      const h = patchHeight(walk.lat, walk.lon);
      const s = patchSlope(walk.lat, walk.lon);
      $("walk-lat").textContent = formatLatitude(walk.lat);
      $("walk-lon").textContent = formatLongitude(walk.lon);
      $("walk-elev").textContent = h == null ? "—" : Math.round(h).toLocaleString();
      $("walk-slope").textContent = s == null ? "—" : s.toFixed(1);
      const dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
      const norm = ((walk.heading % 360) + 360) % 360;
      $("walk-compass").textContent = `${dirs[Math.round(norm / 45) % 8]} ${Math.round(norm)}°`;
    }

    function installWalkControls() {
      walk.keyHandler = (e) => {
        if (!walk.active) return;
        const k = e.key.toLowerCase();
        if (["w", "a", "s", "d"].includes(k)) { walk.keys[k] = e.type === "keydown"; e.preventDefault(); }
        if (k === "escape") exitWalkView();
      };
      document.addEventListener("keydown", walk.keyHandler);
      document.addEventListener("keyup", walk.keyHandler);

      // Use POINTER events: Cesium cancels pointerdown on its canvas, which
      // suppresses compatibility mouse events (mousedown never fires here).
      const canvas = viewer.canvas;
      walk.mouseDown = (e) => { if (walk.active && e.pointerType !== "touch") walk.drag = { x: e.clientX, y: e.clientY }; };
      walk.mouseMove = (e) => {
        if (!walk.active || !walk.drag) return;
        const dx = e.clientX - walk.drag.x, dy = e.clientY - walk.drag.y;
        walk.heading = ((walk.heading + dx * 0.22) % 360 + 360) % 360;
        walk.pitch = Math.max(-85, Math.min(60, walk.pitch + dy * 0.18));
        walk.drag = { x: e.clientX, y: e.clientY };
        updateWalkCamera();
      };
      walk.mouseUp = () => { walk.drag = null; };
      canvas.addEventListener("pointerdown", walk.mouseDown);
      document.addEventListener("pointermove", walk.mouseMove);
      document.addEventListener("pointerup", walk.mouseUp);
    }

    function exitWalkView() {
      if (!walk.active) return;
      walk.active = false;
      if (walk.raf) cancelAnimationFrame(walk.raf);
      if (walk.keyHandler) { document.removeEventListener("keydown", walk.keyHandler); document.removeEventListener("keyup", walk.keyHandler); }
      if (walk.mouseDown) {
        viewer.canvas.removeEventListener("pointerdown", walk.mouseDown);
        document.removeEventListener("pointermove", walk.mouseMove);
        document.removeEventListener("pointerup", walk.mouseUp);
      }
      walk.keys = {}; walk.drag = null;
      const controls = viewer.scene.screenSpaceCameraController;
      controls.enableRotate = true; controls.enableTranslate = true;
      controls.enableTilt = true; controls.enableZoom = true;
      controls.minimumZoomDistance = 12000;
      document.body.classList.remove("walk-mode-active");
      $("walk-hud").classList.add("hidden");
      if (walk.savedCamera) {
        viewer.camera.setView({ destination: walk.savedCamera.position, orientation: walk.savedCamera.orientation });
      } else {
        flyHome();
      }
      ui.coordinate.textContent = "Mars  ·  move over the surface for coordinates";
    }

    /* =====================================================================
       P5 — AI assistant (SSE)
       ===================================================================== */
    let assistantBusy = false;

    async function sendAssistantMessage(text) {
      if (!text || assistantBusy || !viewer) return;
      if (!backendOnline && !(await checkHealth())) {
        assistantPush("ai", "The NAM backend is offline. Start it with: cd nam-backend && uvicorn app.main:app --port 8000");
        return;
      }
      assistantBusy = true;
      assistantPush("user", text);
      const ai = assistantPush("ai", '<span class="thinking">thinking…</span>', true);
      const log = $("assistant-log");
      log.scrollTop = log.scrollHeight;
      let textHtml = "";
      const extras = [];
      try {
        const resp = await fetch(`${API}/api/v1/assistant/chat`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: text })
        });
        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buf = "";
        const render = () => {
          ai.innerHTML = textHtml + extras.join("") + (assistantBusy ? '<span class="thinking">…</span>' : "");
          log.scrollTop = log.scrollHeight;
        };
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buf += decoder.decode(value, { stream: true });
          let idx;
          while ((idx = buf.indexOf("\n\n")) >= 0) {
            const chunk = buf.slice(0, idx); buf = buf.slice(idx + 2);
            const line = chunk.split("\n").find((l) => l.startsWith("data: "));
            if (!line) continue;
            let ev; try { ev = JSON.parse(line.slice(6)); } catch { continue; }
            if (ev.type === "token") textHtml += ev.text;
            else if (ev.type === "fly_to") {
              extras.push('<div class="toolchip fly">⤴ fly to ' + ev.lat.toFixed(2) + "°, " + ev.lon.toFixed(2) + "°</div>");
              viewer.camera.flyTo({
                destination: CesiumLib.Cartesian3.fromDegrees(normalizeLongitude(ev.lon), ev.lat, 620000, MARS),
                orientation: { heading: 0, pitch: CesiumLib.Math.toRadians(-48), roll: 0 },
                duration: 2.2,
                complete: () => selectLocation(ev.lat, normalizeLongitude(ev.lon))
              });
            }
            else if (ev.type === "tool_call") extras.push(`<div class="toolchip">⚙ ${ev.tool}(${JSON.stringify(ev.args).slice(0, 70)})</div>`);
            else if (ev.type === "tool_result") extras.push(`<div class="toolchip ok">✓ ${ev.tool}: ${String(ev.result_summary).slice(0, 140)}</div>`);
            else if (ev.type === "sources") extras.push(`<div class="srcs">sources: ${ev.sources.map((s) => `<a href="${s}" target="_blank" rel="noreferrer">${s.replace(/^https?:\/\//, "").slice(0, 44)}</a>`).join(" · ")}</div>`);
            else if (ev.type === "done") break;
            render();
          }
        }
        if (!textHtml && !extras.length) ai.innerHTML = '<span class="thinking">(no response)</span>';
        else render();
      } catch (error) {
        ai.innerHTML = `Assistant request failed: ${error.message}. Is the NAM backend running?`;
      } finally {
        assistantBusy = false;
      }
    }

    function assistantPush(kind, html, isHtml) {
      const log = $("assistant-log");
      const div = document.createElement("div");
      div.className = `msg ${kind}`;
      if (isHtml) div.innerHTML = html; else div.textContent = html;
      log.append(div);
      log.scrollTop = log.scrollHeight;
      return div;
    }

    /* =====================================================================
       P6 — storms + presence
       ===================================================================== */
    const stormEntities = new Map(); // event id -> entity
    let presenceWS = null;
    const presenceEntities = new Map();

    async function simulateStorm() {
      if (!viewer) return;
      if (!backendOnline && !(await checkHealth())) return;
      // centre of the current view
      const carto = viewer.camera.positionCartographic;
      const lat = CesiumLib.Math.toDegrees(carto.latitude);
      const lon = normalizeLongitude(CesiumLib.Math.toDegrees(carto.longitude));
      const lon360 = lon < 0 ? lon + 360 : lon;
      const kind = $("storm-kind").value;
      const severity = kind === "sep" ? "X-flare-class" : $("storm-severity").value;
      try {
        const d = await post(`/api/v1/env/storms/simulate?kind=${kind}&lat=${lat}&lon=${lon360}&severity=${severity}`);
        drawStorm(d.event);
        renderStormList();
        ui.coordinate.textContent = `[SIM] ${kind} ${severity} at ${lat.toFixed(1)}°, ${lon.toFixed(1)}°`;
      } catch (error) {
        ui.coordinate.textContent = `Storm simulation failed: ${error.message}`;
      }
    }

    function drawStorm(e) {
      if (stormEntities.has(e.id)) return;
      const coords = e.polygon.map((p) => [normalizeLongitude(p.lon), p.lat]);
      const color = e.kind === "sep"
        ? CesiumLib.Color.fromCssColorString("#c46a5a").withAlpha(0.28)
        : CesiumLib.Color.fromCssColorString("#c9a25e").withAlpha(0.3);
      const entities = [];
      entities.push(viewer.entities.add({
        polygon: {
          hierarchy: CesiumLib.Cartesian3.fromDegreesArray(coords.flat()),
          material: color,
          outline: true, outlineColor: CesiumLib.Color.fromCssColorString(e.kind === "sep" ? "#e8834a" : "#c9a25e"), outlineWidth: 2,
          height: 30000
        }
      }));
      entities.push(viewer.entities.add({
        position: CesiumLib.Cartesian3.fromDegrees(normalizeLongitude(e.center.lon), e.center.lat, 60000, MARS),
        label: {
          text: `[SIM] ${e.kind.toUpperCase()} · ${e.severity}\n${e.duration_sols} sols`,
          font: "11px Inter, Arial, sans-serif",
          fillColor: CesiumLib.Color.fromCssColorString("#f1eee5"),
          outlineColor: CesiumLib.Color.fromCssColorString("#151817"),
          outlineWidth: 3,
          style: CesiumLib.LabelStyle.FILL_AND_OUTLINE,
          showBackground: true,
          backgroundColor: CesiumLib.Color.fromCssColorString("#151a17").withAlpha(0.8),
          pixelOffset: new CesiumLib.Cartesian2(0, 18)
        }
      }));
      stormEntities.set(e.id, entities);
    }

    function removeStorm(id) {
      const ents = stormEntities.get(id);
      if (ents) { ents.forEach((en) => viewer.entities.remove(en)); stormEntities.delete(id); }
      renderStormList();
    }

    function renderStormList() {
      const host = $("storm-list");
      if (!host) return;
      if (!stormEntities.size) {
        host.innerHTML = '<span class="empty-waypoints">No simulated events yet</span>';
        return;
      }
      host.replaceChildren();
      stormEntities.forEach((_, id) => {
        const row = document.createElement("div");
        row.className = "storm-event-row";
        const label = document.createElement("span"); label.textContent = id;
        const dismiss = document.createElement("button");
        dismiss.type = "button"; dismiss.className = "dismiss"; dismiss.textContent = "×";
        dismiss.setAttribute("aria-label", `Remove storm ${id}`);
        dismiss.addEventListener("click", () => removeStorm(id));
        row.append(label, dismiss);
        host.append(row);
      });
    }

    function togglePresence() {
      const button = $("presence-toggle");
      if (presenceWS) {
        presenceWS.close(); presenceWS = null;
        button.setAttribute("aria-pressed", "false");
        button.textContent = "Connect";
        $("presence-list").innerHTML = '<span class="empty-waypoints">Disconnected.</span>';
        presenceEntities.forEach((en) => viewer.entities.remove(en));
        presenceEntities.clear();
        return;
      }
      if (!backendOnline && !checkHealth()) return;
      const wsUrl = API.replace(/^http/, "ws") + "/ws/presence";
      try { presenceWS = new WebSocket(wsUrl); } catch (error) {
        $("presence-list").innerHTML = `<span class="empty-waypoints">WebSocket failed: ${error.message}</span>`;
        return;
      }
      button.setAttribute("aria-pressed", "true");
      button.textContent = "Disconnect";
      presenceWS.onmessage = (evt) => {
        let msg; try { msg = JSON.parse(evt.data); } catch { return; }
        if (msg.type !== "presence.update" || !Array.isArray(msg.agents)) return;
        renderPresence(msg.agents);
      };
      presenceWS.onerror = () => {
        $("presence-list").innerHTML = '<span class="empty-waypoints">Presence WebSocket failed — is the backend running?</span>';
      };
      presenceWS.onclose = () => {
        if (presenceWS) { presenceWS = null; button.setAttribute("aria-pressed", "false"); button.textContent = "Connect"; }
      };
    }

    function renderPresence(agents) {
      const host = $("presence-list");
      const seen = new Set();
      const colors = { crew: "#e8834a", rover: "#6fb3bd", habitat: "#7ba07b", cache: "#9a86c9" };
      host.replaceChildren();
      agents.forEach((a) => {
        seen.add(a.id);
        // marker
        const pos = CesiumLib.Cartesian3.fromDegrees(normalizeLongitude(a.lon), a.lat, 3000, MARS);
        let ent = presenceEntities.get(a.id);
        if (!ent) {
          ent = viewer.entities.add({
            id: `nam-presence-${a.id}`,
            position: pos,
            point: { pixelSize: 9, color: CesiumLib.Color.fromCssColorString(colors[a.kind] || "#e1b38e"), outlineColor: CesiumLib.Color.fromCssColorString("#151a17"), outlineWidth: 1.5, disableDepthTestDistance: 350000 },
            label: {
              text: `${a.name}${a.status === "eva" ? " [EVA]" : ""}`,
              font: "10px Inter, Arial, sans-serif",
              fillColor: CesiumLib.Color.fromCssColorString("#f1eee5"),
              outlineColor: CesiumLib.Color.fromCssColorString("#151817"),
              outlineWidth: 2.5,
              style: CesiumLib.LabelStyle.FILL_AND_OUTLINE,
              pixelOffset: new CesiumLib.Cartesian2(10, -10),
              distanceDisplayCondition: new CesiumLib.DistanceDisplayCondition(0, 8000000),
              disableDepthTestDistance: 350000
            }
          });
          presenceEntities.set(a.id, ent);
        } else { ent.position = pos; }
        // list row
        const row = document.createElement("div");
        row.className = "presence-row";
        const nm = document.createElement("span"); nm.textContent = a.name;
        const kind = document.createElement("span"); kind.className = `agent-kind ${a.kind}`; kind.textContent = `${a.kind} · ${a.status}`;
        row.append(nm, kind);
        host.append(row);
      });
      // remove stale agents
      presenceEntities.forEach((ent, id) => {
        if (!seen.has(id)) { viewer.entities.remove(ent); presenceEntities.delete(id); }
      });
    }

    /* =====================================================================
       P7 — MOLA terrain provider
       ===================================================================== */
    function createMolaTerrainProvider() {
      const tilingScheme = new CesiumLib.GeographicTilingScheme({ ellipsoid: MARS, numberOfLevelZeroTilesX: 2, numberOfLevelZeroTilesY: 1 });
      const cache = new Map();
      const width = 33;
      // Estimated level-zero geometric error (same formula Cesium uses):
      // circumference / (level-zero tiles × tile width)
      const levelZeroError = (2 * Math.PI * MARS.maximumRadius) / (2 * 256);
      const provider = {
        tilingScheme,
        ready: true,
        readyPromise: Promise.resolve(true),
        hasWaterMask: false,
        hasVertexNormals: false,
        credit: new CesiumLib.Credit("MOLA MEGDR 4 px/deg · NASA PDS via NAM backend"),
        errorEvent: new CesiumLib.Event(),
        getTileDataAvailable(x, y, level) { return level <= 8 ? true : undefined; },
        getLevelMaximumGeometricError(level) { return levelZeroError / (1 << level); },
        requestTileGeometry(x, y, level, request) {
          const key = `${level}/${x}/${y}`;
          const nX = 2 << level, nY = 1 << level;
          if (x < 0 || x >= nX || y < 0 || y >= nY || level > 8) {
            return Promise.reject(new Error("tile out of range"));
          }
          const deliver = (heights) => new CesiumLib.HeightmapTerrainData({
            buffer: new Float32Array(heights),
            width, height: width,
            structure: { heightScale: 1.0, heightOffset: 0.0, elementsPerHeight: 1, stride: 1, elementMultiplier: 1.0, isBigEndian: false }
          });
          if (cache.has(key)) return Promise.resolve(deliver(cache.get(key)));
          return fetch(`${API}/api/v1/terrain/tile/${level}/${x}/${y}?grid_size=${width}`)
            .then((r) => { if (!r.ok) throw new Error(String(r.status)); return r.json(); })
            .then((d) => {
              const flat = d.heights.flat();
              if (cache.size > 400) cache.clear();
              cache.set(key, flat);
              return deliver(flat);
            })
            .catch((error) => {
              // honest degradation: flat ellipsoid tile (no elevation data) instead of holes
              console.warn("NAM terrain tile failed, using flat ellipsoid:", key, error.message);
              return deliver(new Array(width * width).fill(0));
            });
        }
      };
      return provider;
    }

    /* =====================================================================
       wiring
       ===================================================================== */
    function initNam() {
      // status chip in the map-status bar
      const status = document.querySelector(".map-status");
      if (status && !$("nam-dot")) {
        const sep = document.createElement("span");
        sep.className = "readout-separator"; sep.textContent = " · ";
        const dot = document.createElement("span");
        dot.className = "status-dot"; dot.id = "nam-dot";
        const label = document.createElement("span");
        label.id = "nam-label"; label.textContent = "NAM backend…";
        status.append(sep, dot, label);
      }
      checkHealth();

      // tool buttons
      $("walk-toggle").addEventListener("click", () => {
        if (walk.active) { exitWalkView(); return; }
        if (selectedPoint) enterWalkView(selectedPoint.lat, selectedPoint.lon);
        else ui.coordinate.textContent = "Click a point on Mars first, then enter Walk View";
      });
      $("exit-walk").addEventListener("click", exitWalkView);
      $("enter-walk").addEventListener("click", () => {
        if (selectedPoint) enterWalkView(selectedPoint.lat, selectedPoint.lon);
      });
      $("assistant-toggle").addEventListener("click", () => togglePanel("assistant-panel"));
      $("close-assistant").addEventListener("click", () => closePanel("assistant-panel"));
      $("assistant-form").addEventListener("submit", (e) => {
        e.preventDefault();
        const input = $("assistant-input");
        const q = input.value.trim();
        if (!q) return;
        input.value = "";
        sendAssistantMessage(q);
      });
      document.querySelectorAll(".sugg").forEach((b) => b.addEventListener("click", () => sendAssistantMessage(b.dataset.q)));
      $("storm-toggle").addEventListener("click", () => togglePanel("storm-panel"));
      $("close-storm").addEventListener("click", () => closePanel("storm-panel"));
      $("simulate-storm").addEventListener("click", simulateStorm);
      $("presence-toggle").addEventListener("click", togglePresence);
      $("plan-route").addEventListener("click", planRouteAStar);
      $("clear-route").addEventListener("click", clearAStarRoute);

      // search box: live gazetteer suggestions
      const searchInput = $("location-search");
      let searchTimer = null;
      searchInput.addEventListener("input", () => {
        const q = searchInput.value.trim();
        if (searchTimer) clearTimeout(searchTimer);
        if (q.length < 3) { namHideSearchResults(); return; }
        searchTimer = setTimeout(() => {
          const isCoord = /^\s*-?\d+(\.\d+)?\s*[, ]\s*-?\d+(\.\d+)?\s*$/.test(q);
          if (!isCoord && viewer) gazetteerSearch(q);
        }, 300);
      });
      searchInput.addEventListener("keydown", (e) => { if (e.key === "Escape") namHideSearchResults(); });
      document.addEventListener("pointerdown", (e) => {
        if (!e.target.closest("#search-panel")) namHideSearchResults();
      });
    }

    return {
      enrichInspector, planRouteAStar, gazetteerSearch,
      enterWalkView, exitWalkView,
      sendAssistantMessage, simulateStorm, togglePresence,
      createMolaTerrainProvider, checkHealth, initNam
    };
  })();

  function initNam() { NAM.initNam(); }
  function namEnrichInspector(lat, lon, siteId) { NAM.enrichInspector(lat, lon, siteId); }
  function namGazetteerSearch(query) { NAM.gazetteerSearch(query); }

  document.addEventListener("DOMContentLoaded", init, { once: true });
})();
