# MARSWALK — planetary atlas (prototype 0.4)

A full-screen, plain HTML/CSS/JavaScript Mars map interface using CesiumJS and public NASA/JPL Mars Trek WMTS tiles.

## Run locally

1. Extract the ZIP.
2. Open the `marswalk_frontend` folder in VS Code.
3. Open a terminal in that folder and run:

```bash
py -m http.server 8000
```

4. Visit `http://localhost:8000`.

Do not open the HTML file as `file://`. CesiumJS and NASA imagery are loaded from external services, so an internet connection is required.

## What's new in 0.4 — home screen

- The app opens on a home screen that shares the app's single live Cesium globe: same viewer, same Viking MDIM 2.1 imagery, same scene settings. There is no separate or decorative planet on the home screen.
- Moving the pointer across the screen drifts the globe along the x and y axes (the camera sub-point moves opposite the pointer so the planet visually follows it), with a short ease and a return to centre when the pointer leaves.
- "Enter the atlas" hands control back to Cesium's normal camera, flies down to the working overview and reveals the map toolbars and panels. The map is already loaded underneath, so entering does not reload anything.
- Home screen copy reuses the product's own language ("A field atlas for Mars.") and the existing brand tokens — no new fonts, colours or slogans.
- New file: `home.js` (home overlay, pointer-follow camera, enter transition). `app.js` now dispatches a `marswalk:ready` event after the globe initializes; nothing else in it changed. `index.html` gains the home section and a `home-mode` body class; `styles.css` gains an appended home section.

## What's new in 0.3

- Full-screen globe with a locally generated six-face star skybox.
- The opening camera keeps nearly the whole globe in view, with a slight tilt so the illuminated limb and atmospheric edge read as a sphere in space.
- Natural-looking Viking MDIM 2.1 global colour mosaic is the default basemap. MOLA colour hillshade remains available as an alternate basemap.
- Lighting and a restrained Mars-coloured atmospheric rim.
- Google Earth-style, icon-first floating controls. Panels are hidden until opened.
- Trackpad/mouse-wheel zoom and pinch zoom are enabled through Cesium's camera controller, with a gentler zoom factor and stronger zoom/rotate/translate inertia for trackpads and mouse wheels.
- Layer browser with directly connected Mars Trek equirectangular layers: MOLA roughness, MGS MOC atlas, MOLA/HRSC colour blend and hillshade blend.
- Base-map switching, overlay toggles and opacity controls.
- Custom XYZ / REST WMTS tile URL input for additional Mars equirectangular services.
- Data catalogue with source product, WMTS capabilities, PDS, USGS, THEMIS, HiRISE and rover-image links.
- One-click map image export and GeoJSON traverse export.
- Location search, place bookmarks, point inspection and route sketching.

## Map services and coordinate assumptions

The default basemap is `Mars_Viking_MDIM21_ClrMosaic_global_232m`, a global Viking colour mosaic listed in the Mars Trek equirectangular service catalogue. It uses the Mars 2000 geographic/equirectangular grid. Its tile URL uses the Mars Trek REST pattern:

```text
https://trek.nasa.gov/tiles/Mars/EQ/Mars_Viking_MDIM21_ClrMosaic_global_232m/1.0.0/default/default028mm/{z}/{y}/{x}.jpg
```

The base globe uses Mars 2000 equatorial and polar radii (3,396,190 m and 3,376,200 m). The NASA/JPL WMTS documentation explains that a global equirectangular layer begins at two columns by one row, doubling the number of columns and rows at each zoom level.

Connected overlay tile templates use the Mars Trek equirectangular services and a geographic tiling scheme. A custom layer must use Mars equirectangular coordinates (EPSG:104905) and an XYZ-style template containing `{z}`, `{y}` and `{x}`. WMTS `{TileMatrix}`, `{TileRow}` and `{TileCol}` tokens are also accepted and converted to those placeholders.

## Downloads and data sources

- The Data catalogue in the app links to Mars Trek's map-service catalogue and WMTS capabilities documents.
- It also links to official USGS, PDS, THEMIS, HiRISE and NASA rover image sources.
- WMTS tiles are streamed map images; a capabilities XML file describes the service but is not the source raster download. Use each product/archive link for the downloadable scientific data.
- The Save map image icon exports the current Cesium canvas as a PNG.

## Important scientific limitations

- The globe is a textured Mars ellipsoid, not yet a high-resolution terrain mesh.
- The connected overlay list is restricted to Mars Trek's equirectangular products compatible with this globe. Polar-projected and regional products (for example, many THEMIS polar products and some HiRISE mosaics) are listed in the Data catalogue but are not incorrectly overlaid on the global map.
- A custom tile service must use the same Mars equirectangular grid; adding an Earth web map or a polar map service will misalign.
- Mission markers are regional reference points, not current rover coordinates or landing ellipses.
- The route length is an approximate spherical surface-distance calculation. It does not account for terrain elevation, slope, obstacles, energy, communications, radiation, thermal conditions or mobility constraints. It must not be described as a safe route.

## Files

- `index.html` — full-screen app structure and home screen
- `styles.css` — icon-first overlay interface and home screen
- `app.js` — Cesium globe, star sky, NASA imagery, layer manager, data catalogue and traversal tools
- `home.js` — home screen: pointer-follow camera on the shared globe and the enter transition
