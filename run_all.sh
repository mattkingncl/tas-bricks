#!/usr/bin/env bash
# run_all.sh - fetch and build every optional layer for Tasmania in Bricks on the VM, then rebuild the page.
#   geology (all scenes) -> sea floor (AusBathyTopo) -> statewide 1 km scene -> ice age -> fire history -> index.html
# Re-runnable: downloads are kept in /srv/data/{bathy,glacial}; each step logs to /srv/data/logs/<step>.log.
# Usage (from the kit directory, i.e. where this file is):  ./run_all.sh            # everything
#                                                           ./run_all.sh fire ice   # only some steps
set -uo pipefail
cd "$(dirname "$0")"
PY=${PY:-/srv/data/venv/bin/python}
DEM=${DEM:-/srv/data/dem/tas_dem25.tif}
OUT=${OUT:-/srv/www/data}
WWW=${WWW:-/srv/www}
LOG=/srv/data/logs; mkdir -p "$LOG"
STEPS=${*:-geology bathy statewide ice fire site}

for c in curl gdalwarp ogr2ogr; do command -v $c >/dev/null || { echo "missing $c: sudo apt install -y curl gdal-bin"; exit 1; }; done
[ -f "$DEM" ] || { echo "no DEM at $DEM (run fetch_dem.sh first)"; exit 1; }
df -h /srv/data | tail -1 | awk '{print "free space on /srv/data: " $4 " (sea floor step needs ~6 GB while it runs)"}'

run() { local name=$1; shift; echo "== $name: $*"; local t=$(date +%s)
  if "$@" > "$LOG/$name.log" 2>&1; then echo "   ok ($(( $(date +%s) - t )) s)"; else echo "   FAILED - see $LOG/$name.log"; tail -5 "$LOG/$name.log"; fi; }

for s in $STEPS; do case $s in
  geology)   run geology   $PY geology.py --dem "$DEM" --meta scenes_meta.json --out "$OUT" ;;
  bathy)     run bathy-get $PY bathy.py --work /srv/data/bathy --download --warp
             run bathy     $PY bathy.py --work /srv/data/bathy --apply --out "$OUT" --meta scenes_meta.json ;;
  statewide) run statewide $PY statewide.py --dem "$DEM" --bathy /srv/data/bathy/tas_bathy_mga.tif --out "$OUT" ;;
  ice)       run ice       $PY glacial.py --dem "$DEM" --work /srv/data/glacial --out "$OUT" --meta scenes_meta.json ;;
  fire)      run fire      $PY fire.py --out "$OUT" --meta scenes_meta.json ;;
  site)      run site      $PY make_site.py --template tas-template.html --www "$WWW" --three "$WWW/lib/three" ;;
  *) echo "unknown step $s" ;;
esac; done

echo; echo "== summary (paste this back)"
$PY - "$OUT" <<'EOF'
import json, os, sys
out = sys.argv[1]
print(f"{'scene':11s} {'r':>5s} {'kB':>5s}  geo  bathy ice  fire  notes")
for fn in sorted(os.listdir(out)):
    if not fn.endswith('.json') or '_' in fn or fn == 'index.json': continue
    sid = fn[:-5]; d = json.load(open(os.path.join(out, fn)))
    ex = lambda k: os.path.exists(os.path.join(out, f"{sid}_{k}.json"))
    notes = []
    if ex('ice'): notes.append("ice " + str(json.load(open(os.path.join(out, f'{sid}_ice.json'))).get('stats')))
    if ex('fire'):
        f = json.load(open(os.path.join(out, f'{sid}_fire.json'))); s = [x[0] for x in f['fires']]
        notes.append(f"fires {len(s)} ({min(s)}-{max(s)})")
    print(f"{sid:11s} {d.get('r', 25):5d} {os.path.getsize(os.path.join(out, fn)) // 1000:5d}  "
          f"{'y' if d.get('geo') and ex('geo') else '-':4s} {'y' if d.get('bathy') else '-':5s} {'y' if d.get('ice') else '-':4s} "
          f"{'y' if d.get('fire') else '-':5s} {'; '.join(notes)}")
EOF
for f in "$LOG"/*.log; do grep -h -E "sea floor|tasmania:|GLACIMONTIS|FAILED|AusBathyTopo|DEM:|lakes:|zip member|tas_bathy" "$f" 2>/dev/null | cut -c1-200; done
