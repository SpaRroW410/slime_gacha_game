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


def write_icons(dest: str) -> None:
    """Draw the app icon (a green slime on a dark tile) as PNGs, with no imaging library."""
    import math
    import struct
    import zlib

    def png(size: int) -> bytes:
        rows = []
        for y in range(size):
            row = bytearray([0])
            for x in range(size):
                u, v = x / size - 0.5, y / size - 0.5
                px = (18, 24, 31, 255)
                bx, by = u, (v - 0.06) * 1.25            # body: a dome with a flat-ish base
                if bx * bx + by * by < 0.2 ** 2 or (abs(bx) < 0.2 and 0 <= v + 0.06 < 0.17 and bx * bx + (by * 1.0) ** 2 < 0.2 ** 2 * 1.6):
                    t = max(0.0, 1 - math.hypot(bx + 0.07, by + 0.09) * 3.2)
                    px = (int(70 + 120 * t), int(200 + 40 * t), int(140 + 80 * t), 255)
                for ex in (-0.07, 0.07):
                    if (u - ex) ** 2 + (v - 0.02) ** 2 < 0.028 ** 2:
                        px = (16, 32, 26, 255)
                row += bytes(px)
            rows.append(bytes(row))
        raw = b"".join(rows)

        def chunk(tag: bytes, data: bytes) -> bytes:
            return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))
    for size in (180, 192, 512):
        with open(os.path.join(dest, f"icon-{size}.png"), "wb") as f:
            f.write(png(size))


def write_service_worker(dest: str) -> int:
    """Fill the service worker's version and file list so the whole build is cached for offline play."""
    import hashlib
    import json
    files = []
    h = hashlib.sha1()
    for dp, _, fs in os.walk(dest):
        for f in sorted(fs):
            full = os.path.join(dp, f)
            rel = os.path.relpath(full, dest).replace(os.sep, "/")
            if rel == "sw.js":
                continue
            files.append(rel)
            h.update(rel.encode())
            h.update(str(os.path.getsize(full)).encode())
            with open(full, "rb") as fh:
                if os.path.getsize(full) < 3_000_000:
                    h.update(fh.read())
    files = ["./"] + sorted(files)
    path = os.path.join(dest, "sw.js")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    text = text.replace("__VERSION__", h.hexdigest()[:10]).replace("__FILES__", json.dumps(files))
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return len(files)


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
    write_icons(DIST)
    print(f"service worker caches {write_service_worker(DIST)} files (installable, offline)")
    print("done. Try:  python3 -m http.server -d dist 8766   then open http://127.0.0.1:8766/")


if __name__ == "__main__":
    sys.exit(main())
