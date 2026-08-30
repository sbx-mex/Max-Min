#!/usr/bin/env python3
"""Detecta o elimina únicamente artefactos conocidos de motores anteriores."""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
patterns = ["js/data_part_*.js", "js/data_sem_*.js", "js/data_index.js", "icons/hero-maxmin.png", "icons/splash-1920x1080.png"]
targets = sorted({path for pattern in patterns for path in ROOT.glob(pattern) if path.is_file()})
parser = argparse.ArgumentParser()
parser.add_argument("--apply", action="store_true")
args = parser.parse_args()

if args.apply:
    for target in targets:
        target.unlink()
        print(f"eliminado: {target.relative_to(ROOT)}")
else:
    for target in targets:
        print(f"obsoleto: {target.relative_to(ROOT)}")
    if targets:
        raise SystemExit(1)
print(f"status=ok targets={len(targets)}")
