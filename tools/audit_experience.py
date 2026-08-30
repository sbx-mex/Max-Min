#!/usr/bin/env python3
"""Audita cinco mejoras de navegación, consulta, acomodo y PDF."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageOps
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = ROOT / "audit" / "experience_report.json"
DEFAULT_PDF = ROOT / "output" / "pdf" / "Lista_MIN_MAX_Muestra_38107.pdf"
LETTER_LANDSCAPE_POINTS = (792.0, 612.0)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"ERROR: {message}")


def inspect_pdf(pdf_path: Path, expected_rows: int = 30) -> dict[str, object]:
    try:
        display_file = pdf_path.relative_to(ROOT).as_posix()
    except ValueError:
        display_file = pdf_path.name
    reader = PdfReader(pdf_path)
    expected_pages = (expected_rows + 19) // 20
    require(len(reader.pages) == expected_pages, f"lista PDF con {len(reader.pages)} hojas; se esperaban {expected_pages}")
    title = str((reader.metadata or {}).get("/Title", ""))
    require("LISTA OPERATIVA MIN MAX" in title.upper(), "título documental incorrecto en lista PDF")
    page_reports: list[dict[str, object]] = []
    for page_number, page in enumerate(reader.pages, start=1):
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        require(width > height, f"hoja {page_number} no está en orientación horizontal")
        require(abs(width - LETTER_LANDSCAPE_POINTS[0]) <= 2 and abs(height - LETTER_LANDSCAPE_POINTS[1]) <= 2, f"hoja {page_number} no es Carta")
        text = " ".join((page.extract_text() or "").split()).upper()
        for token in ("TIENDA:", "38107", "SEMANAS:", "#DIA", "#SAP", "USO PROM. SEM", "# PEDIDOS", "HOJA 1 DE"):
            require(token in text, f"hoja {page_number} sin {token}")
        require(not re.search(r"(?<!\d)0\.0(?!\d)", text), f"hoja {page_number} contiene un valor visible igual a 0.0")
        require(text.count("TIENDA:") == 1, f"cabecera repetida incorrectamente en hoja {page_number}")
        page_reports.append({"page": page_number, "sizePoints": [round(width, 2), round(height, 2)], "textCharacters": len(text)})

    visual: list[dict[str, object]] = []
    if shutil.which("pdftocairo"):
        with tempfile.TemporaryDirectory(prefix="maxmin_list_render_") as temp_dir:
            prefix = Path(temp_dir) / "page"
            subprocess.run(["pdftocairo", "-png", "-r", "160", str(pdf_path), str(prefix)], check=True, cwd=ROOT)
            renders = sorted(Path(temp_dir).glob("page-*.png"))
            require(len(renders) == expected_pages, "el render visual no generó una imagen por hoja")
            for page_number, image_path in enumerate(renders, start=1):
                with Image.open(image_path) as image:
                    gray = ImageOps.grayscale(image.convert("RGB"))
                    ink = gray.point(lambda value: 255 if value < 245 else 0)
                    bbox = ink.getbbox()
                    require(bbox is not None, f"hoja {page_number} vacía")
                    left, top, right, bottom = bbox
                    margins = [left, top, image.width - right, image.height - bottom]
                    require(min(margins) >= 8, f"contenido muy cerca del corte en hoja {page_number}: {margins}")
                    coverage = ink.histogram()[255] / (image.width * image.height)
                    require(0.008 <= coverage <= 0.40, f"cobertura visual anómala en hoja {page_number}: {coverage:.4f}")
                    visual.append({"page": page_number, "safeMarginsPixels": margins, "inkCoverage": round(coverage, 4)})

    return {
        "file": display_file,
        "sha256": hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
        "bytes": pdf_path.stat().st_size,
        "pages": expected_pages,
        "rows": expected_rows,
        "pageFormat": "Carta horizontal",
        "pageReports": page_reports,
        "visualSafety": visual,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--pdf-output", type=Path, default=DEFAULT_PDF)
    args = parser.parse_args()
    report_path = args.report.resolve()
    pdf_path = args.pdf_output.resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    index = (ROOT / "index.html").read_text(encoding="utf-8")
    app = (ROOT / "js" / "app.js").read_text(encoding="utf-8")
    styles = (ROOT / "css" / "styles.css").read_text(encoding="utf-8")

    expected_headers = "<th>Sel.</th><th>Ingrediente / SAP</th><th>Categoría</th><th>#DIA</th><th>#SAP</th><th>Uso prom. Sem</th><th>Mín.</th><th>Máx.</th>"
    require(expected_headers in index, "orden de columnas de Consulta incorrecto")
    require("<th>Formato</th>" not in index and "table-format" not in app, "Formato debe controlarse sólo desde el filtro global")
    require("<th>Estado</th>" not in index and '["ESTADO"' not in app, "Estado debe ocultarse de Consulta y Lista PDF")
    require("function positiveReportItems()" in app and "Number(item.usage) > 0" in app and "Number(calc.min) > 0" in app and "Number(calc.max) > 0" in app, "falta el filtro estricto de valores positivos")

    header = index.split("</header>", 1)[0]
    require('id="exportButton"' not in header, "Exportar PDF no debe permanecer como acción global")
    consulta = index[index.index('id="tab-consulta"'):index.index('id="tab-acomodo"')]
    etiquetas = index[index.index('id="tab-etiquetas"'):index.index('id="tab-consulta"')]
    for marker in ("consultaOutputActions", "exportListButton", "addVisibleButton", "exportSelectedLabelsButton"):
        require(marker in consulta, f"falta acción contextual de Consulta: {marker}")
    require("exportLabelsButton" in etiquetas, "falta exportación contextual en Etiquetas")
    require(consulta.index("exportListButton") < consulta.index("addVisibleButton") < consulta.index("exportSelectedLabelsButton"), "la secuencia de botones en Consulta no es intuitiva")
    require("No necesitas seleccionar" in consulta and "Primero toma lo visible" in consulta, "faltan instrucciones discretas para elegir salida")
    require("function listItemsCurrent()" in app and "function listItemsCurrent() {\n  return positiveReportItems();\n}" in app, "Lista PDF debe usar siempre las filas visibles")
    require("state.selected = new Set(items.map((item) => item.id));" in app, "Elegir visibles debe reemplazar una selección anterior")

    for marker in ("Ruta rápida · Etiquetas", "Ruta rápida · Consulta", "Ruta rápida · Acomodo", 'data-step="${index + 1}"', "updateWorkflowProgress"):
        require(marker in app, f"falta ruta numerada: {marker}")
    require("grid-template-columns:repeat(4,1fr)" in styles and ".workflow-step.current" in styles, "la ruta de cuatro pasos no tiene jerarquía visual")
    for marker in (".panel-export-action", ".consulta-output-grid", ".output-option-buttons"):
        require(marker in styles, f"falta diseño de acción contextual: {marker}")
    for marker in ("function buildListPdf", "function buildPdf", "LIST_PAGE_SIZE = 20", "format: \"letter\"", "orientation: \"landscape\""):
        require(marker in app, f"falta motor PDF dual: {marker}")

    require(".acomodo-workflow{display:grid" in styles and "min-height:clamp(430px,58vw,760px)" in styles, "Acomodo no prioriza la fotografía superior")
    acomodo = index[index.index('id="tab-acomodo"'):index.index("</main>")]
    for marker in ("addAcomodoItemsButton", "clearAcomodoItemsButton", "exportAcomodoButton", "marker-table-head"):
        require(marker in acomodo, f"falta control intuitivo de Acomodo: {marker}")
    for marker in ("draggable=\"true\"", "onPhotoStageDrop", "onPhotoStageClick", "placeMarkerAt", "activeMarkerId", "function buildAcomodoPdf", "rackPhotoDataUrl", "ACOMODO_MAX_ITEMS = 25", "ACOMODO_PAGE_SIZE = 8"):
        require(marker in app, f"falta interacción de acomodo: {marker}")
    require('["PEDIDOS", String(state.orders)]' in app, "todas las exportaciones deben mostrar el número de pedidos")
    require('["#", "INGREDIENTE / SAP", "USO PROM. SEM", "MÍN.", "MÁX."]' in app, "PDF de Acomodo no conserva el orden operativo")
    require("pdf-viewer-dialog" in styles and "internal-pdf-link" in index and "openSupportPdf" in app, "las guías PDF no tienen visor interno con cierre")
    require('pdf.text(`Hoja ${pageIndex+1} de ${pages}`' in app, "la paginación debe vivir en el pie")
    require("LISTA OPERATIVA - SOLO VALORES" not in app, "la lista conserva texto redundante en la cabecera")

    require('$("healthBadge").textContent' in app and '$("healthBadge").querySelector' not in app, "el indicador de salud puede romper la inicialización")
    require("Revisa la tabla" in app and "Toma la foto" in app and "Elige y ubica artículos" in app and "Revisa y exporta" in app, "las rutas rápidas no están alineadas con cada pestaña")

    subprocess.run(["node", "tools/generate_list_pdf_sample.cjs", str(pdf_path)], cwd=ROOT, check=True)
    pdf_report = inspect_pdf(pdf_path)

    improvements = [
        {"id": 1, "name": "Botones en contexto", "status": "ok", "evidence": "la exportación salió del encabezado y vive dentro de Etiquetas o Consulta"},
        {"id": 2, "name": "Ruta numerada", "status": "ok", "evidence": "cada pestaña comunica cuatro pasos y resalta el avance actual"},
        {"id": 3, "name": "Consulta sin ambigüedad", "status": "ok", "evidence": "Lista PDF usa visibles; Etiquetas exige Elegir visibles y confirma la selección"},
        {"id": 4, "name": "Exportación segura", "status": "ok", "evidence": "lista y etiquetas conservan Carta horizontal y paginación multipágina"},
        {"id": 5, "name": "Acomodo guiado", "status": "ok", "evidence": "foto dominante, selección libre hasta 25, visor interno y PDF multipágina con pedidos"},
    ]
    payload = {"status": "ok", "improvements": improvements, "listPdf": pdf_report}
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
