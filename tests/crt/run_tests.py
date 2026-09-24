"""Execute Win32 ILP32 CRT contract tests and compile native PPC adapter."""
from pathlib import Path
import json
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'scratch/crt-xdk/tests'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    vcvars = Path('C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Auxiliary/Build/vcvars32.bat')
    compat = ROOT / 'platform/xbox360/cpp-compat/crt'
    shipyard = ROOT.parent / 'LibUltraShip+Fast3D360'
    batch = OUT / 'build-host.cmd'
    batch.write_text('@echo off\ncall "' + str(vcvars) + '" >nul\ncl /nologo /TP /MT /EHsc /D_CRT_SECURE_NO_WARNINGS /DSMASH360_CRT_HOST_TEST /DSHIPYARD_CRT_HOST_TEST /DSHIPYARD_CRT_SNPRINTF=shipyard_snprintf /I"' + str(compat) + '" /I"' + str(shipyard) + '" /Fe:test.exe "' + str(shipyard / 'sources/crt/format.cpp') + '" "' + str(Path(__file__).with_name('snprintf_test.cpp')) + '"\n')
    result = subprocess.run(['cmd.exe','/d','/c',str(batch)],cwd=OUT,capture_output=True)
    (OUT / 'host-build.log').write_bytes(result.stdout+result.stderr)
    assert result.returncode==0,(result.stdout+result.stderr).decode(errors='replace')
    result = subprocess.run([str(OUT / 'test.exe')],cwd=OUT)
    assert result.returncode==0, 'Host CRT contract assertion ' + str(result.returncode)
    result = subprocess.run(['python',str(ROOT / 'tools/prepare_crt_xdk.py')],cwd=ROOT,capture_output=True)
    assert result.returncode==0,(result.stdout+result.stderr).decode(errors='replace')
    assembly=(ROOT/'scratch/crt-xdk/snprintf.asm').read_text()
    body=re.search(r'Shipyard_Vsnprintf\s+PROC(.*?)Shipyard_Vsnprintf ENDP',assembly,re.S)[1]
    assert 'bl\t_vscprintf' in body or re.search(r'bl\s+_vscprintf',body), 'Missing measured pass'
    assert 'bl\t_vsnprintf_s' in body or re.search(r'bl\s+_vsnprintf_s',body), 'Missing bounded render pass'
    report={'win32_ilp32_host_contract':True,'native_powerpc_object':True,'target_runtime_verified':False,
            'powerpc_va_list_copy_evidence':'disassembly contains separate _vscprintf and _vsnprintf_s calls',
            'covered':['truncation count and NUL','size0/null','size1','exact capacity','empty','guard bytes','z integer widths/precision/literal percent','negative signed size','copied va_list repeated mixed int/int64/double/string']}
    (OUT / 'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__': main()
