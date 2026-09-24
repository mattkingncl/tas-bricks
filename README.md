# Tasmania in Bricks — server kit

Static site served by Caddy; scene data pre-cut on the VM from the LIST 25 m DEM.

    www/                 ready-to-serve site (index.html, lib/three, data/<scene>.json)
    tas-template.html    page source (__DATA__ placeholder)
    scenes_meta.json     curated scene definitions: extent, labels, spot heights, lake names/levels
    fetch_dem.sh         download council DEM zips -> statewide VRT + COG
    precut.py            DEM + LIST lakes + LIST land use -> www/data/<scene>.json
    make_site.py         template -> www/index.html (vendored three.js, no CDN)

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
