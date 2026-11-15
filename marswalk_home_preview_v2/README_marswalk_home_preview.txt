MARSWALK home screen concept preview

Files:
- marswalk_home_preview_v2.html: standalone, interactive home-screen concept.
- marswalk_home_preview_v2.png: still design preview.

To try the interactive preview:
1. Keep the HTML file in a folder.
2. Open a terminal in that folder.
3. Run: py -m http.server 8000
4. Open: http://localhost:8000/marswalk_home_preview_v2.html

Requires internet access for Three.js (jsDelivr) and the Mars texture.
Move your mouse around the main scene to steer the globe's orientation. When the pointer leaves the scene, the planet resumes a slow idle rotation.

The Start Exploring button is a placeholder in this standalone preview. In the integrated site it will dismiss the home screen and reveal the existing Cesium map application.

Texture attribution:
Mars surface texture by Solar System Scope: https://www.solarsystemscope.com/textures/
License: Creative Commons Attribution 4.0 International: https://creativecommons.org/licenses/by/4.0/
The home-screen texture is illustrative only. Do not treat it as scientific observation data. The field atlas itself should continue to use its NASA/JPL/USGS map layers and their source metadata.
