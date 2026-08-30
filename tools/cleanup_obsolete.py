#!/usr/bin/env python3
"""Detecta o elimina únicamente artefactos conocidos de motores anteriores."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
patterns = ["js/data_part_*.js", "js/data_sem_*.js", "js/data_index.js", "icons/hero-maxmin.png", "icons/splash-1920x1080.png"]
targets = sorted({path for pattern in patterns for path in ROOT.glob(pattern) if path.is_file()})
parser = argparse.ArgumentParser()
parser.add_argument("--apply", action="store_true")
parser.add_argument("--report", type=Path)
args = parser.parse_args()

report = {
    "status": "clean" if not targets else ("cleaned" if args.apply else "blocked"),
    "apply": args.apply,
    "targets": [target.relative_to(ROOT).as_posix() for target in targets],
}

if args.apply:
    for target in targets:
        target.unlink()
        print(f"eliminado: {target.relative_to(ROOT)}")
else:
    for target in targets:
        print(f"obsoleto: {target.relative_to(ROOT)}")
if args.report:
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
summary = os.environ.get("GITHUB_STEP_SUMMARY")
if summary:
    with Path(summary).open("a", encoding="utf-8") as stream:
        stream.write("## Limpieza de motores obsoletos\n\n")
        stream.write(f"Estado: **{report['status']}** · Objetivos: **{len(targets)}**\n\n")
        if targets:
            stream.write("Ejecuta el workflow **Limpiar motores obsoletos** antes de validar.\n")
if targets and not args.apply:
    raise SystemExit("ERROR: persisten archivos obsoletos; ejecuta el workflow Limpiar motores obsoletos")
print(f"status=ok targets={len(targets)}")
