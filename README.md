# Tasmania in Bricks — server kit

Static site served by Caddy; scene data pre-cut on the VM from the LIST 25 m DEM.

    www/                 ready-to-serve site (index.html, lib/three, data/<scene>.json)
    tas-template.html    page source (__DATA__ placeholder)
    scenes_meta.json     curated scene definitions: extent, labels, spot heights, lake names/levels
    fetch_dem.sh         download council DEM zips -> statewide VRT + COG
    precut.py            DEM + LIST lakes + LIST land use -> www/data/<scene>.json
    make_site.py         template -> www/index.html (vendored three.js, no CDN)
    run_all.sh           optional layers (geology, sea floor, statewide scene, ice age, fire) + site
    geology.py bathy.py statewide.py glacial.py fire.py   one script per layer (see below)

## 1. Deploy now (uses the bundled data)
    rsync -a www/ /srv/www/

## 2. Build data on the VM
    sudo apt -y install gdal-bin unzip python3-venv
    python3 -m venv /srv/data/venv && . /srv/data/venv/bin/activate
    pip install -r requirements.txt
    ./fetch_dem.sh /srv/data/dem                      # ~1-2 GB download, a few minutes
    ./precut.py --dem /srv/data/dem/tas_dem25.tif --meta scenes_meta.json \
                --out /srv/www/data --verify scenes_ref.json
    python3 make_site.py --template tas-template.html --www /srv/www --three www/lib/three

Verification: `--verify scenes_ref.json` compares with the current (browser-built) bundle and reports
max |dZ|, and lake/urban cell differences. Expect 0 everywhere except possibly a few
cells on council boundaries (the VRT takes the last council with data; the browser
build took the first).

## 3. Add or edit a scene
Add an entry to scenes_meta.json (E0, N1 on the 25 m grid; nx, ny in 25 m cells; r0 = coarsest
native tier; lakes = ordered names; labels; spots; lev) and a matching entry in SCENES in
tas-template.html (name, blurb, hero camera). Then run precut.py --only <id> and make_site.py.

## Optional layers: geology, sea floor, statewide scene, ice age, fire
One command fetches and builds everything, then rebuilds index.html (logs in /srv/data/logs):

    ./run_all.sh                    # geology bathy statewide ice fire site
    ./run_all.sh fire site          # any subset, in that order

It ends with a summary table to check. Each layer is optional: the page shows a control only when the
scene's data/<id>.json carries the flag (`geo`, `bathy`, `ice`, `fire`), and falls back otherwise.

| step | script | source | output |
|---|---|---|---|
| geology | geology.py | MRT geology via theLIST (GeologicalAndSoils 14 = 1:25k, 16 = 1:250k) | data/<id>_geo.json, `geo:1` |
| bathy | bathy.py | AusBathyTopo (Australia) 250 m 2026, Geoscience Australia (2.4 GB zip, kept in /srv/data/bathy) | sea-floor heights in the sea cells of data/<id>.json, `bathy:1` |
| statewide | statewide.py | DEM (Tasmania) + AusBathyTopo (sea floor, Victorian coast) + LIST major lakes | data/tasmania.json (1 km; tiers 8/4/2/1 km) |
| ice | glacial.py | GLACIMONTIS palaeoglaciers (Zenodo 15600659), Tasmanian records | data/<id>_ice.json, `ice:1` |
| fire | fire.py | theLIST Fire History - All (EmergencyManagementPublic/1) | data/<id>_fire.json, `fire:1` |

* **Geology** is on by default wherever prepared: walls and build-step slices show rock, the surface keeps
  vegetation; the *Geology map* toggle puts the mapped unit on the top plate. Model: bases of the near-flat
  layered units (Tertiary, Jurassic dolerite, Triassic, Permian) fitted to the DEM height of mapped contacts
  (plane <= 3 deg + Gaussian residual, 600 m) at 100 m, forced to agree with the map in every model cell;
  older basement extruded from the nearest outcrop; Quaternary cover a 10 m veneer; no faults.
* **Statewide geology** (All of Tasmania): geology.py also builds data/tasmania_geo.json from the 1:250k map (layer 16),
  one unit per age group, majority per 1 km cell; walls show the surface rock extended down (no layer-cake model at
  state scale). `./geology.py --dem ... --meta scenes_meta.json --out /srv/www/data --only tasmania`.
* **Palaeo labels** (All of Tasmania, `paleo` in SCENES): Bassian Plain, Bass Basin, Furneaux and King Island land
  bridges, shown only when the sea is lowered by 45 m or more (`PALEO_SL`).
* **Sea floor**: bilinear to 25 m, clipped to [-150, -1] m. `precut.py --bathy /srv/data/bathy/tas_bathy_mga.tif`
  keeps it on a re-cut (otherwise re-run `./run_all.sh bathy`); a re-cut keeps the `geo`/`ice`/`fire` flags when
  their files exist. The scripts only read scenes_meta.json (the scene list), so the repo stays clean. The sea-level slider then runs -120...+70 m;
  lowering it exposes sea floor connected to open water at the model edge.
* **Ice age** toggle (Landscape): ice plates from the mapped glacier outlines, thickness from perfectly plastic
  ice (tau = 100 kPa, `--tau`) built inwards from the margin on the present ground; sea at -120 m where the
  scene has sea floor.
* **Fire history** toggle (Landscape): round tiles on burnt blocks, on the canopy where present, coloured by years
  since the most recent fire before the current season (bushfires to 60 years, planned burns to 20).
* **Water drop** mode: tap to release a drop; D8 steepest descent on a Priority-Flood + epsilon filled surface
  of the model's block heights; outlets are the sea and the model edge; the outlet's catchment is outlined in red.
  Statewide scene only (the mode button opens it). `?debug` in the URL exposes `window.__tb` for testing.

## Caddy
In the site block, let the browser revalidate data (ETag) so regenerated scenes appear at once:

    header /data/* Cache-Control "no-cache"
    header /lib/*  Cache-Control "public, max-age=31536000, immutable"

## Buildings (Hobart, Launceston)
`b` in scenes_meta.json / data/<scene>.json: per 25 m cell building height (uint8, 0.5 m units, raw deflate,
base64), from Overture Maps buildings release 2026-09-23.0 (z14 PMTiles). 16 sub-samples per cell; a cell is
built when >= 4 fall in a footprint and takes the tallest building there. Height = `height` (mostly Microsoft ML),
raised to 3.3 m x `num_floors` where tagged; else residential 5 m, outbuilding 3 m, other 8 m. precut.py carries
`b` through from scenes_meta.json unchanged. Toggle "Buildings" in the page. Remove the `b` key to drop the layer.

Data: LIST Tasmania 25 m DEM, Hydrographic Areas, Landuse Live — Land Tasmania, CC BY 3.0 AU.
Buildings: Overture Maps Foundation (© OpenStreetMap contributors, ODbL; Microsoft ML Buildings, ODbL).
three.js r160 — MIT licence (lib/three/LICENSE).

## Rendering performance
* The shadow map is redrawn only when the model changes, and frames are drawn only when something changes.
* Level of detail by tile (tas-template.html: `TILE`, `LOD_PX`, `LOD_MIN`). Models with more than `LOD_MIN` visible
  pieces are split into `TILE`-stud tiles. A tile where a stud spans at least `LOD_PX` pixels is drawn with rounded
  bricks; farther tiles use plain boxes and 6-sided studs. Tiles off screen are not drawn. Hero views, triangles per frame:
  Hobart 25 m 126 M -> 13 M; Cradle 25 m 22 M -> 1.5 M; zooming in brings full detail back near the camera.
