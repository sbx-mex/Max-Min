#!/usr/bin/env python3
"""Valida un CSV semanal sin modificar el motor publicado."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from collections import Counter
from pathlib import Path

from build_data import load_crosses, norm, normalized_csv_lines, text
from update_week import REQUIRED_HEADERS, source_bytes

ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def audit(args: argparse.Namespace) -> dict[str, object]:
    raw, source_name = source_bytes(args.input.resolve(), args.week)
    if len(raw) > 25 * 1024 * 1024:
        fail("el archivo semanal supera 25 MB; comprímelo como ZIP")
    directory, _, _ = load_crosses(args.directory, args.prices, args.presentations)
    reader = csv.DictReader(normalized_csv_lines(io.BytesIO(raw)))
    headers = set(reader.fieldnames or [])
    if not REQUIRED_HEADERS.issubset(headers):
        fail(f"encabezados inválidos: {reader.fieldnames}")

    rows = 0
    positive_rows = 0
    stores: set[str] = set()
    categories: set[str] = set()
    ingredients: set[str] = set()
    unknown_stores: set[str] = set()
    unknown_store_rows: Counter[str] = Counter()
    source_keys: dict[tuple[str, str, str], int] = {}
    for row_number, row in enumerate(reader, start=2):
        rows += 1
        try:
            row_week = int(float(text(row.get("Semana"))))
        except ValueError:
            fail(f"fila {row_number}: Semana inválida")
        if row_week != args.week:
            fail(f"fila {row_number}: se esperaba Semana {args.week} y se recibió {row_week}")
        if text(row.get("Indicadores")):
            fail(f"fila {row_number}: Indicadores debe permanecer vacío")
        try:
            usage = float(text(row.get("Uso Ideal* (#)")).replace(",", "") or 0)
        except ValueError:
            fail(f"fila {row_number}: Uso Ideal no es numérico")
        if usage < 0:
            fail(f"fila {row_number}: Uso Ideal no puede ser negativo")
        if usage == 0:
            continue
        ceco = text(row.get("Tiendas"))
        category = text(row.get("Categoría Inventario"))
        ingredient = text(row.get("Ingrediente"))
        if not ceco or not category or not ingredient:
            fail(f"fila {row_number}: faltan CeCo, Categoría o Ingrediente")
        source_key = (ceco, category, norm(ingredient))
        if source_key in source_keys:
            fail(f"fila {row_number}: registro duplicado con fila {source_keys[source_key]}")
        source_keys[source_key] = row_number
        if ceco not in directory:
            unknown_stores.add(ceco)
            unknown_store_rows[ceco] += 1
        stores.add(ceco)
        categories.add(category)
        ingredients.add(ingredient)
        positive_rows += 1

    if rows == 0:
        fail("el CSV semanal está vacío")
    if unknown_stores and args.unknown_store_policy == "fail":
        preview = ", ".join(sorted(unknown_stores)[:12])
        blocked_report = {
            "status": "blocked",
            "week": args.week,
            "source": source_name,
            "sourceSha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
            "rows": rows,
            "positiveRows": positive_rows,
            "unknownStores": [
                {"ceco": ceco, "positiveRows": unknown_store_rows[ceco]}
                for ceco in sorted(unknown_stores)
            ],
            "requiredAction": "agregar cada CeCo al Directorio.xlsx con su nombre oficial y volver a ejecutar",
            "result": "data/ no fue modificado",
        }
        report_path = args.report.resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(blocked_report, ensure_ascii=False, indent=2), encoding="utf-8")
        fail(f"CeCo sin cruce en Directorio.xlsx: {preview}")

    report = {
        "status": "warning" if unknown_stores else "ok",
        "week": args.week,
        "source": source_name,
        "sourceSha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "rows": rows,
        "positiveRows": positive_rows,
        "stores": len(stores),
        "categories": len(categories),
        "ingredients": len(ingredients),
        "indicatorNonBlank": 0,
        "duplicateRecords": 0,
        "unknownStores": [
            {"ceco": ceco, "positiveRows": unknown_store_rows[ceco]}
            for ceco in sorted(unknown_stores)
        ],
        "excludedUnknownRows": sum(unknown_store_rows.values()),
        "unknownStorePolicy": args.unknown_store_policy,
        "safeRoute": f"updates/incoming/{Path(args.input).name}",
        "result": "fuente validada; los CeCo fuera del directorio se excluirán" if unknown_stores else "fuente validada; todavía no se modificó data/",
    }
    report_path = args.report.resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audita una fuente semanal sin modificar data/")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--report", type=Path, default=ROOT / "audit" / "week_source_report.json")
    parser.add_argument("--directory", type=Path, default=ROOT / "sources" / "Directorio.xlsx")
    parser.add_argument("--prices", type=Path, default=ROOT / "sources" / "Lista_Precios_Base.xlsx")
    parser.add_argument("--presentations", type=Path, default=ROOT / "tools" / "presentation_reference.json")
    parser.add_argument("--unknown-store-policy", choices=("fail", "skip"), default="skip")
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(audit(parse_args()), ensure_ascii=False, indent=2))
