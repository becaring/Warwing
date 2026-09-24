"""Execute actual generated logging and finite native synchronization contracts."""
from pathlib import Path
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'scratch/port-xdk/tests'

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    compat = ROOT / 'platform/xbox360/cpp-compat'
    assert not (compat / 'port/color_math.h').exists()
    assert not (compat / 'port/timing.h').exists()
    ui=(ROOT/'scratch/port-xdk/compile-tree/port/gui/UIWidgets.cpp').read_text()
    assert '#include "math/color.h"' in ui
    assert all('Shipyard::Math::ColorByte(colorVec.'+component+')' in ui for component in 'xyz')
    source = Path(__file__).with_name('contracts.cpp')
    port = ROOT / 'scratch/port-xdk/compile-tree/port'
    inputs = [source, port / 'port_log.c', ROOT.parent/'LibUltraShip+Fast3D360/sources/crt/format.cpp', ROOT.parent/'LibUltraShip+Fast3D360/sources/clock/chrono.cpp', ROOT.parent/'LibUltraShip+Fast3D360/sources/async/native.cpp']
    batch = OUT / 'build-host.cmd'
    batch.write_text('@echo off\ncall "C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Auxiliary/Build/vcvars32.bat" >nul\ncl /nologo /TP /MT /EHsc /DSMASH360_CRT_HOST_TEST /DSHIPYARD_CRT_HOST_TEST /DSHIPYARD_CRT_SNPRINTF=shipyard_snprintf /D_CRT_SECURE_NO_WARNINGS /I"' + str(compat) + '" /I"' + str(ROOT.parent/'LibUltraShip+Fast3D360') + '" /I"' + str(ROOT.parent/'LibUltraShip+Fast3D360/sources') + '" /I"' + str(port) + '" /Fe:contracts.exe ' + ' '.join('"'+str(x)+'"' for x in inputs) + '\n')
    result = subprocess.run(['cmd.exe', '/d', '/c', str(batch)], cwd=OUT, capture_output=True)
    (OUT / 'host-build.log').write_bytes(result.stdout + result.stderr)
    assert result.returncode == 0, (result.stdout + result.stderr).decode(errors='replace')
    result = subprocess.run([str(OUT / 'contracts.exe')], cwd=OUT, capture_output=True)
    (OUT / 'host-run.log').write_bytes(result.stdout + result.stderr)
    assert result.returncode == 0, (result.stdout + result.stderr).decode(errors='replace')
    sdk = Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')
    command = [str(sdk / 'bin/win32/cl.exe'), '/nologo', '/c', '/TP', '/MT', '/EHsc', '/O2', '/D_XBOX', '/DNOMINMAX', '/I'+str(compat), '/I'+str(ROOT.parent/'LibUltraShip+Fast3D360'), '/I'+str(ROOT.parent/'LibUltraShip+Fast3D360/sources'), '/I'+str(port), '/I'+str(sdk/'include/xbox'), '/FAsc', '/Fa'+str(OUT/'contracts.asm'), '/Fo'+str(OUT/'contracts.obj'), str(source)]
    result = subprocess.run(command, cwd=OUT, capture_output=True)
    (OUT / 'native-build.log').write_bytes(result.stdout + result.stderr)
    assert result.returncode == 0, (result.stdout + result.stderr).decode(errors='replace')
    assembly = (OUT/'contracts.asm').read_text()
    for instruction in ['ldarx', 'stdcx.', 'lwarx', 'stwcx.', 'sync']:
        assert instruction in assembly, 'Missing actual PowerPC atomic instruction '+instruction
    report = {'host_win32_ilp32': True, 'native_powerpc_compile': True, 'native_runtime': False,
              'inputs': {str(p.relative_to(ROOT) if p.is_relative_to(ROOT) else Path('shipyard')/p.relative_to(ROOT.parent/'LibUltraShip+Fast3D360')): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs + [ROOT.parent/'LibUltraShip+Fast3D360/sources/atomic/atomic.h',ROOT.parent/'LibUltraShip+Fast3D360/sources/math/color.h',ROOT.parent/'LibUltraShip+Fast3D360/sources/clock/sleep.h']},
              'checks': ['actual port_log lifecycle/full output/embedded NUL/z and mixed widths', '100000 concurrent 64-bit increments', '10000 release/acquire payload publication handshakes', '64-bit wrap/high-bit/CAS expected update', 'signed counter and bool CAS', 'unsigned fetch_sub wrap and signed INT_MIN subtraction', 'PowerPC 32/64 reservation instructions and full sync (exact acquire paths checked by test_atomic_ordering.py)', 'sleep zero/negative/ceil/INFINITE exclusion/actual elapsed', '40001 original color conversion comparisons plus NaN and infinities']}
    (OUT/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))

if __name__ == '__main__': main()
