/*
 * NAM home / atlas mode bridge.
 * Uses the SAME Cesium Viewer and Mars globe created by the existing app.js.
 * This file must load after Cesium.js and BEFORE app.js.
 */
(() => {
  "use strict";

  if (!window.Cesium || !window.Cesium.Viewer) {
    console.warn("NAM home mode: Cesium Viewer was not available when the bridge loaded.");
    return;
  }

  const C = window.Cesium;
  const OriginalViewer = C.Viewer;
  let mode = "starting";
  let activeViewer = null;
  let homeRoot = null;
  let homeTransform = null;
  let animationFrame = 0;
  let pointerX = 0;
  let pointerY = 0;
  let currentX = 0;
  let currentY = 0;
  let lastPointerAt = 0;
  let lastFrameAt = 0;
  let idleHeading = 0;
  let hiddenEntities = [];
  let savedControls = null;

  const HOME_RANGE = 9_800_000;
  const HOME_PITCH = C.Math.toRadians(-79.5);
  const POINTER_HEADING_RANGE = C.Math.toRadians(17);
  const POINTER_PITCH_RANGE = C.Math.toRadians(5.5);

  function byId(id) { return document.getElementById(id); }

  function createHomeMarkup(mapApp) {
    if (byId("nam-home-screen")) return byId("nam-home-screen");

    const section = document.createElement("section");
    section.className = "nam-home-screen";
    section.id = "nam-home-screen";
    section.setAttribute("aria-label", "NAM home screen");
    section.innerHTML = `
      <header class="nam-home-header">
        <a class="nam-home-brand" href="#" aria-label="Navigation Assistant for Mars">
          <span class="nam-home-mark" aria-hidden="true">N</span>
          <span class="nam-home-brand-copy">
            <strong>NAM</strong>
            <span>Navigation Assistant for Mars</span>
          </span>
        </a>
        <div class="nam-home-system-label">PLANETARY NAVIGATION SYSTEM<br>MISSION INTERFACE · 01</div>
      </header>

      <div class="nam-home-copy">
        <p class="nam-home-kicker">A planetary atlas for exploration</p>
        <h1 class="nam-home-title">Find your way<br>on the <em>Red Planet.</em></h1>
        <p class="nam-home-description">
          Explore Martian terrain, examine scientific observations and plan
          surface traverses through one interactive planetary map.
        </p>
        <div class="nam-home-actions">
          <button class="nam-enter-atlas" id="nam-enter-atlas" type="button">
            Enter MARSWALK <span aria-hidden="true">→</span>
          </button>
          <span class="nam-home-hint">Move your pointer to look around Mars</span>
        </div>
      </div>

      <div class="nam-home-side-note" aria-hidden="true">
        <strong>MARS · 04</strong>
        3D planetary view<br>Live map environment
      </div>

      <footer class="nam-home-footer">
        <span>MARSWALK · PLANETARY ATLAS</span>
        <span>Viking MDIM 2.1 · NASA / JPL / USGS</span>
      </footer>
    `;

    // Keep the real Cesium canvas as the background; the home page is only an overlay.
    mapApp.appendChild(section);
    section.querySelector(".nam-home-brand").addEventListener("click", event => event.preventDefault());
    section.querySelector("#nam-enter-atlas").addEventListener("click", enterAtlas);
    return section;
  }

  function setControlsEnabled(enabled) {
    if (!activeViewer || activeViewer.isDestroyed()) return;
    const controls = activeViewer.scene.screenSpaceCameraController;
    if (enabled) {
      controls.enableInputs = savedControls ? savedControls.enableInputs : true;
      controls.enableZoom = savedControls ? savedControls.enableZoom : true;
      controls.enableRotate = savedControls ? savedControls.enableRotate : true;
      controls.enableTilt = savedControls ? savedControls.enableTilt : true;
      controls.enableTranslate = savedControls ? savedControls.enableTranslate : true;
    } else {
      controls.enableInputs = false;
      controls.enableZoom = false;
      controls.enableRotate = false;
      controls.enableTilt = false;
      controls.enableTranslate = false;
    }
  }

  function hideInitialMapEntities() {
    hiddenEntities = [];
    try {
      activeViewer.entities.values.forEach(entity => {
        hiddenEntities.push({ entity, show: entity.show });
        entity.show = false;
      });
    } catch (error) {
      console.debug("NAM home mode: no initial entities to hide", error);
    }
  }

  function restoreMapEntities() {
    hiddenEntities.forEach(item => {
      if (item.entity && !item.entity.isDestroyed?.()) item.entity.show = item.show;
    });
    hiddenEntities = [];
  }

  function applyHomeCamera() {
    const globe = activeViewer.scene.globe;
    const marsEllipsoid = globe.ellipsoid;
    const target = C.Cartesian3.fromDegrees(0, 0, 0, marsEllipsoid);
    homeTransform = C.Transforms.eastNorthUpToFixedFrame(target, marsEllipsoid);

    lastFrameAt = 0;
    lastPointerAt = performance.now();
    activeViewer.camera.lookAtTransform(
      homeTransform,
      new C.HeadingPitchRange(0, HOME_PITCH, HOME_RANGE)
    );
    queueHomeCamera();
  }

  function animateHomeCamera() {
    animationFrame = 0;
    if (mode !== "home" || !activeViewer || activeViewer.isDestroyed()) return;

    const now = performance.now();
    const deltaSeconds = lastFrameAt ? Math.min((now - lastFrameAt) / 1000, 0.05) : 0;
    lastFrameAt = now;
    const easing = 0.075;
    currentX += (pointerX - currentX) * easing;
    currentY += (pointerY - currentY) * easing;

    // A very slow idle drift keeps the planet feeling alive without competing with the pointer.
    if (now - lastPointerAt > 1200) idleHeading += deltaSeconds * 0.0022;

    const heading = currentX * POINTER_HEADING_RANGE + idleHeading;
    const pitch = HOME_PITCH + currentY * POINTER_PITCH_RANGE;

    activeViewer.camera.lookAtTransform(
      homeTransform,
      new C.HeadingPitchRange(heading, pitch, HOME_RANGE)
    );

    animationFrame = window.requestAnimationFrame(animateHomeCamera);
  }

  function queueHomeCamera() {
    if (mode !== "home" || animationFrame) return;
    animationFrame = window.requestAnimationFrame(animateHomeCamera);
  }

  function installHomePointerMovement(mapApp) {
    mapApp.addEventListener("pointermove", event => {
      if (mode !== "home" || event.pointerType === "touch") return;
      const rect = mapApp.getBoundingClientRect();
      pointerX = C.Math.clamp(((event.clientX - rect.left) / rect.width) * 2 - 1, -1, 1);
      pointerY = C.Math.clamp(((event.clientY - rect.top) / rect.height) * 2 - 1, -1, 1);
      lastPointerAt = performance.now();
      queueHomeCamera();
    });

    mapApp.addEventListener("pointerleave", () => {
      if (mode !== "home") return;
      pointerX = 0;
      pointerY = 0;
      queueHomeCamera();
    });
  }

  // Prevent the atlas's native click/wheel controls from running behind the home page.
  // This listener is registered before app.js installs its own handlers.
  window.addEventListener("pointerdown", event => {
    if (mode !== "home") return;
    if (event.target && event.target.closest && event.target.closest("#nam-enter-atlas")) return;
    if (event.target && event.target.closest && event.target.closest("#cesiumContainer")) {
      event.preventDefault();
      event.stopImmediatePropagation();
    }
  }, true);

  window.addEventListener("contextmenu", event => {
    if (mode === "home" && event.target && event.target.closest && event.target.closest("#cesiumContainer")) {
      event.preventDefault();
      event.stopImmediatePropagation();
    }
  }, true);

  window.addEventListener("wheel", event => {
    if (mode === "home" && event.target && event.target.closest && event.target.closest("#cesiumContainer")) {
      event.preventDefault();
      event.stopImmediatePropagation();
    }
  }, { capture: true, passive: false });

  function finishTransition() {
    mode = "atlas";
    const mapApp = document.querySelector(".map-app");
    if (mapApp) mapApp.classList.remove("nam-home-mode");
    if (homeRoot && homeRoot.isConnected) homeRoot.remove();
    homeRoot = null;
    setControlsEnabled(true);
    restoreMapEntities();
    activeViewer.resize();
    activeViewer.scene.requestRender();
  }

  function enterAtlas() {
    if (mode !== "home" || !activeViewer || activeViewer.isDestroyed()) return;
    mode = "transition";
    if (animationFrame) window.cancelAnimationFrame(animationFrame);
    animationFrame = 0;

    if (homeRoot) homeRoot.classList.add("is-exiting");

    // Move out of the local home-camera frame without replacing the viewer.
    activeViewer.camera.lookAtTransform(C.Matrix4.IDENTITY);

    activeViewer.camera.flyTo({
      destination: C.Cartesian3.fromDegrees(18, 14, 7400000, activeViewer.scene.globe.ellipsoid),
      orientation: {
        heading: C.Math.toRadians(-12),
        pitch: C.Math.toRadians(-82),
        roll: 0
      },
      duration: 2.8,
      easingFunction: C.EasingFunction.CUBIC_IN_OUT,
      complete: finishTransition,
      cancel: finishTransition
    });
  }

  function attachHomeMode(viewer) {
    if (!viewer || (typeof viewer.isDestroyed === "function" && viewer.isDestroyed())) return;
    const mapApp = document.querySelector(".map-app");
    if (!mapApp || !document.getElementById("cesiumContainer")) return;

    activeViewer = viewer;
    mode = "home";
    const controls = viewer.scene.screenSpaceCameraController;
    savedControls = {
      enableInputs: controls.enableInputs,
      enableZoom: controls.enableZoom,
      enableRotate: controls.enableRotate,
      enableTilt: controls.enableTilt,
      enableTranslate: controls.enableTranslate
    };

    mapApp.classList.add("nam-home-mode");
    homeRoot = createHomeMarkup(mapApp);
    hideInitialMapEntities();
    setControlsEnabled(false);
    applyHomeCamera();
    installHomePointerMovement(mapApp);
    viewer.resize();
    viewer.scene.requestRender();
  }

  // Capture the single Viewer instance created by the existing app.js.
  // We do not instantiate a second globe and do not replace the map renderer.
  function NAMViewerCapture(...args) {
    const viewer = Reflect.construct(OriginalViewer, args, OriginalViewer);
    window.__NAM_SHARED_MARS_VIEWER__ = viewer;
    window.setTimeout(() => attachHomeMode(viewer), 0);
    return viewer;
  }
  NAMViewerCapture.prototype = OriginalViewer.prototype;
  Object.setPrototypeOf(NAMViewerCapture, OriginalViewer);
  C.Viewer = NAMViewerCapture;
})();
