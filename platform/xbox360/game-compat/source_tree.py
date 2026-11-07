"""Build a compiler mirror of the source tree so quoted sibling includes obey overlays.

Reusable entry point:
    stage_sources(upstream, destination, translation_units, overlays=(), extra=())
All paths except the two roots are upstream-relative names. Overlays are
directories containing sparse replacements, normally already #line mapped.
Conflicting replacements are rejected: compose transforms before staging.
"""
from pathlib import Path
import hashlib
import json
import re


HEADER_ROOTS = ('include', 'decomp/include', 'decomp/src', 'port', 'debug_tools',
                'libultraship/src', 'libultraship/include')


def digest(content):
    return hashlib.sha256(content).hexdigest()


def starts_with_pragma_once(content):
    content = content.removeprefix(b'\xef\xbb\xbf')
    while True:
        content = content.lstrip()
        if content.startswith(b'//'):
            end = content.find(b'\n')
            content = content[end+1:] if end >= 0 else b''
        elif content.startswith(b'/*'):
            end = content.find(b'*/', 2)
            if end < 0:
                return False
            content = content[end+2:]
        else:
            return bool(re.match(rb'#pragma[ \t]+once(?:[ \t]*[\r\n]|$)', content))


def stage_sources(upstream, destination, translation_units, overlays=(), extra=()):
    upstream, destination = Path(upstream).resolve(), Path(destination).resolve()
    if upstream == destination or upstream.is_relative_to(destination):
        raise ValueError('Compiler mirror must not contain the authoritative source root')
    selected = set(translation_units) | set(extra)
    for directory in HEADER_ROOTS:
        for path in (upstream / directory).rglob('*'):
            if path.is_file() and (path.suffix.lower() in ('.h', '.hpp', '.hxx', '.inl', '.inc') or
                                   path.name.endswith(('.inc.c', '.inc.cpp'))):
                selected.add(path.relative_to(upstream).as_posix())
    replacements = {}
    for overlay in overlays:
        overlay = Path(overlay).resolve()
        if not overlay.is_dir():
            raise ValueError('Missing source overlay: ' + str(overlay))
        for path in sorted(overlay.rglob('*')):
            if not path.is_file():
                continue
            relative = path.relative_to(overlay).as_posix()
            # Do not import assets, metadata or repository internals into the
            # compiler mirror. Source maps belong to the audit, not includes.
            if path.suffix.lower() not in ('.h', '.hpp', '.hxx', '.inl', '.inc', '.c', '.cpp'):
                continue
            if any(part.startswith('.') for part in Path(relative).parts):
                raise ValueError('Hidden overlay input is not a compiler source: ' + relative)
            content = path.read_bytes()
            if relative in replacements and replacements[relative][1] != content:
                raise ValueError('Conflicting overlays for ' + relative + '; compose transformations first')
            replacements[relative] = (path, content)
            selected.add(relative)
    # Some C include fragments use .txt rather than .h/.inc.c (for example
    # ft/ftcollision.txt). Follow literal quoted includes within the source tree
    # instead of copying unrelated text/assets or relying on original siblings.
    pending = list(selected)
    examined = set()
    while pending:
        relative = pending.pop()
        if relative in examined:
            continue
        examined.add(relative)
        original = upstream / relative
        content = replacements[relative][1] if relative in replacements else original.read_bytes()
        for match in re.finditer(rb'^\s*#\s*include\s+["<]([^">\r\n]+)[">]', content, re.M):
            include = match[1].decode('utf-8')
            candidates = [original.parent / include, *[upstream / root / include for root in HEADER_ROOTS]]
            for candidate in candidates:
                candidate = candidate.resolve()
                if candidate.is_relative_to(upstream) and candidate.is_file():
                    name = candidate.relative_to(upstream).as_posix()
                    if name not in selected:
                        if b'\0' in candidate.read_bytes():
                            raise ValueError('Quoted include is binary, not C source: ' + name)
                        selected.add(name)
                        pending.append(name)
                    break
    index = destination / '.staged-files.json'
    if index.is_file():
        for relative in set(json.loads(index.read_text())) - selected:
            stale = (destination / relative).resolve()
            if not stale.is_relative_to(destination):
                raise ValueError('Prior generated path escaped compiler mirror')
            if stale.is_file():
                stale.unlink()
    records = []
    for relative in sorted(selected):
        rel = Path(relative)
        if rel.is_absolute() or '..' in rel.parts:
            raise ValueError('Source must remain within the mirror: ' + relative)
        original = upstream / relative
        if relative in replacements:
            input_path, content = replacements[relative]
        else:
            input_path = original
            content = ('#line 1 "' + original.as_posix() + '"\n').encode() + original.read_bytes()
        original_content = original.read_bytes() if original.is_file() else input_path.read_bytes()
        # XDK applies #pragma once to the current logical filename. Mark the
        # physical generated header before its original-path #line changes it.
        # Only hoist an unconditional initial pragma after whitespace/comments.
        if starts_with_pragma_once(original_content):
            content = b'#pragma once\n' + content
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or target.read_bytes() != content:
            target.write_bytes(content)
        records.append({'relative_path': relative, 'input': str(input_path),
                        'input_sha256': digest(input_path.read_bytes()),
                        'original_sha256': digest(original.read_bytes()) if original.is_file() else None,
                        'generated_sha256': digest(content)})
    index.write_text(json.dumps(sorted(selected), indent=2) + '\n')
    return records
