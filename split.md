Person A — Navigation algorithms and mission planning
Developer A
Highest mathematical priority

Files they can edit:
app/routing.py
app/missions.py
tests/test_submission_routing.py


Must fix
1. Correct the A slope calculation.*
   
   The current formula has a unit conversion error that can inflate calculated slopes by approximately 1,000 times.
   
   Calculate horizontal distance in metres and elevation gradient consistently:
   
   \[
   \text{slope}=\tan^{-1}\left(
   \frac{\Delta h}{\Delta d}
   \right)
   \]
2. Fix antimeridian routing.
   
   A route from longitude 359° to 1° must travel across the short 2° interval, not construct a grid spanning approximately 358°.
3. Fix mission optimization crashes.
   
   missions.py currently assumes every route has stats.length_km.
   
   The degraded fallback does not have this structure. Handle degraded routes explicitly and never report their length as a valid measured route.
4. Make steep-terrain handling consistent.
   
   Ensure the 38° terrain threshold behaves as an actual traversal constraint, rather than simply applying a large finite penalty.
5. Validate route output.
   
   Make sure every successful route returns:
   - Path.
   - Length.
   - Mean slope.
   - Maximum slope.
   - Estimated traversal time.
   - Provenance.
Tests required
- Known flat terrain produces approximately zero slope.
- A known inclined terrain produces a sensible slope.
- 359° to 1° generates a short route.
- Degraded routes do not crash mission optimization.
- Successful routes have all required statistics.
Completion condition
 A* produces mathematically sensible routes and mission optimization never crashes on fallback output.

Person B — Spatial engine and planetary geometry
Developer B
Terrain and coordinates

Files they can edit:
app/terrain.py
app/mars.py
app/routers/walkview.py
tests/test_submission_spatial.py


Must fix
1. Fix procedural terrain continuity.
   
   In terrain.py, _detail() generates a seed from the exact latitude and longitude. This means nearby points can receive unrelated noise values.
   
   Replace this with spatially continuous noise so adjacent terrain samples blend smoothly.
2. Fix terrain interpolation at longitude boundaries.
   
   Handle longitude 0°/360° correctly. Do not extrapolate from the final two grid columns when interpolation should wrap around.
3. Fix antimeridian bounding boxes.
   
   In bbox_stats(), the current longitude swapping can turn a small region crossing 0° into a huge region.
   
   Handle wrapped bounding boxes correctly.
4. Fix polygon area calculations.
   
   In mars.py, unwrap polygon longitudes before calculating area. A polygon crossing 359° to 1° must use the short longitude difference.
5. Fix Walk View's incorrect terrain description.
   
   In routers/walkview.py, the initialization response describes terrain as MOLA-derived even though the current engine supplies synthetic terrain.
   
   Correct the provenance so NAM does not claim to display real MOLA data when it isn't.
Tests required
- Terrain detail changes smoothly between neighbouring coordinates.
- Elevation interpolation works across 0°/360°.
- A small antimeridian bounding box returns a small region.
- Polygon area crossing the antimeridian is sensible.
- Walk View reports the correct terrain source.
Completion condition
 Spatial calculations behave correctly at planetary boundaries and all terrain provenance is accurate.

Person C — JEV AI and tool orchestration
Developer C
AI correctness

Files they can edit:
app/jev/router.py
app/routers/jev.py
tests/test_submission_jev.py


Must fix
1. Fix geological comparisons.
   
   In jev/router.py, the comparison composer currently reads the same analyze_terrain result for both locations.
   
   It must distinguish the first location's result from the second location's result.
2. Fix repeated tool executions.
   
   In routers/jev.py, this line is problematic:
   results[step["tool"]] = res
   
   
   
   If JEV executes analyze_terrain twice, the second result overwrites the first.
   
   Preserve each invocation separately, with its own ID and arguments, while keeping compatibility with the response composers.
3. Fix rover name extraction.
   
   The regular expression for rover routes has alternatives, but the code assumes the first capture group always contains the rover name.
   
   Correct the extraction so Perseverance, Curiosity, Opportunity and Spirit are handled consistently.
4. Fix _slim() JSON truncation.
   
   The current implementation slices serialized JSON and attempts to reconstruct it. This can produce malformed JSON.
   
   Use structured truncation that preserves valid JSON.
5. Improve tool execution failure handling.
   
   If one JEV tool fails:
   - Preserve the error.
   - Do not overwrite successful results.
   - Allow independent subsequent tools to execute.
   - Make the final response acknowledge missing information.
Tests required
- Compare two locations with different terrain statistics.
- Execute the same tool twice and retain both results.
- Test all four rover names.
- Test oversized tool outputs.
- Test one failed tool alongside one successful tool.
Completion condition
 JEV correctly handles multiple tool calls, comparisons and partial failures without producing misleading answers.




# **Complete NAM backend fix and improvement roadmap**

I reviewed the uploaded `nam-backend (1).zip` again, including the actual Python implementation, API routers, data structures, JEV orchestration, and tests.

The current test suite passes **48/48 tests**, but passing the five phase-gate suites does not mean every feature works correctly. There are mathematical errors, incomplete integrations, misleading scientific metadata, and missing capabilities.

I have deliberately excluded security-related recommendations.

I would divide the work into six development areas.

# **1. Critical fixes — do these first**

P0 · Must fix

These are implementation defects that can produce incorrect outputs, broken operations, or misleading results.

| #  | File                      | What to fix                                                                                                                                                                                                                      |
| -- | ------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1  | `app/routing.py`          | Correct the terrain slope calculation. The current formula produces severely inflated slopes because it mixes distance units and elevation differences incorrectly.                                                              |
| 2  | `app/routing.py`          | Fix longitude handling across the 0°/360° boundary. Routes between locations near opposite sides of the longitude boundary can generate incorrect grids and indices.                                                             |
| 3  | `app/routing.py`          | Make steep-terrain avoidance real. The current 38° threshold applies a large finite cost rather than making the cell impassable.                                                                                                 |
| 4  | `app/missions.py`         | Handle degraded route results in `optimize()`. It assumes every route has `stats.length_km`, which is not true for fallback routes.                                                                                              |
| 5  | `app/jev/router.py`       | Fix geological comparison. Both locations currently retrieve results using the same tool key, causing the second result to overwrite the first.                                                                                  |
| 6  | `app/routers/jev.py`      | Preserve multiple executions of the same tool using unique invocation IDs instead of dictionary keys based on tool names.                                                                                                        |
| 7  | `app/jev/router.py`       | Fix rover route matching. The regular expression has two alternatives, but the code assumes the first capture group always contains the rover name.                                                                              |
| 8  | `app/terrain.py`          | Fix longitude interpolation at the global grid boundary. Handle the final longitude cell periodically instead of extrapolating from the last two columns.                                                                        |
| 9  | `app/terrain.py`          | Correct bounding-box calculations crossing the antimeridian. Current longitude swapping can select almost the entire planet instead of a small region.                                                                           |
| 10 | `app/mars.py`             | Fix polygon area calculations across the longitude boundary. A polygon spanning 359° to 1° should not be treated as spanning 358°.                                                                                               |
| 11 | `app/terrain.py`          | Replace the current procedural-detail implementation. `_detail()` derives a new random seed from every coordinate and evaluates noise at a fixed lattice position. This does not produce a spatially continuous terrain surface. |
| 12 | `app/routers/walkview.py` | Correct the terrain provenance. Walk View currently describes its terrain patch as MOLA-derived even though the actual engine returns synthetic terrain.                                                                         |
| 13 | `app/jev/llm.py`          | Validate model-generated tool calls properly, including argument constraints, enum values, nested structures and unexpected arguments.                                                                                           |
| 14 | `app/routers/jev.py`      | Fix `_slim()`. Truncating serialized JSON by slicing characters can produce malformed JSON. Use structured truncation instead.                                                                                                   |
| 15 | `app/missions.py`         | Make mission optimization handle missing or degraded legs without crashing or silently reporting incomplete distances.                                                                                                           |

### **Additional mathematical corrections**

The following deserve independent attention:

- `app/terrain.py`: Handle slope calculations near the poles, where longitude distance approaches zero.
- `app/terrain.py`: Correct slope calculations at grid edges.
- `app/mars.py`: Improve polygon area calculations for large polygons and polar regions.
- `app/mars.py`: Validate coordinates instead of silently clamping invalid latitudes.
- `app/mars.py`: Replace the approximate solar-time calculation with a properly referenced Mars rotation and orbital model.
- `app/terrain.py`: Prevent elevation extrapolation outside the supported latitude range.
- `app/routing.py`: Ensure the A\* heuristic and movement costs remain consistent across every cost preset.

# **2. Terrain and planetary data engine**

P0 · Core infrastructure

This is arguably the most important part of NAM.

At present, the terrain engine is based on a synthetic 0.5° grid. That is useful for prototyping, but it is insufficient for the intended Google Earth-style experience.

['Great Desert = Mars Maps 1](https://images.openai.com/static-rsc-4/AkVRbkp4Ig1A-1GXq4nseuiEVilzZEgLmgLk9GoWOZ77s7b_pzVOmA3LWQ0MJsTOsfgUOUEW8V6zivhilFgJuMen_up-HJqLLVuKet8i9nrmLiUHIWvBi9LsLtDCPoyfllmrFT0GCUmFQnaR_j_CkTWu6plRsalshtyn7F2rhmI?purpose=inline)

[Terrain Model of Mars' Mojave Crater - NASA Science](https://images.openai.com/static-rsc-4/IPj0DY6l8S5_gzxu4tZrcwgogrpf8mklqO0pu8HHpKgndpAr_4EHJRT6qU8d2Qf1I7LF71TVGeLDdQ7H_BuKg7_H2key_Fk5tuA5RGas7Ku4dvVc1M7CST1habyx0oGhZO6owOdEL3iB2IRqxSPtdK63FN_gq_w8sdDls8u7-TY?purpose=inline)

[New Interactive Mosaic Uses NASA Imagery to Show Mars in Vivid Detail | NASA Jet Propulsion Laboratory (JPL)](https://images.openai.com/static-rsc-4/LOgUTdPV9tIL6q_c4fSqRDHY-OD17td82wfwzJKmCvF5zWJ9Dkae22wJEWK3Ki7gqaWuQetkXPuKz9GU5AzTbJFl69pd6ZdcetphPeecxfecOF0utoBpZXpXj_ZZ39rLj4WA4hZFFt-DKMVAsP-KepJELqmTvqoDSSqGDx0jeFo?purpose=inline)

8

### **A. Replace the synthetic DEM**

Implement:

- MOLA MEGDR global elevation ingestion.
- MOLA tile indexing.
- Regional DEM retrieval.
- HiRISE DTM ingestion.
- CTX-derived elevation products where available.
- Multiple DEM resolution levels.
- Automatic resolution selection based on zoom.
- Elevation interpolation across tile boundaries.
- No-data handling.
- Coordinate reference system handling.
- DEM version and source metadata.

**Important:** Do not simply load the entire MOLA dataset into RAM. Implement tiled, windowed access.

### **B. Rebuild the terrain sampling system**

The current engine should evolve into a multi-resolution terrain service.

| Capability             | Improvement                           |
| ---------------------- | ------------------------------------- |
| Elevation              | Real DEM sampling                     |
| Slope                  | Accurate gradient calculations        |
| Aspect                 | Direction of steepest descent         |
| Curvature              | Surface concavity and convexity       |
| Roughness              | Multi-scale surface roughness         |
| Relief                 | Accurate regional elevation variation |
| Terrain classification | Rock, plains, crater, dune, slope     |
| Hazard detection       | Terrain-dependent hazard mapping      |

### **C. Improve terrain mesh generation**

Current mesh generation should be expanded with:

- Adaptive mesh resolution.
- Level-of-detail management.
- Seamless neighbouring terrain patches.
- Normal-vector generation.
- Proper triangle winding.
- Terrain texture coordinates.
- No-data interpolation.
- Real vertical scaling.
- Tile stitching.
- GPU-friendly mesh formats.

### **D. Improve terrain downloads**

The current `/measure/terrain_download` endpoint primarily returns statistics, not an actual terrain dataset.

Build proper exports:

- GeoTIFF.
- Quantized mesh.
- Binary elevation grids.
- OBJ.
- STL.
- glTF terrain meshes.

The exported files should contain their actual spatial reference, resolution, vertical scale and provenance.

# **3. Imagery and scientific data infrastructure**

P0 · Major missing capability

The backend has an imagery registry and tile proxy, but several sources are only registered rather than fully integrated.

### **A. Imagery pipeline**

[Mars Digital Image Mosaic Globe - NASA Science](https://images.openai.com/static-rsc-4/D4iu8gGuJRRpjO9MCcKlGmAZxPHt2zkHIq8CW51F6bmuUDiKl4h1JD4DAK5YJjW02qSRjy6iILt8v68Sj-1Y_ls75qM8qcWLcBEFXCvGQDu60lEcgo5Dt9yAhDchlP6fjf0rnO6xaksyurOxzDXYWr1yVX-r2zOrqK1PWRIDgPU?purpose=inline)

[Astropedia - THEMIS Day IR Controlled Mosaic Mare Tyrrhenum 30S 090E 100 mpp](https://images.openai.com/static-rsc-4/laDnrbgIc5cgkqPidxnt96Z5zEPFwqLjDqCPBesNHraV3sV-Yd8QVxSy-yE5QtWzqU_rIqM4kGhFiisIME2XMk9fWXXEPEXlUVQ41LsPNQJWLitkt5b7P1euLtP2jxSqaG_-ppX281Tgwhr3Gm89AfAwucMOe80aqWxmH4Z8PD0?purpose=inline)

[De nouvelles images époustouflantes montrent le plus grand canyon du Système solaire (sur Mars)](https://images.openai.com/static-rsc-4/GCI5z6C6vBZ1Il4LIfgNyP7qDpanXOTOryxx8AC-Z1mHCOvPyfA1kHHD362B9Pb3O3GqIwKR-wqVoCeaFF7GUpxyirY0vX4tD3cs2Uznv0k0_KfGoDk31o-1pVQG4xfPAdEUdycs9S7x8HoeIdv-G9t3jq_n7M4o4IvNfTigpV8?purpose=inline)

8

Implement the following:

| Dataset      | Required improvement                  |
| ------------ | ------------------------------------- |
| Viking MDIM  | Actual global image tiles             |
| THEMIS       | Day and night infrared tiles          |
| CTX          | Complete operational tile integration |
| HiRISE       | Actual high-resolution image patches  |
| MOLA         | Colour elevation and shaded relief    |
| USGS geology | Functional geological map layers      |
| CRISM        | Mineralogical image products          |

Specific fixes:

- Implement proper WMS support.
- Implement XYZ and WMTS support where applicable.
- Add provider-specific tile adapters.
- Validate tile coordinates and zoom levels.
- Correct image content-type detection.
- Add image dimension validation.
- Add upstream retry and timeout policies.
- Add persistent tile caching.
- Add cache invalidation.
- Add tile coverage metadata.
- Add missing-tile fallback.
- Verify actual imagery endpoints rather than just performing HEAD requests against provider homepages.

The existing tile proxy should become a proper imagery delivery service.

### **B. Scientific data ingestion**

Currently, much of the scientific explorer relies on curated JSON datasets.

Build a proper ingestion pipeline.

**Recommended scientific datasets**

[NASA SVS | GMM-3 Mars Gravity Map](https://images.openai.com/static-rsc-4/swCTk-Kvm03fhcYwDRUTEL3EtPy-K68FNEZyL3I5MMrzhLIdWn_w4_eAmUxMfk2lsr1pTzm61763_EcltQJILey9A8MyKuqcXIZLiExxu_XHQe0QcsnwF5jvx7Idndv3VvVofC9pTBS6s-e_3tvDeiDNREY1BzudO_r5qL1dYoo?purpose=inline)

**MOLA**

Global elevation and topography.

[Nili Fossae in Natural Color and Across the Spectrum - NASA Science](https://images.openai.com/static-rsc-4/Eg-r2nTdRsx4hAIJc5tCfHM7NuDOlmvZ6ZRThIQDkV4NwcxHbvfvL5mEmnrRJ1EiY8QdAghbXBQjJm7kuOsN5IoUAx0xJSG1Yl1Y94dPvUV-pOzhIWk-AX5_xQ0HnO3criP7uBLjeNdCGNJThc1Xeg4e4mCulqTXikRDetNYsNU?purpose=inline)

**CRISM**

Mineralogical composition and alteration.

[Mars Thermal Inertia - NASA Science](https://images.openai.com/static-rsc-4/W-EuxnRcSb4H_YqdKoQNb4Y2q7om96CJB1hDeAtZsK5I6qSOhIWeHGwQ2211e_XS6mKdB-v5XpLvRPK7t0vnHEzR227M3QUKrINdL3l-hhCJz79pxCh4SbMiSZTkk2Wq83OIOczeNxt3vXZyUH-7jjnv1G5OHn01-rrolGcGzck?purpose=inline)

**THEMIS**

Thermal properties and surface composition.

[HiRISE | DTM: Deposits in Crater Depression](https://images.openai.com/static-rsc-4/gVpp6eZSAIz8sRsNMhQJLLTBCscfY1v1nMGj6vrQGFDBOCcLNhXKlx4GKtNSXQq2oAZXGq6_KLtZanQtgxIBpLPMBUIWfxSbUPPYh-d6ghnmWeZdRB7mOJSiHwQl_2mqCx9WE9DB5bThw7qi8DsFKypJm9cMnVCFpa0gtGuV9TU?purpose=inline)

**HiRISE**

High-resolution imagery and terrain models.

[This new map of ice on Mars could guide future astronauts | Space](https://images.openai.com/static-rsc-4/rwINUSwSzsBvCPXgXS2-MBtTwx8fVkxNux8Nafmj3O6wOwbAqM_guGoV4bXq9RsnvjiD1pf36l9ic86VXjS8Z3CKTk-JCrs_V3CSjMJV31phOd3CNXLlmsSz-9GB8ZvWahjubnyIuCVD6j1ZHAoT_Ic4taOCDOh62oMVuusq7Bo?purpose=inline)

**SWIM**

Subsurface water-ice evidence.

Implement:

- NASA PDS metadata ingestion.
- Dataset search by instrument, mission, location and date.
- Download manager.
- Data-format readers.
- Dataset indexing.
- Spatial indexing.
- Dataset processing pipeline.
- Observation-to-image linking.
- Observation-to-location linking.
- Dataset version tracking.
- Scientific citation management.
- Uncertainty and confidence metadata.

**Important improvement:** Store scientific observations as structured records rather than relying on manually curated JSON files as the primary scientific database.

# **4. JEV — Intelligent Mars Explorer**

P1 · Major improvement

JEV has a good foundation, but its current intelligence architecture is relatively basic.

It has a deterministic router, retrieval system, 24 tools and an optional local LLM.

I would make JEV substantially more capable.

### **A. Fix the existing architecture**

| File               | Improvement                                                                   |
| ------------------ | ----------------------------------------------------------------------------- |
| `jev/router.py`    | Replace brittle keyword and regex routing with structured intent recognition. |
| `jev/tools.py`     | Strengthen tool schemas and add semantic validation.                          |
| `jev/retrieval.py` | Improve retrieval ranking and contextual relevance.                           |
| `jev/llm.py`       | Add proper multi-turn tool execution and result verification.                 |
| `routers/jev.py`   | Preserve tool-call history and invocation-specific results.                   |

### **B. Build a proper agent architecture**

I recommend five separate reasoning components:

**1. Intent Understanding**

Understands what the user wants to accomplish.

**2. Mission and Research Planner**

Breaks complex requests into executable steps.

**3. Tool Execution Engine**

Uses terrain, imagery, science and mission tools.

**4. Verification and Evidence Engine**

Checks results, sources, consistency and uncertainty.

**5. Response and Globe Controller**

Explains findings and generates globe-control actions.

### **C. Add advanced JEV capabilities**

- Persistent conversation memory.
- Scientific knowledge graph.
- Semantic search using embeddings.
- Multi-step tool execution.
- Parallel tool execution when independent.
- Tool dependency planning.
- Automatic tool-result verification.
- Citation-level evidence tracking.
- Confidence and uncertainty reporting.
- Contradictory evidence detection.
- Scientific report generation.
- Mission-context awareness.
- Context-aware globe controls.
- Map selection awareness.
- Follow-up question understanding.
- Long-running research tasks.

### **D. Make JEV understand complex requests**

For example:

> Find the safest landing location near an ancient river delta with potential water ice, low slopes and good solar exposure.

JEV should:

1. Identify candidate geological regions.
2. Retrieve scientific observations.
3. Retrieve water-ice evidence.
4. Analyse real terrain elevation and slope.
5. Calculate solar illumination.
6. Evaluate landing constraints.
7. Rank candidate sites.
8. Explain the reasoning and evidence.
9. Display the results on the Mars globe.

That is the level of intelligence I would aim for.

# **5. Navigation, mission planning and simulations**

P1 · Operational capabilities

The current A\* planner is a useful prototype, but it needs substantial improvement before it can support realistic rover mission planning.

### **A. Navigation engine**

- Correct slope calculations.
- Real DEM-based navigation.
- Terrain traversability classification.
- Rock and boulder obstacle maps.
- Crater and cliff avoidance.
- Sand and dune hazard detection.
- Rover wheel-slip estimation.
- Wheel sinkage estimation.
- Energy-aware route planning.
- Solar-powered traversal scheduling.
- Communication availability modelling.
- Route uncertainty.
- Alternative route generation.
- Dynamic obstacle avoidance.
- Replanning after route obstruction.

### **B. Upgrade A\* into a multi-objective planner**

Currently, the routing presets are mainly different weightings of distance and slope.

Add multiple optimization objectives:

| Objective        | What it optimizes              |
| ---------------- | ------------------------------ |
| Shortest route   | Minimum distance               |
| Safest route     | Lowest terrain hazard          |
| Fastest route    | Estimated traversal time       |
| Energy-efficient | Lowest energy consumption      |
| Science-oriented | Maximum scientific value       |
| Balanced         | Combination of all constraints |

Use a weighted cost function such as:

\\[ C = w_dD+w_sS+w_rR+w_eE+w_cC\_{\text{comm}} \\]

Where:

- \\(D\\): distance.
- \\(S\\): slope cost.
- \\(R\\): terrain risk.
- \\(E\\): energy consumption.
- \\(C\_{\text{comm}}\\): communication penalty.

Eventually, consider multi-objective Pareto optimization rather than relying exclusively on one weighted score.

### **C. Mission management**

The existing mission manager needs:

- Mission templates.
- Mission version history.
- Mission scheduling.
- Mission dependencies.
- Multiple rovers per mission.
- Multiple objectives.
- Resource budgets.
- Energy budgets.
- Scientific priority scoring.
- Mission progress tracking.
- Waypoint editing.
- Route recalculation.
- Mission replay.
- Mission comparison with complete statistics.
- Export to GeoJSON, KML and CSV.

### **D. Improve environmental simulations**

The existing environment module has simplified radiation and storm scenarios.

Improve it with:

- Actual historical Mars dust-storm datasets.
- Spatial dust opacity maps.
- Time-dependent storm progression.
- Solar-array performance degradation.
- Atmospheric opacity effects.
- Validated radiation models.
- Radiation exposure along an entire route.
- Terrain-dependent shielding estimates.
- Solar illumination forecasting.
- Thermal environment modelling.
- Seasonal environmental variation.

Do not treat a preset storm scenario as a physical forecast.

# **6. Other backend modules**

These improvements are smaller individually but important collectively.

| Module                        | Improvements                                                                                  |
| ----------------------------- | --------------------------------------------------------------------------------------------- |
| `app/seeds.py`                | Add scalable indexing, pagination, filtering and better spatial searches.                     |
| `app/resources.py`            | Improve water and shelter ranking, uncertainty and spatial proximity calculations.            |
| `app/nodes.py`                | Fix node counting, deletion semantics, spatial filtering and metadata updates.                |
| `app/presence.py`             | Add timestamped telemetry, interpolation and historical playback.                             |
| `app/events.py`               | Add event persistence, sequence IDs, reconnection recovery and subscriptions.                 |
| `app/db.py`                   | Add database migrations, indexes and transaction support for multi-step operations.           |
| `app/connectors/base.py`      | Add persistent caching, retry policies, source validation and connector-specific adapters.    |
| `app/integrity.py`            | Introduce standardized data-quality, uncertainty and provenance schemas.                      |
| `app/routers/science.py`      | Improve discovery filtering, scientific comparisons and dataset-to-observation relationships. |
| `app/routers/panoramas.py`    | Add real asset resolution, image metadata, camera calibration and pose accuracy.              |
| `app/routers/walkview.py`     | Add actual surface imagery, terrain texture, camera visibility and proper surface elevation.  |
| `app/routers/measurements.py` | Add measurement validation, higher-resolution inputs and more accurate geodesic calculations. |

## **7. Specific feature gaps worth addressing**

These are additional capabilities that would make NAM more than a Mars map.

| Feature                   | What NAM should eventually support                        |
| ------------------------- | --------------------------------------------------------- |
| 3D geological exploration | Subsurface layers and geological cross-sections           |
| Crater analysis           | Rim detection, diameter, depth and morphology             |
| River analysis            | Valley-network and ancient drainage reconstruction        |
| Mineral exploration       | Mineralogical maps and spectral analysis                  |
| Water exploration         | Subsurface ice probability and depth estimates            |
| Landing-site analysis     | Multi-criteria landing-zone suitability                   |
| Rover simulation          | Mobility, energy and wheel-terrain interaction            |
| Mission replay            | Historical rover movement and observations                |
| Time explorer             | Seasonal and mission-time-based data                      |
| Scientific annotations    | User-created geological observations                      |
| Comparative exploration   | Compare two locations across multiple scientific datasets |
| Autonomous discovery      | Automatically identify scientifically interesting regions |

# **8. Testing improvements**

The 48 tests passing is encouraging, but the test suite currently validates phase-gate functionality more than scientific and numerical correctness.

I would build a much more comprehensive testing system.

| Test category    | What to test                                         |
| ---------------- | ---------------------------------------------------- |
| Geodesy          | Distances, bearings, longitude wrapping              |
| Terrain          | Interpolation, slope, boundaries, poles              |
| Routing          | Known routes, obstacles, disconnected terrain        |
| Mission planning | Failed routes, optimization and ordering             |
| JEV              | Multi-tool execution, comparisons, context retention |
| Imagery          | Real upstream tiles, content types, missing tiles    |
| Science          | Citation integrity and dataset consistency           |
| Radiation        | Reference values and model sensitivity               |
| Storms           | Historical event comparisons                         |
| Walk View        | Mesh continuity and actual imagery availability      |
| Database         | Transactions, persistence and migrations             |
| Performance      | Large bounding boxes and simultaneous requests       |

### **Particularly important new tests**

1. Route from longitude 359° to longitude 1°.
2. Calculate terrain slope on a known synthetic plane.
3. Compare Jezero and Gale and verify different terrain results.
4. Optimize a mission containing a degraded route.
5. Generate a terrain patch crossing the 0° meridian.
6. Calculate polygon area crossing the antimeridian.
7. Verify that Walk View never labels synthetic data as measured MOLA.
8. Execute the same JEV tool three times and verify that all three results survive.
9. Compare numerical solar illumination against a trusted reference.
10. Generate a mesh from adjacent patches and verify that their shared edges match.

Also introduce numerical regression tests using known reference datasets, not just mocked outputs.

# **9. Recommended development order**

I would not implement all of these simultaneously. This is the order I would follow.

## **NAM Backend Development Roadmap**

1. **Phase A — Correctness and stability**

   First priority

   Fix all 15 critical issues, coordinate handling, numerical calculations, JEV result management and mission failures.

   Deliverable: Reliable existing backend.
2. **Phase B — Real planetary data**

   Core priority

   MOLA ingestion, CTX imagery, HiRISE integration, real tile delivery and spatial data management.

   Deliverable: Real Mars terrain and imagery.
3. **Phase C — Scientific explorer**

   High priority

   PDS ingestion, CRISM, THEMIS, SWIM, scientific indexing and evidence retrieval.

   Deliverable: Actual scientific exploration platform.
4. **Phase D — Advanced navigation**

   Terrain-aware pathfinding, energy modelling, obstacle avoidance and multi-objective mission planning.

   Deliverable: Realistic rover mission-planning engine.
5. **Phase E — JEV intelligence**

   Multi-step agents, semantic retrieval, persistent scientific context, evidence verification and autonomous research.

   Deliverable: Intelligent Mars research assistant.
6. **Phase F — Advanced simulation and collaboration**

   Environmental models, rover simulation, mission playback, real-time telemetry and collaborative exploration.

   Deliverable: Full exploration operations platform.

## **10. What I would give the development team**

Here is the consolidated priority checklist. It can be used directly as an engineering task tracker.

**Engineering task tracker**

# **0/57**

**Critical correctness**

0/15 completed

Fix A\* slope mathematics

Fix 0°/360° route handling

Fix A\* steep-terrain constraints

Handle degraded routes in mission optimization

Fix JEV comparison result overwriting

Fix repeated tool invocation storage

Fix rover route regex

Fix terrain longitude interpolation

Fix antimeridian bounding boxes

Fix polygon area across antimeridian

Replace discontinuous procedural terrain noise

Correct Walk View MOLA provenance

Strengthen LLM tool argument validation

Replace unsafe JSON truncation

Fix incomplete route statistics

**Terrain and data**

0/8 completed

Integrate real MOLA DEM

Build tiled DEM reader

Integrate HiRISE DTMs

Implement adaptive terrain resolution

Improve slope, aspect and curvature

Build continuous terrain meshes

Implement real terrain exports

Add DEM metadata and no-data handling

**Imagery and science**

0/9 completed

Complete CTX tile integration

Implement WMS and WMTS adapters

Integrate THEMIS layers

Integrate HiRISE imagery

Integrate CRISM products

Build NASA PDS ingestion

Build scientific spatial index

Link observations to imagery

Add dataset provenance and uncertainty

**Navigation and missions**

0/8 completed

Build terrain traversability model

Add obstacle detection

Add energy-aware routing

Add communication-aware routing

Implement multi-objective planning

Improve mission optimization

Add mission versioning and replay

Add rover mobility simulation

**JEV**

0/8 completed

Build structured intent recognition

Implement multi-step planning

Improve semantic retrieval

Add persistent scientific memory

Add evidence verification

Add uncertainty-aware responses

Add context-aware map control

Add research workflows

**Other modules and testing**

0/9 completed

Fix node count and deletion

Improve spatial resource ranking

Add event replay and sequence IDs

Add database migrations

Add persistent connector cache

Add panorama pose verification

Add numerical regression tests

Add real-data integration tests

Add performance benchmarks

Reset checklist

## **My final recommendation**

There are three things that should define the next NAM release:

1. **Real Mars:** Replace synthetic terrain and incomplete imagery with actual planetary datasets.
2. **Real navigation:** Make terrain calculations and rover pathfinding scientifically and mathematically defensible.
3. **Real intelligence:** Turn JEV into a multi-step research and mission-planning agent that can reason over actual scientific evidence.

I would call the next milestone **NAM v2.3 — Scientific Data and Navigation Core**.

Do not add more superficial endpoints until these three foundations are reliable. That is where the biggest improvement in the quality of NAM will come from.




