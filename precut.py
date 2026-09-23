#!/usr/bin/env python3
"""
precut.py - build per-scene data files for Tasmania in Bricks from the LIST 25 m DEM.

Engine only (no UI). Reproduces the browser pipeline used to build scenes.json:
  1. DEM window (25 m, GDA94 / MGA55) from the statewide mosaic (VRT or COG); no-data -> sea (id 250)
  2. Lakes from LIST Hydrographic Areas (TopographyAndRelief/38, HYDARTY1='Water Body'),
     rasterised with 4x4 sub-samples per 25 m cell (even-odd rule); water if >= 8/16 covered;
     a named lake smaller than one cell keeps its best cell if >= 4/16
  3. Urban from LIST Landuse Live (CadastreAndAdministrative/77, ALUM):
     541 -> 1 (residential); 530-599 except 542-545, 553 -> 2 (commercial/industrial/transport)
  4. Pack: Int16 row-delta metres + Uint8 lake id + Uint8 urban, raw deflate, base64
Curated metadata (labels, spot heights, lake names/levels, r0) is taken from scenes_meta.json.

Usage:
  python3 precut.py --dem /srv/data/dem/tas_dem25.tif --meta scenes_meta.json --out /srv/www/data
  python3 precut.py ... --only hobart,gorge
  python3 precut.py ... --verify scenes.json    # compare against a previous bundle
"""
import argparse, base64, json, math, sys, time, zlib
import numpy as np
import rasterio
from rasterio.windows import Window
import requests

LIST = "https://services.thelist.tas.gov.au/arcgis/rest/services"
SEA = 250
CELL = 25.0
SUB = 6.25            # 4x4 sub-samples per 25 m cell
P = 1_000_000_007


# ---------------------------------------------------------------- LIST REST
def query(layer_url, where, env, out_fields, session):
    """All features intersecting the envelope, in ascending OBJECTID order, geometry in EPSG:28355."""
    base = f"{LIST}/{layer_url}/query"
    common = dict(where=where, geometry=env, geometryType="esriGeometryEnvelope", inSR="28355",
                  spatialRel="esriSpatialRelIntersects", f="json")
    r = session.post(base, data=dict(common, returnIdsOnly="true"), timeout=120); r.raise_for_status()
    ids = sorted(r.json().get("objectIds") or [])
    feats = []
    for k in range(0, len(ids), 150):
        d = dict(objectIds=",".join(map(str, ids[k:k + 150])), outFields=out_fields,
                 outSR="28355", returnGeometry="true", f="json")
        j = session.post(base, data=d, timeout=300).json()
        if "error" in j: raise RuntimeError(j["error"])
        feats += j["features"]
    if len(feats) != len(ids): raise RuntimeError(f"query count {len(feats)}/{len(ids)}")
    return feats


# ---------------------------------------------------------------- rasterisation (identical to browser cover())
def cover(rings, E0, N1, W, H):
    """Yield (cell index, n of 16 sub-samples inside) for one polygon (even-odd over all rings)."""
    xs_all = [p[0] for r in rings for p in r]; ys_all = [p[1] for r in rings for p in r]
    xmin, xmax, ymin, ymax = min(xs_all), max(xs_all), min(ys_all), max(ys_all)
    jA = max(0, math.floor((N1 - ymax) / SUB - 0.5)); jB = min(4 * H - 1, math.ceil((N1 - ymin) / SUB - 0.5))
    if jB < jA: return
    kA = max(0, math.floor((xmin - E0) / SUB - 0.5)); kB = min(4 * W - 1, math.ceil((xmax - E0) / SUB - 0.5))
    if kB < kA: return
    rows = [[] for _ in range(jB - jA + 1)]
    for r in rings:
        for t in range(len(r) - 1):
            (x1, y1), (x2, y2) = r[t][:2], r[t + 1][:2]
            if y1 == y2: continue
            lo, hi = min(y1, y2), max(y1, y2)
            ja = math.ceil((N1 - hi) / SUB - 0.5); jb = math.floor((N1 - lo) / SUB - 0.5)
            for j in range(max(ja, jA), min(jb, jB) + 1):
                Y = N1 - (j + 0.5) * SUB
                if Y < lo or Y >= hi: continue
                rows[j - jA].append(x1 + (Y - y1) * (x2 - x1) / (y2 - y1))
    cx0, cy0 = kA // 4, jA // 4
    cw, ch = kB // 4 - cx0 + 1, jB // 4 - cy0 + 1
    cnt = np.zeros(ch * cw, np.int32)
    for jj, xs in enumerate(rows):
        if len(xs) < 2: continue
        xs.sort(); cy = ((jj + jA) >> 2) - cy0
        for t in range(0, len(xs) - 1, 2):
            ka = max(kA, math.ceil((xs[t] - E0) / SUB - 0.5)); kb = min(kB, math.ceil((xs[t + 1] - E0) / SUB - 0.5) - 1)
            if kb < ka: continue
            cols = np.arange(ka, kb + 1) >> 2
            np.add.at(cnt, cy * cw + cols - cx0, 1)
    for yy, xx in zip(*np.nonzero(cnt.reshape(ch, cw))):
        yield int((yy + cy0) * W + xx + cx0), int(cnt[yy * cw + xx])


# ---------------------------------------------------------------- DEM window
def read_window(ds, E0, N1, W, H):
    t = ds.transform
    if abs(t.a - CELL) > 1e-6 or abs(t.e + CELL) > 1e-6: raise RuntimeError("DEM is not 25 m")
    c0 = (E0 - t.c) / CELL; r0 = (t.f - N1) / CELL
    if abs(c0 - round(c0)) > 1e-3 or abs(r0 - round(r0)) > 1e-3: raise RuntimeError("window not on 25 m grid")
    win = Window(round(c0), round(r0), W, H)
    nod = ds.nodata if ds.nodata is not None else -9999
    M = ds.read(1, window=win, boundless=True, fill_value=nod).astype(np.float64)
    M[M < -9000] = np.nan
    return M


def jsround(a):  # Math.round semantics (half up), not numpy banker's rounding
    return np.floor(a + 0.5)


def rolling(a):
    h = 0
    for v in a.ravel().tolist(): h = (h * 31 + v) % P
    return h


def pack(Z, L, U):
    H, W = Z.shape
    d = np.empty_like(Z)
    d[:, 1:] = Z[:, 1:] - Z[:, :-1]
    d[1:, 0] = Z[1:, 0] - Z[:-1, 0]
    d[0, 0] = Z[0, 0]
    raw = d.astype("<i2").tobytes() + L.astype(np.uint8).tobytes() + U.astype(np.uint8).tobytes()
    c = zlib.compressobj(9, zlib.DEFLATED, -15)
    return base64.b64encode(c.compress(raw) + c.flush()).decode()


def unpack_z(z, W, H):
    raw = zlib.decompress(base64.b64decode(z), -15)
    d = np.frombuffer(raw[:W * H * 2], "<i2").reshape(H, W).astype(np.int64)
    Z = d.copy(); Z[:, 0] = np.cumsum(d[:, 0]); Z = np.cumsum(Z, axis=1)
    L = np.frombuffer(raw[W * H * 2:W * H * 3], np.uint8).reshape(H, W)
    U = (np.frombuffer(raw[W * H * 3:W * H * 4], np.uint8).reshape(H, W)
         if len(raw) >= W * H * 4 else np.zeros((H, W), np.uint8))
    return Z, L, U


# ---------------------------------------------------------------- one scene
def build_scene(sid, m, ds, session, log):
    E0, N1, W, H = m["E0"], m["N1"], m["nx"], m["ny"]
    lake_names = [n.upper() for n in m.get("lakes", [])]
    E1, N0 = E0 + W * CELL, N1 - H * CELL
    env = f"{E0},{N0},{E1},{N1}"
    M = read_window(ds, E0, N1, W, H)
    sea = np.isnan(M)
    Z = np.where(sea, 0, jsround(np.nan_to_num(M))).astype(np.int64)
    L = np.where(sea, SEA, 0).astype(np.int64).ravel()
    U = np.zeros(W * H, np.int64)
    log(f"{sid}: DEM {W}x{H}, sea {int(sea.sum())}, max {int(Z.max())} m")

    lf = query("Public/TopographyAndRelief/MapServer/38", "HYDARTY1='Water Body'", env, "NAME", session)
    cov = np.zeros(W * H, np.int64); best = {}
    for q in lf:
        name = str(q["attributes"].get("NAME") or "").upper()
        k = lake_names.index(name) + 1 if name in lake_names else 99
        for i, n in cover(q["geometry"]["rings"], E0, N1, W, H):
            if L[i] == SEA: continue
            if n >= 8 and n > cov[i]: L[i] = k; cov[i] = n
            if k != 99 and (k not in best or n > best[k][1]): best[k] = (i, n)
    for k in sorted(best):
        i, n = best[k]
        if not (L == k).any() and n >= 4 and L[i] != SEA: L[i] = k
    log(f"{sid}: lakes {len(lf)} polygons")

    def cls(c):
        if c == 541: return 1
        if 530 <= c < 600 and c not in (542, 543, 544, 545, 553): return 2
        return 0
    uf = [q for q in query("Public/CadastreAndAdministrative/MapServer/77", "LU_CODEN>=530 AND LU_CODEN<600",
                           env, "LU_CODEN", session) if cls(q["attributes"]["LU_CODEN"]) > 0]
    u1 = np.zeros(W * H, np.int64); u2 = np.zeros(W * H, np.int64)
    for q in uf:
        c = cls(q["attributes"]["LU_CODEN"]); tgt = u1 if c == 1 else u2
        for i, n in cover(q["geometry"]["rings"], E0, N1, W, H):
            tgt[i] = min(16, tgt[i] + n)
    sel = (L != SEA) & (u1 + u2 >= 8)
    U[sel] = np.where(u1[sel] >= u2[sel], 1, 2)
    log(f"{sid}: urban {len(uf)} polygons, {int(sel.sum())} cells")

    L = L.reshape(H, W); U = U.reshape(H, W)
    out = {k: v for k, v in m.items() if k not in ("z", "u")}
    out.update(r=25, nx=W, ny=H, sea=int(sea.sum()), z=pack(Z, L, U))
    out["_check"] = dict(hm=rolling(Z), hl=rolling(L), hu=rolling(U), zmax=int(Z.max()),
                         built=time.strftime("%Y-%m-%dT%H:%M:%S%z"))
    return out, Z, L, U


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dem", required=True, help="statewide 25 m mosaic (VRT or GeoTIFF, EPSG:28355)")
    ap.add_argument("--meta", required=True, help="scenes_meta.json (curated labels, lakes, extents)")
    ap.add_argument("--out", required=True, help="output directory, e.g. /srv/www/data")
    ap.add_argument("--only", default="", help="comma-separated scene ids")
    ap.add_argument("--verify", default="", help="previous scenes.json to compare against")
    a = ap.parse_args()
    meta = json.load(open(a.meta))
    ids = [s for s in (a.only.split(",") if a.only else meta.keys()) if s]
    prev = json.load(open(a.verify)) if a.verify else {}
    import os; os.makedirs(a.out, exist_ok=True)
    log = lambda s: print(s, flush=True)
    s = requests.Session(); s.headers["User-Agent"] = "tas-bricks-precut/1.0"
    index = {}
    with rasterio.open(a.dem) as ds:
        if ds.crs and ds.crs.to_epsg() not in (28355, None): sys.exit(f"DEM CRS {ds.crs} is not EPSG:28355")
        for sid in ids:
            out, Z, L, U = build_scene(sid, meta[sid], ds, s, log)
            if sid in prev and prev[sid].get("r") == 25 and prev[sid]["nx"] == out["nx"]:
                pZ, pL, pU = unpack_z(prev[sid]["z"], out["nx"], out["ny"])
                log(f"{sid}: verify  |dZ|max {int(np.abs(pZ - Z).max())} m, dZ!=0 {int((pZ != Z).sum())} cells, "
                    f"lake diff {int((pL != L).sum())}, urban diff {int((pU != U).sum())}")
            fn = os.path.join(a.out, f"{sid}.json")
            with open(fn + ".tmp", "w") as f: json.dump(out, f, separators=(",", ":"))
            os.replace(fn + ".tmp", fn)
            index[sid] = dict(bytes=os.path.getsize(fn), **out["_check"])
            log(f"{sid}: wrote {fn} ({index[sid]['bytes']/1e3:.0f} kB)")
    idx = os.path.join(a.out, "index.json")
    old = json.load(open(idx)) if os.path.exists(idx) else {}
    old.update(index); json.dump(old, open(idx, "w"), indent=1)


if __name__ == "__main__":
    main()
