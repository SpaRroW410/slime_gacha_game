#!/usr/bin/env python3
"""Slime Gacha - entry point.  python3 main.py [--demo] [--seed N] [--save PATH]"""
import argparse

from slime_gacha.cli import run_demo, run_interactive


def main() -> None:
    ap = argparse.ArgumentParser(description="Offline slime gacha prototype")
    ap.add_argument("--demo", action="store_true", help="run a scripted tour of every system")
    ap.add_argument("--seed", type=int, default=None, help="seed the RNG for reproducible runs")
    ap.add_argument("--save", default="savegame.json", help="save file path")
    args = ap.parse_args()
    if args.demo:
        run_demo(args.seed if args.seed is not None else 7)
    else:
        run_interactive(args.seed, args.save)


if __name__ == "__main__":
    main()
