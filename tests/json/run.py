"""Full actual JSON host contract, plus XDK leaf and honest blocker probes."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'upstream/dependencies/json'
OUT = ROOT / 'scratch/json-xdk'
TESTS = Path(__file__).resolve().parent


def execute(args, label, env=None, success=True):
    folder = OUT / label
    folder.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(list(map(str, args)), cwd=folder, env=env, text=True, capture_output=True)
    (folder / 'command.json').write_text(json.dumps(list(map(str, args)), indent=2) + '\n')
    (folder / 'result.log').write_text(result.stdout + result.stderr)
    if success and result.returncode:
        raise AssertionError(f'{label}: exit {result.returncode}\n{result.stdout}{result.stderr}')
    return result


def host():
    msvc = Path('C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Tools/MSVC/14.43.34808')
    sdk = Path('C:/Program Files (x86)/Windows Kits/10')
    env = os.environ.copy()
    env['PATH'] = str(msvc / 'bin/Hostx64/x64') + os.pathsep + env['PATH']
    env['INCLUDE'] = ';'.join(map(str, [msvc / 'include'] + [sdk / 'Include/10.0.26100.0' / p for p in ('ucrt', 'shared', 'um')]))
    env['LIB'] = ';'.join(map(str, [msvc / 'lib/x64'] + [sdk / 'Lib/10.0.26100.0' / p / 'x64' for p in ('ucrt', 'um')]))
    return msvc / 'bin/Hostx64/x64/cl.exe', env


def build_host(label, source, overlay=False, syntax=False, success=True, registry=False):
    compiler, env = host()
    folder = OUT / label
    command = [compiler, '/nologo', '/std:c++20', '/EHsc', '/MD', '/W4']
    if registry:
        command += ['/I' + str(OUT / 'registry-candidate/include')]
    if overlay:
        command += ['/FI' + str(ROOT / 'platform/xbox360/cpp-compat/json/config.h'),
                    '/I' + str(OUT / 'generated/include'), '/I' + str(ROOT / 'platform/xbox360/cpp-compat')]
    command += ['/I' + str(SOURCE / 'include')]
    command += ['/Zs'] if syntax else ['/Fo' + str(folder / 'test.obj'), '/Fe' + str(folder / 'test.exe')]
    command.append(source)
    result = execute(command, label, env, success)
    if syntax or result.returncode:
        return result
    return execute([folder / 'test.exe'], label + '-run')


def main():
    original = build_host('host-original', TESTS / 'reference.cpp')
    print('Full original JSON 3.12.0 rich host contract: PASS')
    assert (OUT / 'generated/manifest.json').exists(), 'generated actual JSON leaf lowering is not implemented'
    transformed = build_host('host-overlay', TESTS / 'reference.cpp', overlay=True)
    assert transformed.stdout == original.stdout, 'rich host behavior changed under generated overlay'
    build_host('escape-original', TESTS / 'escape.cpp')
    build_host('escape-overlay', TESTS / 'escape.cpp', overlay=True)
    print('Full rich host differential and actual RFC6901 leaf: PASS')
    sdk = Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')
    xdk_base = [sdk / 'bin/win32/cl.exe', '/nologo', '/EHsc', '/D_XBOX', '/D_XBOX_VER=200',
                '/I' + str(sdk / 'include/xbox')]
    native = execute(xdk_base + ['/c', '/DJSON_XDK_COMPILE_ONLY',
        '/FI' + str(ROOT / 'platform/xbox360/cpp-compat/json/config.h'),
        '/I' + str(OUT / 'generated/include'), '/I' + str(ROOT / 'platform/xbox360/cpp-compat'),
        '/I' + str(SOURCE / 'include'), '/Fo' + str(OUT / 'xdk-escape/escape.obj'), TESTS / 'escape.cpp'], 'xdk-escape')
    obj = (OUT / 'xdk-escape/escape.obj').read_bytes()
    assert int.from_bytes(obj[:2], 'little') == 0x1f2
    probes = {}
    for name in ('expression_sfinae', 'template_defaults', 'allocator_traits', 'alias_rewrite'):
        source = TESTS / ('probe_' + name + '.cpp')
        modern = build_host('host-probe-' + name, source, syntax=True, success=False)
        old = execute(xdk_base + ['/Zs', source], 'xdk-probe-' + name, success=False)
        probes[name] = {'host_exit': modern.returncode, 'xdk_exit': old.returncode}
    full = execute(xdk_base + ['/Zs', '/TP', '/I' + str(SOURCE / 'include'), SOURCE / 'include/nlohmann/json.hpp'],
                   'xdk-full-original', success=False)
    assert full.returncode != 0, 'update assessment: original JSON unexpectedly compiled'
    (OUT / 'verification.json').write_text(json.dumps({'reference_sha256': hashlib.sha256(original.stdout.encode()).hexdigest(),
        'rich_host_differential_pass': True, 'escape_object_sha256': hashlib.sha256(obj).hexdigest(),
        'probes': probes, 'full_xdk_json_compiles': False}, indent=2) + '\n')
    print(json.dumps(probes, indent=2))
    print('XDK actual leaf compiled; original generic basic_json remains uncompilable (logs recorded).')


if __name__ == '__main__':
    main()


