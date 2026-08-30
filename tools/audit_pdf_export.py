#!/usr/bin/env python3
"""Audita tamaño, paginación y contenido obligatorio de una exportación PDF."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PDF = ROOT / "docs" / "Etiquetas_MIN_MAX_Muestra_38107_Sem18-25.pdf"
LETTER_LANDSCAPE_POINTS = (792.0, 612.0)
REQUIRED_PAGE_TEXT = (
    "TIENDA:", "38107", "PEDREGAL", "SEMANAS:", "18-25",
    "ACTUALIZACIÓN:", "MIN", "MAX", "#DIA", "#SAP", "PEDIDOS",
)


def fail(message: str) -> None:
    raise RuntimeError(message)


def audit_pdf(pdf_path: Path, expected_labels: int = 15) -> dict[str, object]:
    if not pdf_path.is_file():
        fail(f"falta el PDF: {pdf_path}")

    reader = PdfReader(pdf_path)
    expected_pages = (expected_labels + 11) // 12
    if len(reader.pages) != expected_pages or len(reader.pages) < 2:
        fail(f"paginación inesperada: {len(reader.pages)}; esperadas {expected_pages}")

    title = str((reader.metadata or {}).get("/Title", ""))
    if "ETIQUETAS MIN MAX" not in title.upper():
        fail("el PDF no conserva el título documental")

    page_reports: list[dict[str, object]] = []
    labels_found = 0
    for index, page in enumerate(reader.pages, start=1):
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        if width <= height:
            fail(f"página {index} no es horizontal")
        if abs(width - LETTER_LANDSCAPE_POINTS[0]) > 2 or abs(height - LETTER_LANDSCAPE_POINTS[1]) > 2:
            fail(f"página {index} no es Carta horizontal: {width:.2f} x {height:.2f} pt")
        if tuple(page.cropbox) != tuple(page.mediabox):
            fail(f"página {index} tiene un recorte distinto al lienzo")

        text = " ".join((page.extract_text() or "").split())
        upper = text.upper()
        missing = [token for token in REQUIRED_PAGE_TEXT if token not in upper]
        if missing:
            fail(f"página {index} sin contenido obligatorio: {', '.join(missing)}")

        page_labels = upper.count("#DIA")
        if page_labels < 1 or page_labels > 12:
            fail(f"página {index} contiene {page_labels} etiquetas; el rango válido es 1-12")
        if index < len(reader.pages) and page_labels != 12:
            fail(f"página {index} debe estar completa con 12 etiquetas")
        labels_found += page_labels
        page_reports.append({
            "page": index,
            "sizePoints": [round(width, 2), round(height, 2)],
            "labels": page_labels,
            "headerOccurrences": upper.count("TIENDA:"),
            "textCharacters": len(text),
        })

    if labels_found != expected_labels:
        fail(f"se extrajeron {labels_found} etiquetas; se esperaban {expected_labels}")
    if any(page["headerOccurrences"] != 1 for page in page_reports):
        fail("la cabecera compacta debe repetirse exactamente una vez por hoja")

    return {
        "status": "ok",
        "file": str(pdf_path),
        "pages": len(reader.pages),
        "labels": labels_found,
        "labelsPerPage": [page["labels"] for page in page_reports],
        "pageFormat": "Carta horizontal",
        "grid": "4x3",
        "header": "una fila compacta por página",
        "requiredFields": ["Descripción SAP", "Nombre Inventario", "#DIA", "#SAP", "MIN", "MAX", "Formato", "Unidad de medida", "# Pedidos"],
        "pageReports": page_reports,
    }


def main() -> None:
    pdf_path = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_PDF
    expected_labels = int(sys.argv[2]) if len(sys.argv) > 2 else 15
    try:
        report = audit_pdf(pdf_path, expected_labels)
    except RuntimeError as error:
        raise SystemExit(f"ERROR: {error}") from error
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
