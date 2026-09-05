#!/usr/bin/env python3
"""Compara una fuente semanal con los JSON publicados, registro por registro."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path

from build_data import load_directory_records, norm, normalized_csv_lines, text
from update_week import REQUIRED_HEADERS, read_manifest, source_bytes

ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def verify(args: argparse.Namespace) -> dict[str, object]:
    root = args.root.resolve()
    manifest = read_manifest(root)
    raw, source_name = source_bytes(args.input.resolve(), args.week)
    source_sha = hashlib.sha256(raw).hexdigest()
    if int(args.week) not in {int(value) for value in manifest["weeks"]}:
        fail(f"la semana {args.week} no está publicada")
    last_update = manifest.get("lastUpdate", {})
    if int(last_update.get("week", -1)) != args.week or last_update.get("sha256") != source_sha:
        fail("el sello de la última actualización no coincide con la fuente")

    directory = load_directory_records(args.directory)
    categories = {name: index for index, name in enumerate(manifest["categories"])}
    ingredients = {norm(item["name"]): index for index, item in enumerate(manifest["ingredients"])}
    expected: dict[str, dict[tuple[int, int], int]] = {}
    seen: dict[tuple[str, str, str], int] = {}
    reader = csv.DictReader(normalized_csv_lines(io.BytesIO(raw)))
    if not REQUIRED_HEADERS.issubset(set(reader.fieldnames or [])):
        fail(f"encabezados inválidos: {reader.fieldnames}")

    excluded_unknown = 0
    for row_number, row in enumerate(reader, start=2):
        try:
            usage = float(text(row.get("Uso Ideal* (#)")).replace(",", "") or 0)
        except ValueError:
            fail(f"fila {row_number}: Uso Ideal no es numérico")
        if usage <= 0:
            continue
        ceco = text(row.get("Tiendas"))
        category = text(row.get("Categoría Inventario"))
        ingredient_key = norm(row.get("Ingrediente"))
        if ceco not in directory:
            excluded_unknown += 1
            continue
        source_key = (ceco, category, ingredient_key)
        if source_key in seen:
            fail(f"fila {row_number}: duplicada con fila {seen[source_key]}")
        seen[source_key] = row_number
        if category not in categories or ingredient_key not in ingredients:
            fail(f"fila {row_number}: categoría o ingrediente no fue publicado")
        expected.setdefault(ceco, {})[(categories[category], ingredients[ingredient_key])] = int(round(usage * 100))

    published: dict[str, dict[tuple[int, int], int]] = {}
    duplicate_published = 0
    for store in manifest["stores"]:
        ceco = str(store["code"])
        payload = json.loads((root / str(store["file"])).read_text(encoding="utf-8"))
        flat = payload.get(str(args.week), [])
        records: dict[tuple[int, int], int] = {}
        for offset in range(0, len(flat), 3):
            key = (int(flat[offset]), int(flat[offset + 1]))
            if key in records:
                duplicate_published += 1
            records[key] = int(flat[offset + 2])
        if records:
            published[ceco] = records

    mismatches: list[dict[str, object]] = []
    for ceco in sorted(set(expected) | set(published)):
        expected_records = expected.get(ceco, {})
        published_records = published.get(ceco, {})
        for key in sorted(set(expected_records) | set(published_records)):
            if expected_records.get(key) != published_records.get(key):
                mismatches.append({
                    "ceco": ceco,
                    "categoryId": key[0],
                    "ingredientId": key[1],
                    "expectedCents": expected_records.get(key),
                    "publishedCents": published_records.get(key),
                })
    if duplicate_published:
        fail(f"se detectaron {duplicate_published} registros publicados duplicados")
    if mismatches:
        preview = json.dumps(mismatches[:5], ensure_ascii=False)
        fail(f"la publicación difiere de la fuente en {len(mismatches)} registros: {preview}")

    report = {
        "status": "ok",
        "week": args.week,
        "source": source_name,
        "sourceSha256": source_sha,
        "verifiedRecords": sum(len(records) for records in expected.values()),
        "verifiedStores": len(expected),
        "excludedUnknownRows": excluded_unknown,
        "duplicateSourceRecords": 0,
        "duplicatePublishedRecords": 0,
        "mismatches": 0,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verifica que una semana publicada coincida con su CSV")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--directory", type=Path, default=ROOT / "sources" / "Directorio.xlsx")
    return parser.parse_args()


if __name__ == "__main__":
    print(json.dumps(verify(parse_args()), ensure_ascii=False, indent=2))
