#!/usr/bin/env python3
"""Genera, renderiza y certifica la muestra multipágina antes de publicar."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageOps

from audit_pdf_export import audit_pdf

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "docs" / "Etiquetas_MIN_MAX_Muestra_38107_Sem18-25.pdf"
DEFAULT_REPORT = ROOT / "audit" / "pdf_release_report.json"


def run(command: list[str]) -> None:
    subprocess.run(command, cwd=ROOT, check=True)


def inspect_render(path: Path, page: int) -> dict[str, object]:
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        gray = ImageOps.grayscale(rgb)
        ink = gray.point(lambda value: 255 if value < 245 else 0)
        bbox = ink.getbbox()
        if bbox is None:
            raise RuntimeError(f"la página renderizada {page} está vacía")
        left, top, right, bottom = bbox
        margins = [left, top, rgb.width - right, rgb.height - bottom]
        if min(margins) < 12:
            raise RuntimeError(f"contenido demasiado cerca del corte en página {page}: {margins}px")
        ink_pixels = ink.histogram()[255]
        coverage = ink_pixels / (rgb.width * rgb.height)
        if coverage < 0.008 or coverage > 0.35:
            raise RuntimeError(f"cobertura visual anómala en página {page}: {coverage:.4f}")
        return {
            "page": page,
            "pixels": [rgb.width, rgb.height],
            "contentBox": [left, top, right, bottom],
            "safeMarginsPixels": margins,
            "inkCoverage": round(coverage, 4),
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--labels", type=int, default=15)
    args = parser.parse_args()
    output = args.output.resolve()
    report_path = args.report.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    if not shutil.which("node"):
        raise SystemExit("ERROR: Node.js no está disponible")
    if not shutil.which("pdftoppm"):
        raise SystemExit("ERROR: Poppler/pdftoppm no está disponible")

    run(["node", "tools/generate_pdf_sample.cjs", str(output)])
    pdf_report = audit_pdf(output, args.labels)

    with tempfile.TemporaryDirectory(prefix="maxmin_pdf_") as temp_dir:
        prefix = Path(temp_dir) / "page"
        run(["pdftoppm", "-png", "-r", "180", str(output), str(prefix)])
        renders = sorted(Path(temp_dir).glob("page-*.png"))
        if len(renders) != pdf_report["pages"]:
            raise SystemExit("ERROR: el render no produjo una imagen por hoja")
        visual = [inspect_render(path, index) for index, path in enumerate(renders, start=1)]

    payload = {
        **pdf_report,
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "bytes": output.stat().st_size,
        "renderDpi": 180,
        "visualSafety": visual,
    }
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
