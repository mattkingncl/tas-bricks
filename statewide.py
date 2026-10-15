#!/usr/bin/env python3
"""
statewide.py - the low-resolution "All of Tasmania" scene (1 km native; page tiers 8/4/2/1 km) for the
Water drop mode and the ice-age sea level.

Grid: E 160000-640000, N 5160000-5760000 (MGA55), i.e. Tasmania, King and Flinders Islands, Bass Strait and the
Victorian coast. Built on a 250 m grid, then 4 x 4 blocks:
  * Tasmania: LIST 25 m DEM, exact block mean of valid cells; a 250 m cell is land when >= 50% valid
  * elsewhere: AusBathyTopo 250 m (bathy.py): sea floor clipped to [-150, -1] m, and land (> 0 m) only where
    more than 5 km from the Tasmanian DEM (the Victorian mainland; Tasmanian coastline comes from the DEM)
  * a 1 km cell is sea when >= 8 of its 16 cells are sea; its height is the mean of its majority class
Lakes: major named lakes from LIST Hydrographic Areas (layer 38), centre-sampled at 250 m, lake when >= 8/16.

Usage:
  python3 statewide.py --dem /srv/data/dem/tas_dem25.tif --bathy /srv/data/bathy/tas_bathy_mga.tif --out /srv/www/data
"""
import argparse, json, os, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
E0, N1, E1, N0 = 160000, 5760000, 640000, 5160000
G, R = 250, 1000
LAKES = ["Great Lake", "Lake Gordon", "Lake Pedder", "Lake Burbury", "Lake St Clair", "Arthurs Lake", "Lake King William",
         "Lake Echo", "Lake Mackintosh", "Lake Rowallan", "Lake Murchison", "Lake Pieman", "Lake Sorell", "Lake Crescent",
         "Woods Lake", "Lake Plimsoll", "Lake Margaret", "Lake Barrington", "Lake Meadowbank", "Lake Cethana",
         "Lake Rosebery", "Lake Leake", "Tooms Lake", "Lake Augusta", "Lake Mackenzie", "Lake Parangana", "Lake Gairdner",
         "Bronte Lagoon", "Lake Binney", "Dee Lagoon", "Laughing Jack Lagoon", "Lake Dulverton", "Lake Selina"]
# [name, lat, lon, label text, water]; peak heights are LIST spot heights (m AHD)
PLACES = [
    ["Hobart", -42.8821, 147.3272, "", 0], ["Launceston", -41.4332, 147.1441, "", 0], ["Devonport", -41.1770, 146.3510, "", 0],
    ["Burnie", -41.0556, 145.9037, "", 0], ["Queenstown", -42.0806, 145.5570, "", 0], ["Strahan", -42.1536, 145.3276, "", 0],
    ["St Helens", -41.3207, 148.2398, "", 0], ["Mount Ossa", -41.8710, 146.0330, "1617 m", 0],
    ["Cradle Mountain", -41.6848, 145.9511, "1545 m", 0], ["Ben Lomond", -41.5392, 147.6636, "1572 m", 0],
    ["kunanyi / Mt Wellington", -42.8960, 147.2372, "1271 m", 0], ["Frenchmans Cap", -42.2735, 145.8285, "1446 m", 0],
    ["Federation Peak", -43.2667, 146.4583, "1224 m", 0], ["Great Lake", -41.95, 146.73, "", 1],
    ["Macquarie Harbour", -42.30, 145.38, "", 1], ["Bass Strait", -39.90, 146.20, "", 1],
    ["King Island", -39.87, 143.98, "", 0], ["Flinders Island", -40.05, 148.03, "", 0], ["Wilsons Promontory", -39.03, 146.37, "", 0]]
# where rivers meet the sea (named in the Water drop readout when the drop reaches the sea within 15 km)
OUTLETS = [["the Derwent estuary", -42.83, 147.25], ["the Tamar / kanamaluka", -41.25, 146.95], ["the Huon estuary", -43.10, 147.03],
           ["Macquarie Harbour (Gordon & King rivers)", -42.35, 145.45], ["the Pieman River mouth", -41.66, 144.92],
           ["the Arthur River mouth", -41.05, 144.66], ["the Mersey at Devonport", -41.17, 146.36],
           ["the Forth River mouth", -41.16, 146.25], ["the Leven at Ulverstone", -41.15, 146.17], ["the Emu at Burnie", -41.05, 145.91],
           ["the Inglis at Wynyard", -40.99, 145.73], ["the Duck at Smithton", -40.85, 145.13], ["Ringarooma Bay", -40.90, 147.93],
           ["Georges Bay, St Helens", -41.30, 148.28], ["Moulting Lagoon (Swan & Apsley)", -42.03, 148.18],
           ["the Prosser at Orford", -42.56, 147.87], ["Pitt Water (Coal River)", -42.80, 147.50],
           ["Port Davey & Bathurst Harbour", -43.30, 145.95], ["the Henty River mouth", -42.03, 145.24],
           ["Port Sorell (Rubicon River)", -41.16, 146.55], ["the Little Swanport estuary", -42.33, 148.00]]


def dem250(ds, log):
    """Mean of valid 25 m DEM cells per 250 m cell, and the number valid (0-100), over the statewide grid."""
    from rasterio.windows import Window
    W, H = (E1 - E0) // G, (N1 - N0) // G
    t = ds.transform; c0 = round((E0 - t.c) / 25); r0 = round((t.f - N1) / 25)
    nod = ds.nodata if ds.nodata is not None else -9999
    S = np.zeros((H, W)); C = np.zeros((H, W), np.int32)
    for j in range(0, H, 40):
        h = min(40, H - j)
        M = ds.read(1, window=Window(c0, r0 + j * 10, W * 10, h * 10), boundless=True, fill_value=nod).astype(np.float64)
        ok = (M > -9000) & (M != nod)
        S[j:j + h] = np.where(ok, M, 0).reshape(h, 10, W, 10).sum(axis=(1, 3))
        C[j:j + h] = ok.reshape(h, 10, W, 10).sum(axis=(1, 3))
    log(f"DEM: {int((C >= 50).sum())} land cells of 250 m")
    return np.where(C > 0, S / np.maximum(C, 1), np.nan), C


def grow(a, n):
    b = a.copy()
    for _ in range(n):
        c = b.copy(); c[1:] |= b[:-1]; c[:-1] |= b[1:]; c[:, 1:] |= b[:, :-1]; c[:, :-1] |= b[:, 1:]; b = c
    return b


def lakes250(session, log, W, H):
    from precut import query
    from rasterio.features import rasterize
    from affine import Affine
    names = [n.upper() for n in LAKES]
    where = "HYDARTY1='Water Body' AND UPPER(NAME) IN (" + ",".join("'" + n.replace("'", "''") + "'" for n in names) + ")"
    feats = query("Public/TopographyAndRelief/MapServer/38", where, f"{E0},{N0},{E1},{N1}", "NAME", session)
    L = np.zeros((H, W), np.uint8); found = []
    for q in feats:
        nm = str(q["attributes"].get("NAME") or "").upper()
        if nm not in names or not q.get("geometry"): continue
        if nm not in found: found.append(nm)
        k = found.index(nm) + 1
        geom = {"type": "Polygon", "coordinates": q["geometry"]["rings"]}
        m = rasterize([(geom, 1)], out_shape=(H, W), transform=Affine(G, 0, E0, 0, -G, N1), fill=0, dtype="uint8")
        L[m > 0] = k
    log(f"lakes: {len(feats)} polygons, {len(found)} named lakes")
    return L, [LAKES[names.index(n)] for n in found]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dem", required=True); ap.add_argument("--bathy", required=True)
    ap.add_argument("--out", default="/srv/www/data"); ap.add_argument("--no-lakes", action="store_true")
    a = ap.parse_args(); log = lambda s: print(s, flush=True)
    import rasterio, requests
    from rasterio.warp import transform as xy
    from precut import sample_raster, fill_nan, pack, rolling, jsround, SEA, BED_MIN, BED_MAX
    W, H = (E1 - E0) // G, (N1 - N0) // G
    t = time.time()
    with rasterio.open(a.dem) as ds: Z, C = dem250(ds, log)
    with rasterio.open(a.bathy) as bds: B = sample_raster(bds, E0, N1, W, H, G)
    log(f"AusBathyTopo on 250 m grid: nodata {np.isnan(B).mean():.3f}, min {np.nanmin(B):.0f}, max {np.nanmax(B):.0f}")
    B = fill_nan(B)
    tas = C >= 50
    near = grow(C > 0, 20)                                           # within 5 km of the Tasmanian DEM
    main_land = ~near & (B > 0)
    land = tas | main_land
    hgt = np.where(tas, Z, np.where(main_land, B, np.clip(B, BED_MIN, BED_MAX)))
    Lk = np.zeros((H, W), np.uint8); lake_names = []
    if not a.no_lakes:
        s = requests.Session(); s.headers["User-Agent"] = "tas-bricks-statewide/1.0"
        try: Lk, lake_names = lakes250(s, log, W, H)
        except Exception as e: log(f"lakes: FAILED ({e}); continuing without lakes")
    Lk[~land] = 0
    # 4 x 4 blocks -> 1 km
    f = R // G; w, h = W // f, H // f
    blk = lambda A: A.reshape(h, f, w, f)
    nland = blk(land).sum(axis=(1, 3)); sea = nland * 2 < f * f
    lsum = np.where(blk(land), blk(hgt), 0).sum(axis=(1, 3)); ssum = np.where(blk(~land), blk(hgt), 0).sum(axis=(1, 3))
    Z1 = np.where(sea, ssum / np.maximum(f * f - nland, 1), lsum / np.maximum(nland, 1))
    L1 = np.where(sea, SEA, 0).astype(np.int64)
    for k in range(1, len(lake_names) + 1):
        n = (blk(Lk) == k).sum(axis=(1, 3)); L1[(n * 2 >= f * f) & ~sea] = k
    Zi = jsround(Z1).astype(np.int64); U = np.zeros((h, w), np.int64)
    X = lambda lat, lon: [round(v) for v in (lambda e, n: (e[0], n[0]))(*xy("EPSG:4326", "EPSG:28355", [lon], [lat]))]
    labels = []
    for nm, la, lo, txt, wt in PLACES:
        e, n = X(la, lo)
        if E0 <= e < E1 and N0 <= n < N1: labels.append([nm, e, n, txt, wt])
    out = dict(E0=E0, N1=N1, r=R, r0=2 * R, nx=w, ny=h, sea=int(sea.sum()), bathy=1,
               lev={str(k): -1 for k in range(1, len(lake_names) + 1)}, lakes=lake_names,
               spots=[], labels=labels,   # no spot heights: at 1-8 km a summit value would make a needle
               outlets=[[nm, *X(la, lo)] for nm, la, lo in OUTLETS], z=pack(Zi, L1, U))
    out["_check"] = dict(hm=rolling(Zi), hl=rolling(L1), zmax=int(Zi.max()), zmin=int(Zi.min()), built=time.strftime("%Y-%m-%dT%H:%M:%S%z"))
    fn = os.path.join(a.out, "tasmania.json")
    json.dump(out, open(fn + ".tmp", "w"), separators=(",", ":")); os.replace(fn + ".tmp", fn)
    idx = os.path.join(a.out, "index.json"); old = json.load(open(idx)) if os.path.exists(idx) else {}
    old["tasmania"] = dict(bytes=os.path.getsize(fn), **out["_check"]); json.dump(old, open(idx, "w"), indent=1)
    log(f"tasmania: {w}x{h} km, sea {int(sea.sum())} cells, mainland cells {int(main_land.sum())} (250 m), "
        f"z {int(Zi.min())}..{int(Zi.max())} m, lakes {len(lake_names)}, wrote {fn} ({os.path.getsize(fn) / 1e3:.0f} kB) in {time.time() - t:.0f} s")


if __name__ == "__main__":
    main()
