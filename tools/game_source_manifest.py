"""Deterministic C translation-unit selection from the pinned BattleShip CMake.

This is a compiler audit input, not a replacement game build. The exact CMake
revision is guarded: upstream selection changes require a fresh review.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / 'upstream/BattleShip'
CMAKE_SHA256 = '47197c26cdec6370ce0c6b31f802a598240c9375625417c9aded960679fab24f'


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def manifest(version='us'):
    cmake = UPSTREAM / 'CMakeLists.txt'
    if sha256(cmake) != CMAKE_SHA256:
        raise RuntimeError('Pinned CMake changed; re-audit source selection before compiling')
    text = cmake.read_text(encoding='utf-8')
    entries = {}

    def add(path, group, target):
        relative = path.relative_to(UPSTREAM).as_posix()
        if relative in entries:
            raise RuntimeError('Duplicate translation unit: ' + relative)
        entries[relative] = {'path': relative, 'sha256': sha256(path),
                             'selection': group, 'upstream_target': target}

    # Only the directory globs actually referenced by SSB64_DECOMP_SOURCES.
    block = re.search(r'set\(SSB64_DECOMP_SOURCES\s+(.*?)\n\)', text, re.S)[1]
    for var in re.findall(r'\$\{(SSB64_SRC_\w+)\}', block):
        glob = re.search(r'file\(GLOB_RECURSE\s+' + var + r'\s+([^\n]+)\)', text)[1]
        for pattern in re.findall(r'"([^"]+\.c)"', glob):
            directory = UPSTREAM / pattern.removesuffix('*.c')
            for path in sorted(directory.rglob('*.c')):
                relative = path.relative_to(UPSTREAM).as_posix()
                if relative.endswith('.inc.c'):
                    continue
                if version == 'jp' and relative in (
                        'decomp/src/mn/mncommon/mncongra.c',
                        'decomp/src/mn/mncommon/mnstartup.c'):
                    continue
                add(path, var, 'ssb64_game')
    for var in ('SSB64_LIBULTRA_PORT', 'SSB64_NAUDIO_PORT'):
        block = re.search(r'set\(' + var + r'\s+(.*?)\n\)', text, re.S)[1]
        for source in re.findall(r'^\s*(decomp/[^\s]+\.c)\b', block, re.M):
            add(UPSTREAM / source, var, 'ssb64_game')
    for path in sorted((UPSTREAM / 'port/stubs').glob('*.c')):
        add(path, 'SSB64_STUBS', 'ssb64_game')
    for path in sorted((UPSTREAM / 'port').rglob('*.c')):
        if 'stubs' not in path.relative_to(UPSTREAM / 'port').parts:
            add(path, 'SSB64_SRC_PORT', 'ssb64')
    for directory in ('debug_tools/gbi_trace', 'debug_tools/acmd_trace'):
        for path in sorted((UPSTREAM / directory).glob('*.c')):
            add(path, 'SSB64_DEBUG_TOOLS', 'ssb64')
    return {'schema': 1, 'region': version, 'cmake_sha256': CMAKE_SHA256,
            'scope': 'All upstream C translation units; C++ application dependencies excluded',
            'excluded': ['decomp/src/db', 'decomp/src/ovl8', '*.inc.c',
                         'decomp/src/libultra except explicit CMake lists'],
            'sources': [entries[key] for key in sorted(entries)]}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', choices=('us', 'jp'), default='us')
    parser.add_argument('--output', type=Path, default=ROOT / 'scratch/game-xdk/source-manifest.json')
    args = parser.parse_args()
    result = manifest(args.version)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(f'{len(result["sources"])} C translation units -> {args.output}')
