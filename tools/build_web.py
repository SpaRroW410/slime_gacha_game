#!/usr/bin/env python3
"""Build the STATIC web edition (no Python server needed): python3 tools/build_web.py [--cdn]

Produces ./dist containing the UI, the game packaged as slime_gacha.zip, and (unless --cdn) a vendored copy of
Pyodide (Python compiled to WebAssembly, fetched once with `npm pack pyodide`). Host dist/ on any static
server (GitHub Pages, itch.io, `python3 -m http.server -d dist`). Once vendored it works fully offline.
"""
import argparse
import glob
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")
PYODIDE_VERSION = "0.26.4"
PYODIDE_FILES = ["pyodide.js", "pyodide.asm.js", "pyodide.asm.wasm", "python_stdlib.zip", "pyodide-lock.json"]


def build_zip(path: str) -> int:
    n = 0
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for dirpath, dirs, files in os.walk(os.path.join(ROOT, "slime_gacha")):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for f in files:
                if f.endswith(".pyc"):
                    continue
                full = os.path.join(dirpath, f)
                z.write(full, os.path.relpath(full, ROOT))
                n += 1
    return n


def vendor_pyodide(dest: str, tgz: str = None) -> None:
    os.makedirs(dest, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        if not tgz:
            print(f"fetching pyodide@{PYODIDE_VERSION} via npm ...")
            subprocess.run(["npm", "pack", f"pyodide@{PYODIDE_VERSION}", "--silent"], cwd=tmp, check=True,
                           stdout=subprocess.DEVNULL)
            tgz = glob.glob(os.path.join(tmp, "pyodide-*.tgz"))[0]
        with tarfile.open(tgz) as t:
            for name in PYODIDE_FILES:
                member = t.getmember(f"package/{name}")
                member.name = name
                try:
                    t.extract(member, dest, filter="data")
                except TypeError:          # Python < 3.12 has no extraction filters
                    t.extract(member, dest)


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the static (Pyodide) web edition into ./dist")
    ap.add_argument("--cdn", action="store_true", help="do not vendor Pyodide; load it from the jsDelivr CDN")
    ap.add_argument("--pyodide-tgz", help="use a local `npm pack pyodide` tarball instead of downloading")
    args = ap.parse_args()
    if os.path.isdir(DIST):
        shutil.rmtree(DIST)
    shutil.copytree(os.path.join(ROOT, "web"), DIST, ignore=shutil.ignore_patterns("vendor"))
    n = build_zip(os.path.join(DIST, "slime_gacha.zip"))
    print(f"packed {n} python files -> dist/slime_gacha.zip")
    if not args.cdn:
        vendor_pyodide(os.path.join(DIST, "vendor", "pyodide"), args.pyodide_tgz)
        size = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(DIST) for f in fs) / 1e6
        print(f"vendored Pyodide {PYODIDE_VERSION}; dist is {size:.1f} MB (works offline)")
    print("done. Try:  python3 -m http.server -d dist 8766   then open http://127.0.0.1:8766/")


if __name__ == "__main__":
    sys.exit(main())
