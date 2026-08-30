#!/usr/bin/env python3
"""Valida visualmente medible la muestra PDF multipágina incluida."""

import sys
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
PDF = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "docs" / "Etiquetas_MIN_MAX_Muestra_38107_Sem18-25.pdf"

if not PDF.is_file():
    raise SystemExit("ERROR: falta la muestra PDF multipágina")
reader = PdfReader(PDF)
if len(reader.pages) < 2:
    raise SystemExit("ERROR: la muestra debe probar más de una hoja")
for index, page in enumerate(reader.pages, start=1):
    width = float(page.mediabox.width)
    height = float(page.mediabox.height)
    if width <= height:
        raise SystemExit(f"ERROR: página {index} no es horizontal")
    if abs(width - 792) > 2 or abs(height - 612) > 2:
        raise SystemExit(f"ERROR: página {index} no es Carta")
print({"status": "ok", "pages": len(reader.pages), "page": "letter-landscape"})
