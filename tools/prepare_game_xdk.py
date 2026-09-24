"""Compile actual pinned BattleShip C sources with XDK, retaining all failures.

The SoH donor lowering is imported byte-for-byte, and only generated preprocessed
copies are compiled. No archive is produced unless every selected TU succeeds;
partial audits never become a misleading game library. No application/XEX link.
"""
from pathlib import Path
import argparse
import json
import os
import re
import subprocess
import sys
from game_source_manifest import ROOT, UPSTREAM, manifest, sha256
from platform_base import resolve as resolve_platform_base

COMPAT = ROOT / 'platform/xbox360/game-compat'
PLATFORM_BASE = resolve_platform_base(ROOT)


def write_report(output, report, name):
    temporary = output / (name + '.tmp.json')
    temporary.write_text(json.dumps(report, indent=2) + '\n')
    temporary.replace(output / (name + '.json'))


def float_max_spelling(source):
    """Use XDK float.h's FLT_MAX spelling for the same IEEE binary32 value.

    Skip strings/character literals, including #line paths. The pinned decimal
    is just above the exact maximum; modern C compilers round it to max, while
    XDK diagnoses overflow. Both spellings round to 0x7f7fffff (verified).
    """
    pattern = rb'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|(?<![\w.])3\.40282346639e\+38F(?![\w.])'
    count = 0
    def replace(match):
        nonlocal count
        if match[0] == b'3.40282346639e+38F':
            count += 1
            return b'3.402823466e+38F'
        return match[0]
    return re.sub(pattern, replace, source), count


def prepare_gbi_header(output):
    original = UPSTREAM / 'decomp/include/PR/gbi.h'
    if sha256(original) != 'dd78c1a53ee0834118df71758351c33af3380a39e7e5cee613907763140a9485':
        raise RuntimeError('GBI header changed; re-audit MSVC argument rescan adaptation')
    text = original.read_text(encoding='utf-8')
    for name, parameters in (('gDPSetCombineMode', 'pkt, a, b'), ('gsDPSetCombineMode', 'a, b')):
        target = name.replace('Mode', 'LERP')
        pattern = r'(#define\s+' + name + r'\([^\n]+?\)\s+)' + target + r'\([^\n]+\)'
        text, count = re.subn(pattern, lambda match: match[1] +
                             'SMASH360_GBI_APPLY(' + target + ', (' + parameters + '))', text)
        if count != 1:
            raise RuntimeError('Expected exactly one upstream macro definition: ' + name)
    # XDK gives a mixed-size bitfield its own storage unit. These two legacy
    # packet views therefore become 12 bytes and inflate Gfx to 16, whereas
    # Fast3D consumes 8-byte packets on Xenon. Preserve the N64 byte/bit layout:
    # the pop parameter shares the second u32; color's first four bytes are
    # four byte fields. No command encoding or pointer width changes.
    for old, new in (
        ('unsigned char\tparam:8;', 'unsigned int\tparam:8;'),
        ('int\t\tcmd:8;\n\t\tunsigned char\tpad;',
         'unsigned char\tcmd;\n\t\tunsigned char\tpad;'),
    ):
        if text.count(old) != 1:
            raise RuntimeError('Expected one mixed-storage GBI packet member: ' + old)
        text = text.replace(old, new)
    text = text.replace('} Gfx;', '} Gfx;\n#if defined(_XBOX) && defined(_M_PPC)\n'
                        'typedef char Smash360GfxPacketMustBeEightBytes[(sizeof(Gfx) == 8) ? 1 : -1];\n'
                        '#endif')
    generated = output / 'header-overlay/PR/gbi.h'
    generated.parent.mkdir(parents=True, exist_ok=True)
    generated.write_text('#line 1 "' + original.as_posix() + '"\n' + text, encoding='utf-8')
    return generated


def prepare_stdarg_header(output):
    original = UPSTREAM / 'decomp/include/stdarg.h'
    if sha256(original) != '61d2fd3e871272ac1081cf46a8a801307fbaf5bcccc51edbf51e1c33bc8c2ee9':
        raise RuntimeError('stdarg header changed; re-audit native variadic ABI')
    source = original.read_text(encoding='utf-8')
    for operation in ('start', 'arg', 'end'):
        old = '#define va_' + operation + ' __crt_va_' + operation
        if source.count(old) != 1:
            raise RuntimeError('Expected one desktop va macro: ' + operation)
        source = source.replace(old, '#define va_' + operation + ' _crt_va_' + operation)
    source = source.replace('#define va_copy __crt_va_copy', '#define va_copy(destination, source) ((destination) = (source))')
    target = output / 'c-language-overlay/decomp/include/stdarg.h'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('#line 1 "' + original.as_posix() + '"\n' + source, encoding='utf-8')
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', choices=('us', 'jp'), default='us')
    parser.add_argument('--source', action='append', help='Exact upstream-relative TU; repeatable')
    parser.add_argument('--limit', type=int, help='Audit first N TUs, never archive a subset')
    parser.add_argument('--generated-include', type=Path, action='append', default=[])
    parser.add_argument('--source-overlay', type=Path, action='append', default=[], help='Sparse source overlay; repeatable, conflicting replacements rejected')
    parser.add_argument('--archive', action='store_true', help='Create static library only if all C TUs pass')
    parser.add_argument('--keep-going', action='store_true')
    parser.add_argument('--audit-name', default='compile-audit', help='Report basename under scratch/game-xdk')
    args = parser.parse_args()
    if not re.fullmatch(r'[a-zA-Z0-9_-]+', args.audit_name):
        parser.error('audit-name must be a plain alphanumeric basename')
    output = ROOT / 'scratch/game-xdk'
    for directory in ('sources', 'objects', 'logs', 'drivers'):
        (output / directory).mkdir(parents=True, exist_ok=True)
    (output / 'drivers' / (sha256(__file__) + '.py')).write_bytes(Path(__file__).read_bytes())
    # Install with: python -m pip install --target scratch/host-python
    # tree-sitter==0.25.2 tree-sitter-c==0.24.1
    sys.path.insert(0, str(ROOT / 'scratch/host-python'))
    sys.path.insert(0, str(COMPAT))
    from typed_generic import lower_port_generics, lower_rumble_initializers
    from semantic_bool import lower_booleans
    from narrow_c import lower_scene_typeof, lower_map_positions
    from source_tree import stage_sources
    from xbox360_platform import c89_lower
    data = manifest(args.version)
    gbi_header = prepare_gbi_header(output)
    stdarg_header = prepare_stdarg_header(output)
    crt_header = PLATFORM_BASE / 'sources/crt/format.h'
    # Make the narrow GBI adaptation another regular upstream-relative overlay.
    gbi_overlay = output / 'gbi-source-overlay'
    gbi_target = gbi_overlay / 'decomp/include/PR/gbi.h'
    gbi_target.parent.mkdir(parents=True, exist_ok=True)
    gbi_target.write_bytes(gbi_header.read_bytes())
    compile_tree = output / 'compile-tree'
    staged_inputs = stage_sources(UPSTREAM, compile_tree,
                                 [source['path'] for source in data['sources']],
                                 [*args.source_overlay, gbi_overlay, stdarg_header.parents[2]])
    (output / 'staged-inputs.json').write_text(json.dumps(staged_inputs, indent=2) + '\n')
    (output / 'source-manifest.json').write_text(json.dumps(data, indent=2) + '\n')
    sources = data['sources']
    if args.source:
        selected = set(args.source)
        sources = [source for source in sources if source['path'] in selected]
        if selected != {source['path'] for source in sources}:
            parser.error('A requested source is not in the pinned upstream C selection')
    if args.limit:
        sources = sources[:args.limit]
    xdk = Path(os.environ.get('XEDK', r'C:\Program Files (x86)\Microsoft Xbox 360 SDK'))
    compiler = xdk / 'bin/win32/cl.exe'
    definitions = ['_XBOX', 'XBOX', 'SMASH_XBOX360', 'NDEBUG', 'NOMINMAX',
                   '_CRT_SECURE_NO_WARNINGS', '_USE_MATH_DEFINES', '_MBCS',
                   'REGION_' + args.version.upper() + '=1', 'VERSION_' + args.version.upper() + '=1',
                   'NON_MATCHING=1', 'NON_EQUIVALENT=1', 'AVOID_UB=1', 'PORT=1',
                   'F3DEX_GBI_2=1', '_LANGUAGE_C', 'N_MICRO=1',
                   'CIMGUI_DEFINE_ENUMS_AND_STRUCTS', 'DISABLE_SCRIPTING=1']
    if args.version == 'us':
        definitions += ['PORT_HIRES_ENABLED=1']
    common = [str(compiler), '/nologo', '/TC', '/MT', '/O2', '/fp:precise', '/W3']
    common += ['/D' + item for item in definitions]
    report = {'schema': 1, 'scope': 'Native C objects only; platform link, remaining ABI/endian integration and execution unproven',
              'compiler': str(compiler), 'compiler_sha256': sha256(compiler),
              'driver_sha256': sha256(__file__),
              'lowering_source': str((PLATFORM_BASE / 'python/xbox360_platform/c89_lower.py').resolve()),
              'lowering_sha256': sha256(PLATFORM_BASE / 'python/xbox360_platform/c89_lower.py'),
              'typed_generic_sha256': sha256(COMPAT / 'typed_generic.py'),
              'semantic_bool_sha256': sha256(COMPAT / 'semantic_bool.py'),
              'narrow_c_sha256': sha256(COMPAT / 'narrow_c.py'),
              'staging_sha256': sha256(COMPAT / 'source_tree.py'),
              'staged_inputs_sha256': sha256(output / 'staged-inputs.json'),
              'selected': len(sources), 'total': len(data['sources']), 'results': [],
              'platform_link_dependencies': ['char *XboxEnv_Get(const char *name)', 'extern float __libm_qnan_f', 'int snprintf(char *, size_t, const char *, ...)'],
              'stdarg_header': {'source_sha256': sha256(UPSTREAM / 'decomp/include/stdarg.h'), 'generated_sha256': sha256(stdarg_header)},
              'gbi_header': {'source_sha256': sha256(UPSTREAM / 'decomp/include/PR/gbi.h'),
                             'generated_sha256': sha256(gbi_header), 'generated': str(gbi_header)},
              'parser_dependency_files': {
                  str(path.relative_to(ROOT)): sha256(path)
                  for package in ('tree_sitter', 'tree_sitter_c')
                  for path in sorted((output / 'python-tools' / package).rglob('*'))
                  if path.suffix in ('.py', '.pyd')}}
    if args.source_overlay:
        report['overlay_inputs'] = {str(path.resolve()): sha256(path)
                                    for overlay in args.source_overlay
                                    for path in sorted(overlay.rglob('*')) if path.is_file()}
    objects = []
    for source in sources:
        path = UPSTREAM / source['path']
        compiled_input = compile_tree / source['path']
        name = source['path'].replace('/', '__').removesuffix('.c')
        generated = output / 'sources' / (name + '.c')
        obj = output / 'objects' / (name + '.obj')
        # Preserve BattleShip's separate game/port include universes.
        includes = list(args.generated_include)
        includes = [compile_tree, COMPAT / 'include'] + includes
        if source['upstream_target'] == 'ssb64_game':
            includes += [compile_tree / sub for sub in ('include', 'decomp/include')]
        includes += [compile_tree / sub for sub in ('decomp/src', 'port', 'debug_tools',
                    'libultraship/src', 'libultraship/include')]
        includes += [PLATFORM_BASE, xdk / 'include/xbox']
        flags = common + ['/FI' + str(COMPAT / 'compiler_compat.h')]
        # These are the selected C snprintf callers; no new declarations or
        # standard-header include ordering is imposed on unrelated game TUs.
        if source['path'].startswith(('debug_tools/acmd_trace/', 'debug_tools/gbi_trace/')):
            flags += ['/FI' + str(crt_header)]
        flags += ['/I' + str(item.resolve()) for item in includes]
        preprocess = flags + ['/E', str(compiled_input)]
        run = subprocess.run(preprocess, cwd=ROOT, capture_output=True)
        log = output / 'logs' / (name + '.log')
        log.write_bytes(run.stderr)
        record = dict(source, preprocess_command=preprocess, preprocess_exit=run.returncode,
                      log=str(log.relative_to(ROOT)), compiled_input=str(compiled_input),
                      compiled_input_sha256=sha256(compiled_input))
        if run.returncode == 0:
            corrected, literal_changes = float_max_spelling(run.stdout)
            platform_constant = False
            if source['path'] == 'port/stubs/libc_compat.c':
                if source['sha256'] != '69b898f33608f51f2f8faa7643fcb49f21fe4835ccd823bc78fd90b0a91b3602':
                    raise RuntimeError('libc_compat changed; re-audit platform NaN declaration')
                if corrected.count(b'f32 __libm_qnan_f = NAN;') != 1:
                    raise RuntimeError('Expected exactly one canonical NaN definition')
                corrected = corrected.replace(b'f32 __libm_qnan_f = NAN;', b'extern f32 __libm_qnan_f;')
                platform_constant = True
            selected_generics, unknown_generics = [], []
            if b'_Generic' in corrected:
                corrected, selected_generics, unknown_generics = lower_port_generics(corrected, c89_lower.PARSER)
            rumble_initializers = None
            if source['path'] == 'decomp/src/gm/gmrumble.c':
                corrected, rumble_initializers = lower_rumble_initializers(corrected, c89_lower.PARSER)
            boolean_lowering = None
            if b'_Bool' in corrected:
                corrected, boolean_lowering = lower_booleans(corrected, c89_lower.PARSER)
            narrow = None
            if source['path'] == 'decomp/src/sc/scmanager.c':
                if source['sha256'] != '75ac154f1b590f4b03210686b7bbd29bd29cfccee956b6db70eb680110f0dead':
                    raise ValueError('Scene manager source changed; re-audit typeof')
                corrected, narrow = lower_scene_typeof(corrected)
            if source['path'] == 'decomp/src/mn/mnmaps/mnmaps.c':
                if source['sha256'] != 'eb7690cd1b8caf9a96a4a6cf4c62225e782dce6810b1857a42617708350d0924':
                    raise ValueError('Map source changed; re-audit designated array')
                corrected, narrow = lower_map_positions(corrected, c89_lower.PARSER)
            lowered, changes = c89_lower.lower(corrected, float_union_type=b'CutsceneData')
            generated.write_bytes(lowered)
            dependencies = {str(path.resolve()): sha256(path), str(compiled_input.resolve()): sha256(compiled_input)}
            for match in re.finditer(rb'^#line \d+ "([^"\r\n]+)"', run.stdout, re.M):
                dependency = Path(match[1].decode('utf-8', errors='replace'))
                if dependency.is_file():
                    dependencies[str(dependency.resolve())] = sha256(dependency)
            record.update(dependencies=dependencies, generated=str(generated.relative_to(ROOT)),
                          generated_sha256=sha256(generated), lowered_scopes=changes,
                          float_max_spelling_changes=literal_changes,
                          selected_generics=selected_generics, unresolved_generics=unknown_generics)
            record['platform_nan_declaration'] = platform_constant
            record['rumble_initializers'] = rumble_initializers
            record['boolean_lowering'] = boolean_lowering
            record['narrow_c_syntax'] = narrow
            command = common + ['/c', '/Fo' + str(obj), str(generated)]
            run = subprocess.run(command, cwd=ROOT, capture_output=True)
            with log.open('ab') as stream:
                stream.write(run.stdout + run.stderr)
            record.update(compile_command=command, compile_exit=run.returncode)
            if run.returncode == 0:
                objects.append(obj)
                record.update(object=str(obj.relative_to(ROOT)), object_sha256=sha256(obj))
        report['results'].append(record)
        report['passed'] = len(objects)
        if len(report['results']) % 16 == 0 or run.returncode != 0:
            write_report(output, report, args.audit_name)
        print(('PASS ' if run.returncode == 0 else 'FAIL ') + source['path'], flush=True)
        if run.returncode != 0 and not args.keep_going:
            break
    write_report(output, report, args.audit_name)
    complete = len(objects) == len(data['sources'])
    if args.archive and complete:
        response = output / 'archive.rsp'
        archive = output / 'BattleShipGameC.lib'
        response.write_text('/nologo\n/OUT:"' + str(archive) + '"\n' +
                            '\n'.join('"' + str(obj) + '"' for obj in objects) + '\n')
        command = [str(xdk / 'bin/win32/lib.exe'), '@' + str(response)]
        run = subprocess.run(command, cwd=ROOT, capture_output=True)
        (output / 'logs/archive.log').write_bytes(run.stdout + run.stderr)
        report['archive_exit'] = run.returncode
        if run.returncode == 0:
            report.update(archive=str(archive.relative_to(ROOT)), archive_sha256=sha256(archive))
        write_report(output, report, args.audit_name)
        if run.returncode:
            return run.returncode
    elif args.archive:
        print('Archive withheld: complete upstream C source selection has not compiled.')
    print(f'{len(objects)}/{len(report["results"])} attempted TUs compiled; {len(data["sources"])} total')
    return 0 if len(objects) == len(sources) and (not args.archive or complete) else 1


if __name__ == '__main__':
    sys.exit(main())
