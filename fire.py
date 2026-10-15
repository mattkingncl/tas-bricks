#!/usr/bin/env python3
"""
fire.py - fire history for Tasmania in Bricks, from theLIST Fire History - All
(Public/EmergencyManagementPublic/MapServer/1; fields IGN_SEASON e.g. 19791980, FIRE_TYPE, FIRE_NAME, IGN_DATE).

Each perimeter is rasterised with the same 4 x 4 sub-samples per 25 m cell as the lakes (precut.cover); a cell is
burnt by a fire when >= 8/16 sub-samples are inside. Per cell the K most recent fires are kept (most recent first).

Output data/<id>_fire.json:
  fires: [[season start year, type 0 bushfire | 1 planned burn | 2 unknown, name, km2 burnt within the scene], ...]
  K, f: base64 raw-deflate Uint16 (little-endian) [ny*nx*K] of 1-based fire ids, 0 = none
and sets "fire": 1 in data/<id>.json (scenes_meta.json is only read, for the scene list).

Usage:
  python3 fire.py --out /srv/www/data [--only hobart,gorge]
"""
import argparse, base64, datetime, json, os, sys, time, zlib
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
LAYER = "Public/EmergencyManagementPublic/MapServer/1"
KMAX = 8


def season_of(a):
    s = str(a.get("IGN_SEASON") or "").strip()
    if len(s) >= 4 and s[:4].isdigit() and 1850 < int(s[:4]) < 2100: return int(s[:4])
    d = a.get("IGN_DATE")
    if d:
        t = datetime.datetime.fromtimestamp(d / 1000, datetime.timezone.utc)
        return t.year if t.month >= 7 else t.year - 1       # fire season runs July-June
    return None


def type_of(a):
    t = str(a.get("FIRE_TYPE") or "").lower()
    return 1 if "plan" in t else 0 if "bush" in t or "wild" in t else 2


def build(sid, sc, session, log):
    from precut import query, cover
    E0, N1, W, H = sc["E0"], sc["N1"], sc["nx"], sc["ny"]
    env = f"{E0},{N1 - H * 25},{E0 + W * 25},{N1}"
    feats = query(LAYER, "1=1", env, "IGN_SEASON,FIRE_TYPE,FIRE_NAME,IGN_DATE", session)
    cells = {}      # cell -> [(season, date, fire idx)]
    fires = []
    nos = 0
    for q in feats:
        a = q["attributes"]; s = season_of(a)
        if s is None or not q.get("geometry"): nos += 1; continue
        k = len(fires); n = 0
        for i, c in cover(q["geometry"]["rings"], E0, N1, W, H):
            if c >= 8: cells.setdefault(i, []).append((s, a.get("IGN_DATE") or 0, k)); n += 1
        name = " ".join(w.capitalize() for w in str(a.get("FIRE_NAME") or "").split())
        fires.append([s, type_of(a), name, n])
    used = sorted({k for v in cells.values() for _, _, k in v})
    remap = {k: j + 1 for j, k in enumerate(used)}
    table = [[fires[k][0], fires[k][1], fires[k][2], round(fires[k][3] * 625 / 1e6, 3)] for k in used]
    K = min(KMAX, max((len(v) for v in cells.values()), default=0))
    f = np.zeros((H * W, max(K, 1)), np.uint16)
    trunc = 0
    for i, v in cells.items():
        v.sort(key=lambda t: (-t[0], -t[1]))
        trunc += max(0, len(v) - K)
        for j, (_, _, k) in enumerate(v[:K]): f[i, j] = remap[k]
    c = zlib.compressobj(9, zlib.DEFLATED, -15)
    d = dict(K=max(K, 1), fires=table, f=base64.b64encode(c.compress(f.astype("<u2").tobytes()) + c.flush()).decode(),
             src="theLIST Fire History - All, " + time.strftime("%Y-%m-%d"))
    burnt = len(cells)
    log(f"{sid}: {len(feats)} perimeters ({nos} without season), {len(table)} burn >= 1 cell, K={K} "
        f"({trunc} older cell-fires dropped), burnt cells {burnt} ({100 * burnt / (W * H):.0f}%), "
        f"seasons {min((t[0] for t in table), default='-')}-{max((t[0] for t in table), default='-')}")
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/srv/www/data"); ap.add_argument("--meta", default=os.path.join(HERE, "scenes_meta.json"))
    ap.add_argument("--only", default="")
    a = ap.parse_args(); log = lambda s: print(s, flush=True)
    import requests
    s = requests.Session(); s.headers["User-Agent"] = "tas-bricks-fire/1.0"
    meta = json.load(open(a.meta))
    ids = [x for x in (a.only.split(",") if a.only else meta.keys()) if x]
    for sid in ids:
        sfn = os.path.join(a.out, f"{sid}.json")
        if not os.path.exists(sfn): log(f"{sid}: no {sfn}"); continue
        sc = json.load(open(sfn))
        if sc.get("r", 25) != 25: continue
        try: d = build(sid, sc, s, log)
        except Exception as e: log(f"{sid}: FAILED {e}"); continue
        if not d["fires"]: log(f"{sid}: no fires mapped"); continue
        fn = os.path.join(a.out, f"{sid}_fire.json"); json.dump(d, open(fn, "w"), separators=(",", ":"))
        sc["fire"] = 1; json.dump(sc, open(sfn + ".tmp", "w"), separators=(",", ":")); os.replace(sfn + ".tmp", sfn)
        log(f"{sid}: wrote {fn} ({os.path.getsize(fn) / 1e3:.0f} kB)")


if __name__ == "__main__":
    main()
