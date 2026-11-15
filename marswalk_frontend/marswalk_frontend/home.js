/* Marswalk home screen (0.4).
   The landing view shares the app's single live Cesium Mars globe — the same
   viewer, the same Viking MDIM 2.1 imagery and the same scene settings as the
   map. There is no second, decorative planet on the home screen.

   While the home overlay is up:
   - the app's floating chrome is hidden (see styles.css `body.home-mode`),
   - moving the pointer drifts the camera sub-point so the globe follows the
     pointer along the x and y axes,
   - "Enter the atlas" hands the camera back, flies down to the working view
     and reveals the map toolbars and panels. */

(() => {
  "use strict";

  const home = document.getElementById("home-screen");
  if (!home) return;

  const enterButton = document.getElementById("enter-app");
  const REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Framing matches the app's own opening overview camera in app.js
  // (18°E, 14°N, heading -12°, pitch -82°) so the home view and the map view
  // are unmistakably the same Mars.
  const BASE = { lon: 18, lat: 14, heading: -12, pitch: -82 };
  const HOME_ALTITUDE = 8400000;  // slightly wider than the app opening view
  const ENTER_ALTITUDE = 5200000; // the camera flies down to this on enter
  const LONGITUDE_TRAVEL = 26;    // degrees of sub-point travel across the x axis
  const LATITUDE_TRAVEL = 13;     // degrees of sub-point travel across the y axis
  const FOLLOW_EASE = 0.06;       // per-frame lerp toward the pointer target

  let viewer = null;
  let CesiumLib = null;
  let ellipsoid = null;
  let entered = false;
  let frameId = null;
  let targetX = 0;
  let targetY = 0;
  let currentX = 0;
  let currentY = 0;

  window.addEventListener("marswalk:ready", (event) => {
    const detail = event.detail || {};
    viewer = detail.viewer || null;
    CesiumLib = detail.Cesium || null;
    ellipsoid = detail.ellipsoid || null;
    if (viewer && CesiumLib && ellipsoid && !entered) activateHomeCamera();
  });

  function activateHomeCamera() {
    const controls = viewer.scene.screenSpaceCameraController;
    controls.enableZoom = false;
    controls.enableRotate = false;
    controls.enableTilt = false;
    controls.enableTranslate = false;
    if (REDUCED_MOTION) {
      applyPointerCamera();
    } else {
      frameId = window.requestAnimationFrame(step);
    }
  }

  function step() {
    currentX += (targetX - currentX) * FOLLOW_EASE;
    currentY += (targetY - currentY) * FOLLOW_EASE;
    applyPointerCamera();
    frameId = window.requestAnimationFrame(step);
  }

  // Camera sub-point moves opposite to the pointer so the globe itself
  // visually follows the pointer along both axes.
  function applyPointerCamera() {
    if (!viewer || viewer.isDestroyed()) return;
    viewer.camera.setView({
      destination: CesiumLib.Cartesian3.fromDegrees(
        BASE.lon - currentX * LONGITUDE_TRAVEL,
        BASE.lat + currentY * LATITUDE_TRAVEL,
        HOME_ALTITUDE,
        ellipsoid
      ),
      orientation: {
        heading: CesiumLib.Math.toRadians(BASE.heading),
        pitch: CesiumLib.Math.toRadians(BASE.pitch),
        roll: 0
      }
    });
  }

  function onPointerMove(event) {
    const bounds = home.getBoundingClientRect();
    targetX = Math.max(-1, Math.min(1, ((event.clientX - bounds.left) / bounds.width) * 2 - 1));
    targetY = Math.max(-1, Math.min(1, ((event.clientY - bounds.top) / bounds.height) * 2 - 1));
    if (REDUCED_MOTION) {
      currentX = targetX;
      currentY = targetY;
      applyPointerCamera();
    }
  }

  function onPointerLeave() {
    targetX = 0;
    targetY = 0;
    if (REDUCED_MOTION) {
      currentX = 0;
      currentY = 0;
      applyPointerCamera();
    }
  }

  function enterApp() {
    if (entered) return;
    entered = true;
    if (frameId) {
      window.cancelAnimationFrame(frameId);
      frameId = null;
    }
    home.removeEventListener("pointermove", onPointerMove);
    home.removeEventListener("pointerleave", onPointerLeave);
    home.classList.add("is-leaving");
    document.body.classList.remove("home-mode");

    if (viewer && CesiumLib && ellipsoid && !viewer.isDestroyed()) {
      const controls = viewer.scene.screenSpaceCameraController;
      controls.enableZoom = true;
      controls.enableRotate = true;
      controls.enableTilt = true;
      controls.enableTranslate = true;
      const finish = () => home.classList.add("hidden");
      if (REDUCED_MOTION) {
        viewer.camera.setView({
          destination: CesiumLib.Cartesian3.fromDegrees(BASE.lon, BASE.lat, ENTER_ALTITUDE, ellipsoid),
          orientation: {
            heading: CesiumLib.Math.toRadians(BASE.heading),
            pitch: CesiumLib.Math.toRadians(BASE.pitch),
            roll: 0
          }
        });
        window.setTimeout(finish, 120);
      } else {
        viewer.camera.flyTo({
          destination: CesiumLib.Cartesian3.fromDegrees(BASE.lon, BASE.lat, ENTER_ALTITUDE, ellipsoid),
          orientation: {
            heading: CesiumLib.Math.toRadians(BASE.heading),
            pitch: CesiumLib.Math.toRadians(BASE.pitch),
            roll: 0
          },
          duration: 2.2,
          complete: finish,
          cancel: finish
        });
        window.setTimeout(finish, 2600); // safety net if the flight is interrupted
      }
    } else {
      // Globe never became ready; still leave the home screen so the
      // map error / retry UI is fully interactive.
      home.classList.add("hidden");
    }
  }

  home.addEventListener("pointermove", onPointerMove);
  home.addEventListener("pointerleave", onPointerLeave);
  enterButton.addEventListener("click", enterApp);
})();
