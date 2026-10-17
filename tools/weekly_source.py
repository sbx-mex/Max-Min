"""Límites y lectura segura compartidos por la cola, el auditor y el importador."""
from __future__ import annotations

import math
import re
import zipfile
from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_EXPANDED_BYTES = 128 * 1024 * 1024
MAX_PENDING_FILES = 100
REQUIRED_HEADERS = {"Semana", "Tiendas", "Categoría Inventario", "Ingrediente", "Indicadores", "Uso Ideal* (#)"}


def parse_week(value: object) -> int:
    try:
        number = Decimal(str(value).strip())
        if not number.is_finite() or number != number.to_integral_value() or not 1 <= number <= 53:
            raise ValueError()
        return int(number)
    except (InvalidOperation, ValueError):
        raise ValueError(f"Semana inválida: {value!r}; debe ser un entero entre 1 y 53") from None


def parse_usage(value: object) -> float:
    try:
        usage = float(str(value or "0").strip().replace(",", "") or "0")
    except ValueError:
        raise ValueError("Uso Ideal no es numérico") from None
    if not math.isfinite(usage) or usage < 0 or usage * 100 > 4_294_967_295:
        raise ValueError("Uso Ideal debe ser finito, no negativo y caber en el motor compacto")
    return usage


def read_source(path: Path) -> tuple[bytes, str]:
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"fuente inexistente o enlazada: {path.name}")
    if path.stat().st_size > MAX_UPLOAD_BYTES:
        raise ValueError(f"{path.name} supera 25 MiB por archivo; usa un ZIP")
    if path.suffix.lower() == ".csv":
        return path.read_bytes(), path.name
    if path.suffix.lower() != ".zip":
        raise ValueError("la fuente debe ser CSV o ZIP")
    try:
        with zipfile.ZipFile(path) as archive:
            candidates = [info for info in archive.infolist() if not info.is_dir() and info.filename.lower().endswith(".csv")]
            if len(candidates) != 1:
                raise ValueError("el ZIP debe contener exactamente un CSV")
            info = candidates[0]
            member = PurePosixPath(info.filename)
            if member.is_absolute() or ".." in member.parts or "\\" in info.filename or re.match(r"^[A-Za-z]:", info.filename):
                raise ValueError("ruta CSV insegura dentro del ZIP")
            if info.file_size > MAX_EXPANDED_BYTES or info.flag_bits & 1:
                raise ValueError("CSV comprimido demasiado grande o cifrado")
            return archive.read(info), member.name
    except zipfile.BadZipFile as error:
        raise ValueError("ZIP dañado") from error


def incoming_files(root: Path) -> list[Path]:
    folder = root / "updates" / "incoming"
    files = sorted(path for path in folder.iterdir() if path.suffix.lower() in {".csv", ".zip"})
    if len(files) > MAX_PENDING_FILES:
        raise ValueError("incoming admite hasta 100 fuentes pendientes")
    for path in files:
        if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_UPLOAD_BYTES:
            raise ValueError(f"fuente inválida o mayor de 25 MiB: {path.name}")
    return files
