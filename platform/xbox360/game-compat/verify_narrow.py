"""Verify actual stage table lowering and XDK return-address intrinsic."""
from pathlib import Path
import json
import os
import re
import struct
import subprocess
import sys
from verify import ROOT, UPSTREAM, COMPAT, symbol_data
from narrow_c import lower_map_positions
from prepare_game_xdk import prepare_stdarg_header


def main():
    out = ROOT / 'scratch/game-xdk/verification/narrow'
    out.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(ROOT / 'scratch/host-python'))
    from xbox360_platform import c89_lower
    enums = re.search(rb'typedef enum GRKind\s*\{.*?\} GRKind;', (UPSTREAM / 'decomp/src/gr/grdef.h').read_bytes(), re.S)[0]
    vector = re.search(rb'typedef struct Vec3f\s*\{.*?\} Vec3f;', (UPSTREAM / 'decomp/include/ssb_types.h').read_bytes(), re.S)[0]
    positions = re.search(rb'Vec3f positions\[.*?\n\s*\};', (UPSTREAM / 'decomp/src/mn/mnmaps/mnmaps.c').read_bytes(), re.S)[0]
    positions = re.sub(rb'^#(?:ifdef PORT|endif)[^\n]*', b'', positions, flags=re.M)
    fixture = b'typedef float f32;\n' + enums + b'\n' + vector + b'\n' + positions + b'''
int main(void) { int i; if (sizeof(positions) != 204) return 1;
for (i=9; i<17; ++i) {
if (i==13 || i==14 || i==16) { if (positions[i].x!=1600.0F || positions[i].y!=1800.0F || positions[i].z!=0.0F) return 2; }
else if (positions[i].x!=0.0F || positions[i].y!=0.0F || positions[i].z!=0.0F) return 3; }
return positions[0].x==1700.0F && positions[8].x==1200.0F ? 0 : 4; }
'''
    converted, stats = lower_map_positions(fixture, c89_lower.PARSER)
    def run(command):
        result = subprocess.run(command, cwd=out, capture_output=True)
        assert result.returncode == 0, (result.stdout + result.stderr).decode(errors='replace')
        return result
    vcvars = Path('C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Auxiliary/Build/vcvars64.bat')
    for name, contents in [('original', fixture), ('lowered', converted)]:
        (out / (name + '.c')).write_bytes(contents)
        batch = out / 'host.cmd'
        batch.write_text('@echo off\ncall "' + str(vcvars) + '" >nul\ncl /nologo /TC /std:c11 /MT /Fe:' + name + '.exe /Fo:' + name + '.obj ' + name + '.c\n')
        run(['cmd.exe', '/d', '/c', str(batch)])
        run([str(out / (name + '.exe'))])
    xdk = Path(os.environ.get('XEDK', 'C:/Program Files (x86)/Microsoft Xbox 360 SDK'))
    flags = [str(xdk / 'bin/win32/cl.exe'), '/nologo', '/TC', '/MT', '/O2', '/c', '/D_XBOX', '/I' + str(COMPAT / 'include')]
    run(flags + ['/Folowered-ppc.obj', 'lowered.c'])
    data = symbol_data((out / 'lowered-ppc.obj').read_bytes(), 'positions', 204)
    values = struct.unpack('>51f', data)
    for i in range(9, 17):
        assert values[i*3:i*3+3] == ((1600.0, 1800.0, 0.0) if i in (13, 14, 16) else (0.0, 0.0, 0.0))
    (out / 'intrinsic.c').write_text('#include <intrin.h>\nvoid *caller_address(void) { return _ReturnAddress(); }\n')
    run(flags + ['/FAs', '/Faintrinsic.asm', '/Fointrinsic.obj', 'intrinsic.c'])
    assembly = (out / 'intrinsic.asm').read_text()
    body = re.search(r'caller_address PROC(.*?)caller_address ENDP', assembly, re.S)[1]
    assert re.search(r'\bmflr\s+r3', body) and not re.search(r'\bbl\s', body), body
    stdarg = prepare_stdarg_header(ROOT / 'scratch/game-xdk')
    (out / 'varargs.c').write_text('''#include <stdarg.h>
#ifndef va_copy
#define va_copy(destination, source) ((destination) = (source))
#endif
int variadic_probe(int marker, ...) {
va_list args, copy; int first, second; unsigned __int64 wide; double fraction;
va_start(args, marker); va_copy(copy, args);
first = va_arg(args, int); second = va_arg(copy, int);
wide = va_arg(args, unsigned __int64); fraction = va_arg(args, double);
va_end(copy); va_end(args);
return first + second + (int)wide + (int)fraction;
}
''')
    assembly_bodies = []
    for name, paths in [('sdk', []), ('mapped', [stdarg.parent])]:
        native_flags = [str(xdk / 'bin/win32/cl.exe'), '/nologo', '/TC', '/MT', '/O2', '/W3', '/D_XBOX', '/DPORT']
        native_flags += ['/I' + str(path) for path in paths + [xdk / 'include/xbox']]
        result = run(native_flags + ['/c', '/FAs', '/Fava-' + name + '.asm', '/Fova-' + name + '.obj', 'varargs.c'])
        assert b'C4013' not in result.stdout + result.stderr
        listing = (out / ('va-' + name + '.asm')).read_text()
        section = re.search(r'variadic_probe\s+PROC(.*?)variadic_probe ENDP', listing, re.S)[1]
        assembly_bodies.append([line.strip() for line in section.splitlines() if line.startswith('\t')])
    assert assembly_bodies[0] == assembly_bodies[1], 'Native variadic instructions differ'
    report = {'actual_stage_table_host_original_and_lowered': True, 'native_powerpc_zero_rows': [9,10,11,12,15],
              'native_return_address_intrinsic': 'mflr r3; no function call', 'stage_transform': stats,
              'mapped_stdarg_matches_sdk_powerpc_mixed_varargs': True}
    (out / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
