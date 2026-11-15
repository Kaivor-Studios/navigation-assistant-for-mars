NAM — HOME SCREEN + ATLAS TRANSITION
====================================

WHAT THIS UPDATE DOES
---------------------
- Adds a cinematic but restrained NAM home screen using the NAM brand colours.
- Reuses the exact Cesium Mars globe already created by nam-v2/frontend/app.js.
- Mouse movement subtly changes the camera viewpoint while on the home screen.
- The globe has a very slow idle drift when the pointer is still.
- Clicking “Enter MARSWALK” flies the same camera into the existing atlas view.
- The existing atlas controls, NASA imagery, layers, places, route planner, inspector,
  Walk View and NAM backend integration remain in app.js and styles.css untouched.

IMPORTANT: ONE GLOBE, TWO MODES
-------------------------------
This package does not create a second Mars globe. It captures the existing Cesium
Viewer created by your current app.js. Home mode changes the camera behaviour and
shows a home overlay. Atlas mode hands the same Viewer back to normal Cesium controls.

INSTALLATION (WINDOWS)
----------------------
1. Download and extract NAM_HOME_ATLAS_UPDATE.zip.
2. Copy/extract the folder NAM_HOME_ATLAS_UPDATE into the ROOT of your GitHub project
   (the same folder that contains README.md, marswalk_frontend and nam-v2).
3. Open the NAM_HOME_ATLAS_UPDATE folder.
4. Double-click INSTALL_HOME_MODE.bat.
5. The installer copies two new files into nam-v2/frontend and adds their references
   to index.html. It creates index.html.before-nam-home-mode.bak before changing it.
6. Open nam-v2/frontend in VS Code and launch the frontend as you normally do.

The installer does not overwrite app.js or styles.css.

IF YOU NEED TO UNDO
-------------------
- Restore nam-v2/frontend/index.html from index.html.before-nam-home-mode.bak.
- Delete nam-v2/frontend/nam-home-mode.js and nam-home-mode.css.

BACKEND NOTE
------------
This is a frontend integration. It does not bundle or modify the Python/C++ backend.
The Mars globe and map services require an internet connection. Backend-powered NAM
features still require the NAM FastAPI backend to be running and reachable as in your
existing project setup.

TROUBLESHOOTING
---------------
- If the page stays on the map and no home screen appears, check the browser console.
- Confirm nam-home-mode.js is loaded before app.js in index.html. The installer does
  this automatically.
- If you deploy to Netlify, the frontend can be hosted there, but the FastAPI backend
  must be hosted separately and its API URL configured for the deployed environment.
