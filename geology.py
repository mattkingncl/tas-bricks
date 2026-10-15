#!/usr/bin/env python3
"""
geology.py - surface and subsurface geology for Tasmania in Bricks (engine only, no UI).

Surface: MRT geological polygons (LIST Public/GeologicalAndSoils: 14 = 1:25k, 16 = 1:250k fallback),
rasterised with 4x4 sub-samples per 25 m cell; 1:25k wins where it covers >= 8/16 of the cell.

Subsurface ("2.5D layer cake", indicative):
  * Units are classed as cover (Quaternary), layered (Tertiary, Jurassic dolerite, Triassic, Permian:
    near-flat-lying in Tasmania) or basement (older, folded).
  * Layered units are ordered young -> old (dolerite sill treated as the top of the sequence).
    For each layer k the elevation of its BASE, B_k(x, y), is interpolated (thin-plate spline, smoothed)
    from the DEM elevation of every mapped contact between layer i (above) and layer j (below):
    B_i = ... = B_(j-1) = z_contact (the layers in between are absent there).
  * The browser enforces the surface map per model cell: where layer i is mapped,
    B_m >= ground for m < i and B_m <= ground for m >= i; then B_1 >= B_2 >= ... (monotone).
  * Below the lowest base: basement, extruded vertically from the nearest mapped basement unit
    (steeply dipping, folded rocks).
  * Quaternary cover is a veneer of fixed thickness (default 10 m) over the modelled bedrock.
Faults are not yet used to split the interpolation.

Output data/<id>_geo.json (fetched by the page only when "Geology" is switched on):
  units   [{sym, desc, cls, col, minage, maxage}]  (index + 1 = unit id)
  layers  [[unit ids in layer k], ...]  young -> old
  su      surface unit per 25 m cell (uint8, raw deflate, base64)
  bu      basement unit per 25 m cell (uint8, raw deflate, base64)
  bs      base surfaces at gs m (int16 m, K x (gny x gnx), raw deflate, base64), node (0,0) at (E0, N1)
  gs, gnx, gny, tq, src
Usage:
  python3 geology.py --dem /srv/data/dem/tas_dem25.tif --meta scenes_meta.json --out /srv/www/data --only cradle
"""
import argparse, base64, json, math, os, sys, time, zlib
import numpy as np

SUB = 6.25
CELL = 25.0

# ---------------------------------------------------------------- classification
# colour keys must exist in the page palette (COL in tas-template.html)
def classify(sym, desc, minage, maxage):
    s = (sym or '').strip(); d = (desc or '').lower(); a = 0.5 * ((minage or 0) + (maxage or 0))
    if s in ('', 'Unknown') or (not minage and not maxage):       return 'unknown', 'lbg'
    if a < 2.6 or s.startswith('Q'):                               return 'cover', 'tan'
    if 'dolerite' in d or s.startswith('Jd'):                      return 'layer', 'dbg'
    if a < 66:   return 'layer', ('dkbrown' if 'basalt' in d else 'dktan')          # Cenozoic
    if a < 252:  return 'layer', 'nougat'                                            # Triassic
    if a < 310:                                                                     # Permian (Parmeener)
        if 'sandstone' in d:                         return 'layer', 'sandblue'
        if 'diamictite' in d or 'boulder' in d or 'conglomerate' in d: return 'layer', 'dktan'
        return 'layer', 'lbg'
    if 'granite' in d or 'granodiorite' in d:      return 'basement', 'pink'
    if a < 444:  return 'basement', 'olive'                                          # Silurian-Devonian
    if a < 485:  return 'basement', 'mdblue'                                         # Ordovician
    if a < 541:  return 'basement', 'sandgreen'                                      # Cambrian
    return 'basement', ('white' if 'quartzite' in d else 'lavender')                 # Precambrian


def layer_order(units):
    """Group layered units by age into layers, young -> old. Dolerite (intrusive sill) on top."""
    lay = [(i + 1, u) for i, u in enumerate(units) if u['cls'] == 'layer']   # units classed 'absent' are skipped
    keyf = lambda t: (0 if t[1]['col'] == 'dbg' else 1, 0.5 * (t[1]['minage'] + t[1]['maxage']))
    lay.sort(key=keyf)
    layers, cur, curkey = [], [], None
    for uid, u in lay:
        k = (u['sym'][:1], round(0.5 * (u['minage'] + u['maxage']), 1), u['col'])
        if curkey is not None and k != curkey:
            layers.append(cur); cur = []
        cur.append(uid); curkey = k
    if cur: layers.append(cur)
    return layers


# ---------------------------------------------------------------- model
def fit_surface(P, gx, gy, lam=600.0, w0=0.25):
    """Base surface from contact points P (x, y, z): least-squares plane (regional dip of the near-flat
    Tasmanian cover sequence) plus a Gaussian-weighted residual correction that decays to the plane
    away from the data (length scale lam m; w0 = prior weight of the plane). Bounded, no wild extrapolation."""
    A = np.c_[P[:, 0], P[:, 1], np.ones(len(P))]
    if len(P) >= 8 and np.ptp(P[:, 0]) > 200 and np.ptp(P[:, 1]) > 200:
        coef, *_ = np.linalg.lstsq(A, P[:, 2], rcond=None)
        # limit the dip: the Parmeener sequence and dolerite sheets are near-flat (typically < 3 degrees),
        # and a dip fitted to a small cluster of contacts must not be extrapolated across the scene
        g = np.hypot(coef[0], coef[1]); gmax = math.tan(math.radians(3))
        if g > gmax: coef[:2] *= gmax / g; coef[2] = np.mean(P[:, 2] - P[:, 0] * coef[0] - P[:, 1] * coef[1])
    else:
        coef = np.array([0.0, 0.0, float(np.median(P[:, 2]))])
    plane = lambda x, y: coef[0] * x + coef[1] * y + coef[2]
    r = P[:, 2] - plane(P[:, 0], P[:, 1])
    X = np.c_[gx.ravel(), gy.ravel()]
    num = np.zeros(len(X)); den = np.full(len(X), w0)
    for i in range(0, len(P), 256):
        d2 = ((X[:, None, :] - P[None, i:i + 256, :2]) ** 2).sum(-1)
        w = np.exp(-d2 / lam ** 2)
        num += w @ r[i:i + 256]; den += w.sum(1)
    S = plane(X[:, 0], X[:, 1]) + num / den
    # leave-one-in fit statistics at the data points
    d2 = ((P[:, None, :2] - P[None, :, :2]) ** 2).sum(-1); w = np.exp(-d2 / lam ** 2)
    fit = plane(P[:, 0], P[:, 1]) + (w @ r) / (w.sum(1) + w0)
    return S.reshape(gx.shape), dict(dip_deg=round(math.degrees(math.atan(np.hypot(coef[0], coef[1]))), 2),
                                     rms_plane=float(np.sqrt((r ** 2).mean())), rms_fit=float(np.sqrt(((P[:, 2] - fit) ** 2).mean())))


def model(su, dem, units, gs=100.0):
    """su: (H, W) surface unit ids (1-based), dem: (H, W) metres (nan = sea). Returns dict."""
    H, W = su.shape
    present = set(np.unique(su).tolist())
    layers = layer_order([u if (i + 1) in present else dict(u, cls='absent') for i, u in enumerate(units)])
    K = len(layers)
    lay_of = np.zeros(len(units) + 1, np.int16)            # unit id -> layer index 1..K, 0 = not layered
    for k, ids in enumerate(layers):
        for u in ids: lay_of[u] = k + 1
    cls = ['none'] + [u['cls'] for u in units]
    is_base = np.array([c == 'basement' for c in cls])
    L = lay_of[su]
    Lb = np.where(is_base[su], K + 1, L)                   # basement counts as layer K+1
    pts = [[] for _ in range(K)]
    for dy, dx in ((0, 1), (1, 0)):
        a = Lb[:H - dy, :W - dx]; b = Lb[dy:, dx:]
        za = dem[:H - dy, :W - dx]; zb = dem[dy:, dx:]
        ok = (a > 0) & (b > 0) & (a != b) & np.isfinite(za) & np.isfinite(zb)
        for y, x in zip(*np.nonzero(ok)):
            i, j = sorted((int(a[y, x]), int(b[y, x])))
            z = 0.5 * (za[y, x] + zb[y, x])
            E = (x + 0.5 + dx / 2) * CELL; N = (y + 0.5 + dy / 2) * CELL   # scene-local metres (x east, y south)
            for m in range(i, j):
                if m <= K: pts[m - 1].append((E, N, z))
    gnx = int(math.ceil(W * CELL / gs)) + 1; gny = int(math.ceil(H * CELL / gs)) + 1
    gx, gy = np.meshgrid(np.arange(gnx) * gs, np.arange(gny) * gs)
    zmin, zmax = float(np.nanmin(dem)), float(np.nanmax(dem))
    surfaces, stats, prev = [], [], None
    for k in range(K):
        P = np.array(pts[k], float).reshape(-1, 3)
        if len(P) >= 3:
            S, st = fit_surface(P, gx, gy)
        else:
            m = L == k + 1
            S = np.full(gx.shape, float(np.nanmin(dem[m])) - 20 if m.any() else zmin - 50); st = {}
        S = np.clip(S, zmin - 600, zmax + 300)
        if prev is not None: S = np.minimum(S, prev)       # monotone: base of an older layer is lower
        surfaces.append(S); prev = S
        stats.append(dict(layer=k + 1, units=[units[u - 1]['sym'] for u in layers[k]], contacts=int(len(P)), **st))
    from scipy.ndimage import distance_transform_edt
    bm = is_base[su]
    if bm.any():
        _, (iy, ix) = distance_transform_edt(~bm, return_indices=True); bu = su[iy, ix]
    else:
        bu = np.zeros_like(su)
    return dict(layers=layers, surfaces=surfaces, bu=bu, gs=gs, gnx=gnx, gny=gny, stats=stats)


def pack_u8(a):
    c = zlib.compressobj(9, zlib.DEFLATED, -15); return base64.b64encode(c.compress(a.astype(np.uint8).tobytes()) + c.flush()).decode()

def pack_i16(a):
    c = zlib.compressobj(9, zlib.DEFLATED, -15); return base64.b64encode(c.compress(np.round(a).astype('<i2').tobytes()) + c.flush()).decode()


def to_json(res, su, units, tq=10.0, src=''):
    return dict(units=[{k: u[k] for k in ('sym', 'desc', 'cls', 'col', 'minage', 'maxage')} for u in units],
                layers=res['layers'], su=pack_u8(su), bu=pack_u8(res['bu']),
                bs=pack_i16(np.stack(res['surfaces'])) if res['surfaces'] else '', gs=res['gs'],
                gnx=res['gnx'], gny=res['gny'], tq=tq, src=src)


# ---------------------------------------------------------------- data access (VM)
def fetch_units(meta, session, log):
    """Query LIST geology polygons for the scene and rasterise (25k priority, 250k fallback)."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from precut import query, cover
    E0, N1, W, H = meta['E0'], meta['N1'], meta['nx'], meta['ny']
    env = f"{E0 - 500},{N1 - H * CELL - 500},{E0 + W * CELL + 500},{N1 + 500}"
    units, index = [], {}
    def uid(a, scale):
        k = (scale, a.get('SYMBOL'), a.get('RCODE'))
        if k not in index:
            cls, col = classify(a.get('SYMBOL'), a.get('DESCRIPT'), a.get('MINAGE'), a.get('MAXAGE'))
            units.append(dict(sym=a.get('SYMBOL') or '', desc=a.get('DESCRIPT') or '', cls=cls, col=col,
                              minage=a.get('MINAGE') or 0, maxage=a.get('MAXAGE') or 0, scale=scale))
            index[k] = len(units)
        return index[k]
    best = {}
    for layer, scale in ((14, '25k'), (16, '250k')):
        cnt = {}                                  # (cell, unit) -> sub-sample count
        feats = query(f"Public/GeologicalAndSoils/MapServer/{layer}", "1=1", env, "*", session)
        for f in feats:
            u = uid(f['attributes'], scale)
            for i, n in cover(f['geometry']['rings'], E0, N1, W, H):
                cnt[(i, u)] = cnt.get((i, u), 0) + n
        m = {}
        for (i, u), n in cnt.items():
            if n > m.get(i, (0, 0))[1]: m[i] = (u, n)
        tot = {}
        for (i, u), n in cnt.items(): tot[i] = tot.get(i, 0) + n
        best[scale] = (m, tot)
        log(f"geology {scale}: {len(feats)} polygons")
    su = np.zeros(W * H, np.uint8)
    m250, _ = best['250k']; m25, t25 = best['25k']
    for i, (u, n) in m250.items(): su[i] = u
    for i, (u, n) in m25.items():
        if t25.get(i, 0) >= 8: su[i] = u
    return su.reshape(H, W), units


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dem', required=True); ap.add_argument('--meta', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--only', default=''); ap.add_argument('--tq', type=float, default=10.0)
    a = ap.parse_args()
    import rasterio, requests
    from precut import read_window, jsround
    meta = json.load(open(a.meta)); s = requests.Session(); s.headers['User-Agent'] = 'tas-bricks-geology/1.0'
    log = lambda m: print(m, flush=True)
    with rasterio.open(a.dem) as ds:
        for sid in [x for x in (a.only.split(',') if a.only else meta.keys()) if x]:
            m = meta[sid]
            if m.get('r', 25) != 25: continue
            try:
                dem = read_window(ds, m['E0'], m['N1'], m['nx'], m['ny'])
                su, units = fetch_units(m, s, log)
                t = time.time(); res = model(su, dem, units)
                log(f"{sid}: {res['stats']}, {time.time() - t:.1f} s")
                out = to_json(res, su, units, a.tq, src='MRT 1:25k/1:250k geology via LIST, ' + time.strftime('%Y-%m-%d'))
            except Exception as e:
                log(f"{sid}: FAILED {e!r}"); continue
            fn = os.path.join(a.out, f'{sid}_geo.json'); json.dump(out, open(fn, 'w'), separators=(',', ':'))
            log(f"{sid}: wrote {fn} ({os.path.getsize(fn) / 1e3:.0f} kB)")
            sfn = os.path.join(a.out, f'{sid}.json')          # flag the scene so the page loads it
            if os.path.exists(sfn):
                d = json.load(open(sfn)); d['geo'] = 1
                json.dump(d, open(sfn + '.tmp', 'w'), separators=(',', ':')); os.replace(sfn + '.tmp', sfn)


if __name__ == '__main__':
    main()
