#!/usr/bin/env bash
# Download the LIST 25 m DEM (per council) and build a statewide mosaic.
# Output: /srv/data/dem/tas_dem25.vrt and tas_dem25.tif (COG, EPSG:28355, 25 m, nodata -9999)
set -euo pipefail
D=${1:-/srv/data/dem}; mkdir -p "$D"; cd "$D"
COUNCILS="BREAK_O_DAY BRIGHTON BURNIE CENTRAL_COAST CENTRAL_HIGHLANDS CIRCULAR_HEAD CLARENCE
DERWENT_VALLEY DEVONPORT DORSET FLINDERS GEORGE_TOWN GLAMORGAN_SPRING_BAY GLENORCHY HOBART
HUON_VALLEY KENTISH KING_ISLAND KINGBOROUGH LATROBE LAUNCESTON MEANDER_VALLEY NORTHERN_MIDLANDS
SORELL SOUTHERN_MIDLANDS TASMAN WARATAH_WYNYARD WEST_COAST WEST_TAMAR"
missing=()
for m in $COUNCILS; do
  f="LIST_DEM_25M_${m}.zip"
  [ -s "$f" ] && continue
  if wget -q --show-progress -O "$f.part" "https://listdata.thelist.tas.gov.au/opendata/data/$f" && [ -s "$f.part" ]; then
    mv "$f.part" "$f"
  else
    rm -f "$f.part"; missing+=("$m")
  fi
done
[ ${#missing[@]} -eq 0 ] || { echo "MISSING: ${missing[*]} (check names on listdata.thelist.tas.gov.au)"; }
: > asc.txt
for z in LIST_DEM_25M_*.zip; do a=$(unzip -Z1 "$z" | grep -i '\.asc$' | head -1); echo "/vsizip/$PWD/$z/$a" >> asc.txt; done
echo "$(wc -l < asc.txt) council grids"
gdalbuildvrt -overwrite -a_srs EPSG:28355 -srcnodata -9999 -vrtnodata -9999 -input_file_list asc.txt tas_dem25.vrt
gdal_translate -of COG -co COMPRESS=DEFLATE -co PREDICTOR=3 -co BIGTIFF=IF_SAFER tas_dem25.vrt tas_dem25.tif
gdalinfo -stats tas_dem25.tif | grep -E 'Size is|Pixel Size|STATISTICS_(MIN|MAX)'
