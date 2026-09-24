"""Verify the pinned libzip source and invoke Shipyard's XDK projection."""

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from platform_base import resolve as resolve_platform_base
SOURCE = ROOT / 'upstream/dependencies/libzip'
OWN = ROOT / 'platform/xbox360/cpp-compat/libzip'
OUT = ROOT / 'scratch/libzip-xdk/generated'
PLATFORM_BASE = resolve_platform_base(ROOT)
from xbox360_platform.libzip import project


def prepare():
    locks = json.loads((OWN / 'sources.lock.json').read_text())
    for name, digest in locks['files'].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError('libzip source drift: ' + name)
    manifest = project(SOURCE, OUT, SOURCE.relative_to(ROOT).as_posix())
    manifest['locks'] = locks
    receipt = OUT.parent / 'manifest.json'
    data = (json.dumps(manifest, indent=2) + '\n').encode('utf-8')
    if not receipt.exists() or receipt.read_bytes() != data:
        receipt.write_bytes(data)
    return manifest


if __name__ == '__main__':
    prepare()
    print('Generated pinned libzip native C runtime')
