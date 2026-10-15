#!/usr/bin/env python3
"""
bathy.py - sea floor for Tasmania in Bricks, from AusBathyTopo (Australia) 250 m 2026 (Geoscience Australia, CC BY 4.0).

  1. --download : fetch AusBathyTopo_Australia_2026_250m.zip (2.4 GB, resumable) into --work
  2. --warp     : cut Tasmania + Bass Strait and warp to EPSG:28355, 250 m, bilinear  ->  <work>/tas_bathy_mga.tif
                  grid E 160000-640000, N 5160000-5760000 (the statewide scene's extent)
  3. --apply    : put sea-floor heights into the sea cells of existing data/<id>.json scenes (clipped to [-150, -1] m)
                  and set "bathy": 1 there (a later precut.py re-cut keeps it only with --bathy <work>/tas_bathy_mga.tif)

Usage:
  python3 bathy.py --work /srv/data/bathy --download --warp
  python3 bathy.py --work /srv/data/bathy --apply --out /srv/www/data --meta scenes_meta.json
"""
import argparse, json, os, subprocess, sys, zipfile
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
URL = "https://files.ausseabed.gov.au/survey/AusBathyTopo_Australia_2026_250m.zip"
ZIPN = "AusBathyTopo_Australia_2026_250m.zip"
TIF = "tas_bathy_mga.tif"
EXTENT = (160000, 5160000, 640000, 5760000)      # xmin ymin xmax ymax, EPSG:28355


def download(work, log):
    os.makedirs(work, exist_ok=True); z = os.path.join(work, ZIPN)
    log(f"downloading {URL} -> {z} (resumable)")
    subprocess.run(["curl", "-fL", "--retry", "5", "-C", "-", "-o", z, URL], check=True)
    with zipfile.ZipFile(z) as zf:
        bad = zf.testzip()
        if bad: sys.exit(f"corrupt member in zip: {bad}")
    return z


def warp(work, log, keep=False):
    z = os.path.join(work, ZIPN)
    with zipfile.ZipFile(z) as zf:
        tifs = [n for n in zf.namelist() if n.lower().endswith(".tif")]
        msl = [n for n in tifs if "msl" in n.lower()] or tifs
        if not msl: sys.exit(f"no GeoTIFF in {z}: {zf.namelist()[:20]}")
        name = msl[0]; log(f"zip member: {name}")
        tmp = os.path.join(work, os.path.basename(name))
        if not os.path.exists(tmp):   # the member is deflated inside the zip: extract once for random access
            log(f"extracting {name} ...")
            with zf.open(name) as fi, open(tmp + ".part", "wb") as fo:
                while True:
                    b = fi.read(1 << 24)
                    if not b: break
                    fo.write(b)
            os.replace(tmp + ".part", tmp)
    out = os.path.join(work, TIF)
    cmd = ["gdalwarp", "-overwrite", "-t_srs", "EPSG:28355", "-te", *map(str, EXTENT), "-tr", "250", "250",
           "-r", "bilinear", "-dstnodata", "-9999", "-co", "COMPRESS=DEFLATE", "-co", "TILED=YES", tmp, out]
    log(" ".join(cmd)); subprocess.run(cmd, check=True)
    if not keep: os.remove(tmp); log(f"removed {tmp} (use --keep to retain)")
    import rasterio
    with rasterio.open(out) as ds:
        a = ds.read(1, masked=True)
        log(f"{out}: {ds.width}x{ds.height}, min {a.min():.0f} m, max {a.max():.0f} m, nodata {a.mask.mean():.3f}")
    return out


def apply(work, out_dir, meta_fn, log, only=""):
    import rasterio
    from precut import unpack_z, pack, sea_floor, SEA
    bds = rasterio.open(os.path.join(work, TIF))
    meta = json.load(open(meta_fn)) if meta_fn else {}
    ids = [s for s in (only.split(",") if only else meta.keys()) if s]
    for sid in ids:
        fn = os.path.join(out_dir, f"{sid}.json")
        if not os.path.exists(fn): log(f"{sid}: no {fn}"); continue
        d = json.load(open(fn))
        if d.get("r", 25) != 25: log(f"{sid}: skipped (statewide scene is built by statewide.py)"); continue
        W, H = d["nx"], d["ny"]
        Z, L, U = unpack_z(d["z"], W, H); Z = Z.copy()
        if not (L == SEA).any(): log(f"{sid}: no sea"); continue
        st = sea_floor(bds, Z, L, d["E0"], d["N1"])
        d["z"] = pack(Z, L, U); d["bathy"] = 1
        with open(fn + ".tmp", "w") as f: json.dump(d, f, separators=(",", ":"))
        os.replace(fn + ".tmp", fn)
        log(f"{sid}: sea floor {st}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", default="/srv/data/bathy")
    ap.add_argument("--download", action="store_true"); ap.add_argument("--warp", action="store_true")
    ap.add_argument("--apply", action="store_true"); ap.add_argument("--keep", action="store_true")
    ap.add_argument("--out", default="/srv/www/data"); ap.add_argument("--meta", default=os.path.join(HERE, "scenes_meta.json"))
    ap.add_argument("--only", default="")
    a = ap.parse_args(); log = lambda s: print(s, flush=True)
    if a.download: download(a.work, log)
    if a.warp: warp(a.work, log, a.keep)
    if a.apply: apply(a.work, a.out, a.meta, log, a.only)


if __name__ == "__main__":
    main()
