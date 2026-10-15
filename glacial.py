#!/usr/bin/env python3
"""
glacial.py - last-glaciation ice for Tasmania in Bricks.

Outlines: GLACIMONTIS, empirically reconstructed palaeoglaciers (Zenodo record 15600659, CC BY 4.0), layer
EmpiricallyReconstructedPaleoglaciers, records with mrange2 = 'Australia' south of N 5 700 000 (MGA55), i.e. the
Tasmanian reconstructions (Colhoun & Barrows 2001; Barrows et al. 2001, 2002; Mackintosh et al. 2006), ~44-20 ka.

Thickness is not mapped, so it is modelled: perfectly plastic ice (Nye 1952) with basal shear stress tau on today's
ground (the bed), built inwards from the mapped margin. Along a flow line  dS/dx = tau / (rho g H),  H = S - B.
On the 100 m grid this is solved exactly per step with Dijkstra from the margin (S = B outside the ice):
    (S_i - S_j) (H_i + H_j) / 2 = tau d / (rho g),   d = 100 m or 141 m,   S_i = B_i + H_i  (> S_j: Dijkstra order valid)
which gives the Nye profile H = sqrt(2 tau x / (rho g)) on a flat bed, thin ice over high ground and thick ice in troughs.

Output data/<id>_ice.json: {gs, nx, ny, h (base64 raw-deflate Uint16 LE, metres, 0 = no ice), dtype, unit, tau, src, stats}
on the scene grid (origin E0, N1): gs = 100 m for 25 m scenes, 1000 m for the statewide scene.

Usage:
  python3 glacial.py --dem /srv/data/dem/tas_dem25.tif --work /srv/data/glacial --out /srv/www/data [--only cradle,ossa]
"""
import argparse, base64, heapq, json, math, os, subprocess, sys, time, zipfile
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
URL = "https://zenodo.org/api/records/15600659/files/GLACIMONTIS_SHP.zip/content"
LAYER = "EmpiricallyReconstructedPaleoglaciers"
RHO, G = 900.0, 9.81
GS = 100.0          # ice model grid (m)
PAD = 10000.0       # model window padding beyond the scene (m): glaciers crossing the scene edge get their true margin


def outlines(work, log):
    """Tasmanian palaeoglacier polygons in EPSG:28355 as GeoJSON features."""
    os.makedirs(work, exist_ok=True)
    z = os.path.join(work, "GLACIMONTIS_SHP.zip"); gj = os.path.join(work, "tas_palaeoglaciers_mga.geojson")
    if not os.path.exists(z):
        log(f"downloading {URL}")
        subprocess.run(["curl", "-fL", "--retry", "5", "-o", z + ".part", URL], check=True); os.replace(z + ".part", z)
    if not os.path.exists(gj):
        with zipfile.ZipFile(z) as zf:
            shp = [n for n in zf.namelist() if n.endswith(LAYER + ".shp")]
        if not shp: sys.exit(f"{LAYER}.shp not found in {z}")
        cmd = ["ogr2ogr", "-f", "GeoJSON", "-t_srs", "EPSG:28355", "-where", "mrange2 = 'Australia'", gj,
               f"/vsizip/{z}/{shp[0]}"]
        log(" ".join(cmd)); subprocess.run(cmd, check=True)
    feats = json.load(open(gj))["features"]
    keep = []
    for f in feats:
        ys = [p[1] for poly in _polys(f["geometry"]) for ring in poly for p in ring]
        if ys and max(ys) < 5700000: keep.append(f)
    srcs = sorted({str(f["properties"].get("scitation") or "")[:60] for f in keep})
    log(f"GLACIMONTIS: {len(feats)} Australian records, {len(keep)} in Tasmania; sources: {srcs}")
    return keep


def _polys(g):
    return [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"] if g["type"] == "MultiPolygon" else []


def rasterise(feats, E0, N1, W, H, cell):
    from rasterio.features import rasterize
    from affine import Affine
    shapes = [(f["geometry"], 1) for f in feats]
    if not shapes: return np.zeros((H, W), bool)
    return rasterize(shapes, out_shape=(H, W), transform=Affine(cell, 0, E0, 0, -cell, N1), fill=0,
                     dtype="uint8", all_touched=False).astype(bool)


def bed100(ds, E0, N1, W, H):
    """Mean DEM height of each 100 m cell (4 x 4 native 25 m cells, NaN where any is no-data)."""
    from precut import read_window
    out = np.empty((H, W))
    for r0 in range(0, H, 200):           # 200 rows of 100 m at a time (bounded memory for the statewide window)
        h = min(200, H - r0)
        M = read_window(ds, E0, N1 - r0 * GS, 4 * W, 4 * h)
        out[r0:r0 + h] = M.reshape(h, 4, W, 4).mean(axis=(1, 3))
    return out


def thickness(mask, bed, cell, tau):
    """Perfectly plastic ice thickness (m) inside `mask` by Dijkstra from the margin (see module docstring)."""
    Hh, Ww = mask.shape
    ice = mask & np.isfinite(bed)
    S = np.where(ice, np.inf, bed)          # ice surface; outside ice S = B (margin condition)
    k1 = tau * cell / (RHO * G)
    nb = [(-1, 0, 1.0), (1, 0, 1.0), (0, -1, 1.0), (0, 1, 1.0),
          (-1, -1, math.sqrt(2)), (-1, 1, math.sqrt(2)), (1, -1, math.sqrt(2)), (1, 1, math.sqrt(2))]
    B = bed; done = ~ice; heap = []
    def relax(i, j, Sj, Hj):
        for dy, dx, dd in nb:
            y, x = i + dy, j + dx
            if 0 <= y < Hh and 0 <= x < Ww and not done[y, x]:
                a = B[y, x] - Sj; b = Hj; k = k1 * dd
                # surface step over the mean thickness: (S_i - S_j) (H_i + H_j) / 2 = k  (exact Nye on a flat bed)
                h = (-(a + b) + math.sqrt((a - b) ** 2 + 8 * k)) / 2
                if h <= 0: h = 2 * k / (a + math.sqrt(a * a + 4 * k))      # steep rise of the bed: thin ice
                s = B[y, x] + h
                if s < S[y, x]: S[y, x] = s; heapq.heappush(heap, (s, y, x))
    ys, xs = np.nonzero(ice)
    for y, x in zip(ys.tolist(), xs.tolist()):          # seed from the margin (non-ice neighbours of ice cells)
        for dy, dx, _ in nb:
            yy, xx = y + dy, x + dx
            if 0 <= yy < Hh and 0 <= xx < Ww and done[yy, xx] and np.isfinite(B[yy, xx]):
                relax(yy, xx, B[yy, xx], 0.0)
    while heap:
        s, y, x = heapq.heappop(heap)
        if done[y, x] or s > S[y, x]: continue
        done[y, x] = True; relax(y, x, s, s - B[y, x])
    Hice = np.where(ice & np.isfinite(S), S - B, 0.0)
    return Hice


def pack(a):
    import zlib
    c = zlib.compressobj(9, zlib.DEFLATED, -15)
    return base64.b64encode(c.compress(a.tobytes()) + c.flush()).decode()


def encode(Hice):
    """Whole metres (uint16), at least 1 where there is ice."""
    return np.where(Hice > 0, np.clip(np.floor(Hice + 0.5), 1, 65535), 0).astype("<u2")


def write(out_dir, sid, grid, gs, tau, stats, log, meta):
    fn = os.path.join(out_dir, f"{sid}_ice.json")
    d = dict(gs=gs, nx=grid.shape[1], ny=grid.shape[0], h=pack(grid), dtype="u2", unit=1, tau=tau, stats=stats,
             src="GLACIMONTIS (Zenodo 15600659, CC BY 4.0); plastic-ice thickness, " + time.strftime("%Y-%m-%d"))
    json.dump(d, open(fn, "w"), separators=(",", ":"))
    sfn = os.path.join(out_dir, f"{sid}.json"); s = json.load(open(sfn)); s["ice"] = 1
    json.dump(s, open(sfn + ".tmp", "w"), separators=(",", ":")); os.replace(sfn + ".tmp", sfn)
    log(f"{sid}: wrote {fn} ({os.path.getsize(fn) / 1e3:.0f} kB) {stats}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dem", required=True); ap.add_argument("--work", default="/srv/data/glacial")
    ap.add_argument("--out", default="/srv/www/data"); ap.add_argument("--meta", default=os.path.join(HERE, "scenes_meta.json"))
    ap.add_argument("--only", default=""); ap.add_argument("--tau", type=float, default=100e3, help="basal shear stress, Pa")
    a = ap.parse_args(); log = lambda s: print(s, flush=True)
    import rasterio
    feats = outlines(a.work, log)
    meta = json.load(open(a.meta))
    ids = [s for s in (a.only.split(",") if a.only else list(meta.keys()) + ["tasmania"]) if s]
    with rasterio.open(a.dem) as ds:
        for sid in ids:
            sfn = os.path.join(a.out, f"{sid}.json")
            if not os.path.exists(sfn): log(f"{sid}: no {sfn}"); continue
            sc = json.load(open(sfn)); R = sc["r"]; E0, N1 = sc["E0"], sc["N1"]; Wm, Hm = sc["nx"] * R, sc["ny"] * R
            if R == 25:       # scene: model on a padded 100 m window, crop to the scene
                pe0, pn1 = E0 - PAD, N1 + PAD; W, H = int((Wm + 2 * PAD) / GS), int((Hm + 2 * PAD) / GS)
                mask = rasterise(feats, pe0, pn1, W, H, GS)
                if not mask[int(PAD / GS):-int(PAD / GS), int(PAD / GS):-int(PAD / GS)].any(): log(f"{sid}: no ice"); continue
                t = time.time(); Hice = thickness(mask, bed100(ds, pe0, pn1, W, H), GS, a.tau)
                p = int(PAD / GS); crop = Hice[p:H - p, p:W - p]; grid = encode(crop); gs = 100
            else:             # statewide (1 km): model at 100 m over the glaciers' bounding box, then 10 x 10 blocks
                f = int(R / GS); W, H = int(Wm / GS), int(Hm / GS)
                full = rasterise(feats, E0, N1, W, H, GS)
                if not full.any(): log(f"{sid}: no ice"); continue
                ys, xs = np.nonzero(full)
                y0 = max(0, (ys.min() - 50) // f * f); y1 = min(H, (ys.max() + 50) // f * f + f)
                x0 = max(0, (xs.min() - 50) // f * f); x1 = min(W, (xs.max() + 50) // f * f + f)
                t = time.time(); sub = thickness(full[y0:y1, x0:x1], bed100(ds, E0 + x0 * GS, N1 - y0 * GS, x1 - x0, y1 - y0), GS, a.tau)
                blk = sub.reshape((y1 - y0) // f, f, (x1 - x0) // f, f); n = (blk > 0).sum(axis=(1, 3)); s = blk.sum(axis=(1, 3))
                crop = np.zeros((H // f, W // f)); crop[y0 // f:y1 // f, x0 // f:x1 // f] = np.where(n * 2 >= f * f, s / np.maximum(n, 1), 0.0)
                grid = encode(crop); gs = R
            stats = dict(area_km2=round(float((crop > 0).sum() * gs * gs / 1e6), 1), hmax=round(float(crop.max())),
                         hmean=round(float(crop[crop > 0].mean())) if (crop > 0).any() else 0, secs=round(time.time() - t, 1))
            write(a.out, sid, grid, gs, a.tau, stats, log, meta)


if __name__ == "__main__":
    main()
