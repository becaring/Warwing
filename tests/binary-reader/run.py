"""Compare the actual pinned reader with generated reader code, then XDK-compile it."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from platform_base import resolve as resolve_platform_base
PLATFORM_BASE = resolve_platform_base(ROOT)
LUS = ROOT / 'upstream/BattleShip/libultraship'
OUT = ROOT / 'scratch/binary-reader-xdk'
NAMES = ('BinaryReader', 'MemoryStream', 'Stream')


def run(args, **kwargs):
    result = subprocess.run([str(a) for a in args], text=True, capture_output=True, **kwargs)
    if result.returncode:
        raise AssertionError(f'Command failed ({result.returncode}): {args}\n{result.stdout}{result.stderr}')
    return result.stdout


def fixtures():
    folder = OUT / 'fixtures'
    folder.mkdir(parents=True, exist_ok=True)
    paths = []
    for tag, order in enumerate(('<', '>')):
        values = (tag, -42, 240, -12345, 0xfedc, -123456789, 0xfedcba98,
                  -0x0102030405060708, 0xfedcba9876543210, 1.5, -1234.125,
                  float('inf'), -float('inf'), -0.0, -0.0)
        blob = struct.pack(order + 'BbBhHiIqQfdfdfd', *values)
        blob += struct.pack(order + 'IQ', 0x7fc00000, 0x7ff8000000000000)
        path = folder / ('little.bin' if not tag else 'big.bin')
        path.write_bytes(blob)
        paths.append(path)
    archive = ROOT / 'scratch/assets/BattleShip.o2r'
    with zipfile.ZipFile(archive) as z:
        candidates = []
        for name in z.namelist():
            blob = z.read(name)
            if len(blob) < 80 or blob[0] not in (0, 1):
                continue
            order = '<' if blob[0] == 0 else '>'
            if struct.unpack_from(order + 'I', blob, 4)[0] != 0x52454c4f:
                continue
            file_id, internal, external, count = struct.unpack_from(order + 'IHHI', blob, 64)
            if not count:
                continue
            candidates.append((file_id != 52, file_id, name, blob, order, internal, external, count))
        assert candidates, 'real RELO sample with external dependencies not found'
        _, file_id, name, blob, order, internal, external, count = sorted(candidates)[0]
    ids = struct.unpack_from(order + f'{count}H', blob, 76)
    size = struct.unpack_from(order + 'I', blob, 76 + count * 2)[0]
    payload = blob[80 + count * 2:]
    assert len(payload) == size
    value = 2166136261
    for byte in payload:
        value = ((value ^ byte) * 16777619) & 0xffffffff
    expected = 'reloc=' + ','.join(map(str, (file_id, internal, external, count, *ids, size, value)))
    path = folder / 'real-relo.bin'
    path.write_bytes(blob)
    paths.append(path)
    provenance = {'archive': str(archive), 'entry': name,
                  'entry_sha256': hashlib.sha256(blob).hexdigest(), 'expected': expected}
    (folder / 'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
    return paths, expected, provenance


def host_environment():
    compiler = Path('C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Tools/MSVC/14.43.34808')
    sdk = Path('C:/Program Files (x86)/Windows Kits/10')
    version = '10.0.26100.0'
    env = os.environ.copy()
    env['PATH'] = str(compiler / 'bin/Hostx64/x64') + os.pathsep + env['PATH']
    env['INCLUDE'] = ';'.join(map(str, [compiler / 'include'] + [sdk / 'Include' / version / p for p in ('ucrt', 'shared', 'um')]))
    env['LIB'] = ';'.join(map(str, [compiler / 'lib/x64'] + [sdk / 'Lib' / version / p / 'x64' for p in ('ucrt', 'um')]))
    return compiler / 'bin/Hostx64/x64/cl.exe', env


def host_build(label, source_root, fixture_paths):
    folder = OUT / label
    folder.mkdir(parents=True, exist_ok=True)
    compiler, env = host_environment()
    args = [compiler, '/nologo', '/std:c++20', '/EHsc', '/MD', '/W4',
            '/I' + str(source_root / 'include'), '/I' + str(ROOT / 'platform/xbox360/cpp-compat'),
            '/I' + str(PLATFORM_BASE / 'sources'),
            '/Fe:' + str(folder / 'reader.exe'), '/Fo:' + str(folder) + '/',
            Path(__file__).parent / 'reader_contract.cpp']
    args += [source_root / 'src/ship/utils/binarytools' / (name + '.cpp') for name in NAMES]
    log = run(args, env=env, cwd=folder)
    (folder / 'compile.log').write_text(log)
    result = run([folder / 'reader.exe', *fixture_paths], cwd=folder)
    (folder / 'result.txt').write_text(result)
    return result


def helpers_and_xdk(generated):
    folder = OUT / 'host-generated'
    compiler, env = host_environment()
    log = run([compiler, '/nologo', '/std:c++20', '/EHsc', '/MD', '/W4',
               '/I' + str(generated / 'include'), '/I' + str(ROOT / 'platform/xbox360/cpp-compat'),
               '/I' + str(PLATFORM_BASE / 'sources'),
               '/Fo:' + str(folder / 'helper_contract.obj'), '/Fe:' + str(folder / 'helper.exe'),
               Path(__file__).parent / 'helper_contract.cpp'], env=env, cwd=folder)
    (folder / 'helper-compile.log').write_text(log)
    run([folder / 'helper.exe'], cwd=folder)
    folder = OUT / 'xdk'
    folder.mkdir(parents=True, exist_ok=True)
    sdk = Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')
    sources = [generated / 'src/ship/utils/binarytools' / (name + '.cpp') for name in NAMES]
    sources.append(Path(__file__).parent / 'xdk_contract.cpp')
    command = [sdk / 'bin/win32/cl.exe', '/nologo', '/c', '/EHsc', '/D_XBOX', '/D_XBOX_VER=200',
               '/I' + str(sdk / 'include/xbox'), '/I' + str(generated / 'include'),
               '/I' + str(ROOT / 'platform/xbox360/cpp-compat'), '/I' + str(PLATFORM_BASE / 'sources'),
               '/Fo' + str(folder) + '/', *sources]
    log = run(command, cwd=folder)
    (folder / 'compile.log').write_text(log)
    objects = {}
    for source in sources:
        obj = folder / (source.stem + '.obj')
        data = obj.read_bytes()
        assert struct.unpack_from('<H', data)[0] == 0x1f2, f'{obj}: expected PowerPC BE COFF machine'
        objects[obj.name] = hashlib.sha256(data).hexdigest()
    return {'command': list(map(str, command)), 'objects_sha256': objects}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline-only', action='store_true')
    args = parser.parse_args()
    fixture_paths, expected, provenance = fixtures()
    original = host_build('host-original', LUS, fixture_paths)
    assert expected in original, 'original reader must agree with independent Python RELO decoding'
    print('Original reader host contract: PASS')
    if args.baseline_only:
        return
    generated = OUT / 'generated'
    assert (generated / 'manifest.json').exists(), 'generated reader compatibility output is not implemented'
    transformed = host_build('host-generated', generated, fixture_paths)
    assert original == transformed, f'original/generated behavior differs:\n{original}\n{transformed}'
    print('Generated reader differential contract: PASS')
    xdk = helpers_and_xdk(generated)
    print('Zero initialization / enum contracts / XDK production object compile: PASS')
    (OUT / 'verification.json').write_text(json.dumps({'fixture': provenance, 'original': original,
        'generated': transformed, 'xdk': xdk}, indent=2) + '\n')
    print(provenance['expected'])


if __name__ == '__main__':
    main()
