#!/usr/bin/env python3
"""Empaqueta sólo el sitio y comprueba ambos motores antes de desplegar Pages."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

from audit_data_integrity import audit

ROOT = Path(__file__).resolve().parents[1]
FILES = ('index.html', 'sw.js', 'manifest.webmanifest')
FOLDERS = {'css': {'.css'}, 'js': {'.js'}, 'data': {'.js', '.json'},
    'assets': {'.svg', '.webp', '.png', '.jpg', '.jpeg', '.gif'},
    'icons': {'.png', '.svg', '.ico'}, 'vendor': {'.js'}, 'docs/guias': {'.pdf'}}


def copy_public(root: Path, output: Path) -> None:
    root, output = root.resolve(), output.resolve()
    if output == root or root in output.parents:
        raise ValueError('el artefacto debe construirse fuera del repositorio')
    output.mkdir(parents=True, exist_ok=False)
    for relative in FILES:
        source = root / relative
        if source.is_symlink():
            raise ValueError('no se publican enlaces')
        shutil.copy2(source, output / relative)
    for folder, suffixes in FOLDERS.items():
        for source in sorted((root / folder).rglob('*')):
            if source.is_symlink():
                raise ValueError('no se publican enlaces')
            if not source.is_file() or source.suffix.lower() not in suffixes:
                continue
            target = output / source.relative_to(root)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    html = (output / 'index.html').read_text(encoding='utf-8')
    for reference in re.findall(r'(?:src|href)="([^"]+)"', html):
        if re.match(r'^(?:https?:|#|data:|mailto:)', reference):
            continue
        path = output / reference.split('?', 1)[0]
        if not path.is_file():
            raise ValueError('recurso público faltante: ' + reference)
    (output / '.nojekyll').touch()


def build(root: Path, output: Path) -> dict:
    copy_public(root, output)
    result = audit(output)
    if result['status'] != 'ok':
        raise ValueError('el artefacto público no coincide con los sellos de los motores')
    source = (output / 'data/manifest.js').read_bytes()
    manifest = json.loads(source.decode().split('=', 1)[1].strip()[:-1])
    report = {'status': 'ok', 'files': sum(p.is_file() for p in output.rglob('*')),
        'verifiedStoreFiles': result['files'], 'weeks': manifest['weeks'],
        'pendingWeeks': manifest.get('pendingWeeks', []),
        'manifestSha256': hashlib.sha256(source).hexdigest()}
    (output / 'data/publication.json').write_text(json.dumps(report, ensure_ascii=False) + '\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(ROOT, args.output), ensure_ascii=False))
