#!/usr/bin/env python3
"""
make_site.py - assemble the static site for Caddy.

  www/index.html        page (scene data NOT embedded; fetched from data/<id>.json)
  www/lib/three/...     vendored three.js 0.160.0 (no CDN dependency)
  www/data/<id>.json    per-scene data (from precut.py, or split from an existing scenes.json)

Usage:
  python3 make_site.py --template tas-template.html --www /srv/www [--three /path/to/three/package] [--split scenes.json]
"""
import argparse, json, os, shutil

IMPORTMAP_CDN = ('{"imports":{"three":"https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js",'
                 '"three/addons/":"https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/"}}')
IMPORTMAP_LOCAL = '{"imports":{"three":"./lib/three/build/three.module.js","three/addons/":"./lib/three/examples/jsm/"}}'
ADDONS = ["controls/OrbitControls.js", "geometries/RoundedBoxGeometry.js", "environments/RoomEnvironment.js"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", required=True)
    ap.add_argument("--www", required=True)
    ap.add_argument("--three", default="", help="unpacked three@0.160.0 npm package dir (contains build/, examples/)")
    ap.add_argument("--split", default="", help="existing scenes.json to split into data/<id>.json")
    a = ap.parse_args()
    os.makedirs(os.path.join(a.www, "data"), exist_ok=True)

    html = open(a.template, encoding="utf-8").read()
    assert "__DATA__" in html, "template has no __DATA__ placeholder"
    html = html.replace("__DATA__", "{}")
    if a.three:
        assert IMPORTMAP_CDN in html, "importmap not found in template"
        html = html.replace(IMPORTMAP_CDN, IMPORTMAP_LOCAL)
        for rel in ["build/three.module.js"] + ["examples/jsm/" + x for x in ADDONS]:
            dst = os.path.join(a.www, "lib/three", rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            src = os.path.join(a.three, rel)
            if not (os.path.exists(dst) and os.path.samefile(src, dst)): shutil.copyfile(src, dst)
        src, dst = os.path.join(a.three, "LICENSE"), os.path.join(a.www, "lib/three/LICENSE")
        if not (os.path.exists(dst) and os.path.samefile(src, dst)): shutil.copyfile(src, dst)
    tmp = os.path.join(a.www, "index.html.tmp")
    open(tmp, "w", encoding="utf-8").write(html)
    os.replace(tmp, os.path.join(a.www, "index.html"))

    if a.split:
        for sid, d in json.load(open(a.split)).items():
            fn = os.path.join(a.www, "data", f"{sid}.json")
            json.dump(d, open(fn + ".tmp", "w"), separators=(",", ":")); os.replace(fn + ".tmp", fn)
            print(f"data/{sid}.json {os.path.getsize(fn)/1e3:.0f} kB")
    print("index.html", os.path.getsize(os.path.join(a.www, "index.html")) // 1000, "kB")


if __name__ == "__main__":
    main()
