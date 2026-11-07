"""Keep native listings for /W3 pointer-width and undefined-behavior findings."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'scratch/game-xdk/abi-diagnostics'
FILES = ['decomp__src__lb__lbcommon', 'decomp__src__lb__lbparticle',
         'decomp__src__mn__mnvsmode__mnvsresults', 'decomp__src__libultra__n_audio__n_env',
         'decomp__src__sys__objdisplay', 'decomp__src__sys__taskman']


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    xdk = Path(os.environ.get('XEDK', 'C:/Program Files (x86)/Microsoft Xbox 360 SDK'))
    records = []
    for name in FILES:
        source = ROOT / 'scratch/game-xdk/sources' / (name + '.c')
        command = [str(xdk / 'bin/win32/cl.exe'), '/nologo', '/TC', '/MT', '/O2', '/fp:precise', '/W3', '/D_XBOX',
                   '/c', '/FAs', '/Fa' + str(OUT / (name + '.asm')), '/Fo' + str(OUT / (name + '.obj')), str(source)]
        result = subprocess.run(command, cwd=ROOT, capture_output=True)
        (OUT / (name + '.log')).write_bytes(result.stdout + result.stderr)
        assert result.returncode == 0
        records.append({'generated_source': str(source), 'sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                        'command': command, 'listing': str(OUT / (name + '.asm'))})
    def function(name, symbol):
        listing = (OUT / (name + '.asm')).read_text()
        return re.search(re.escape(symbol) + r'\s+PROC(.*?)' + re.escape(symbol) + ' ENDP', listing, re.S)[1]
    best = function(FILES[2], 'mnVSResultsGetBestManExcept')
    assert re.search(r'lwz\s+r11,first_man\$\(r1\)', best)
    assert not re.search(r'stw\s+[^\n]*first_man\$', best)
    matrix = function(FILES[0], 'func_ovl0_800CB140')
    # The fake expression has no optimized read of f[2][2]. Its value is
    # stored before the conversion routine (which ignores matrix column3).
    assert re.search(r'stfs\s+[^\n]*f\$\+28h', matrix)
    assert not re.search(r'lfs\s+[^\n]*f\$\+28h', matrix)
    for suffix in ('func_80026104_26D04', 'func_80026094_26C94'):
        body = function(FILES[3], suffix)
        assert re.search(r'lwz\s+r9,0\(r11\)', body) and not re.search(r'\bextsw\b', body)
    for pointer in [0, 1, 15, 16, 0x7ffffff0, 0x7fffffff, 0x80000000, 0x80000001, 0xfffffff0, 0xffffffff]:
        extended = pointer if pointer < 0x80000000 else pointer + 0xffffffff00000000
        native_round = (((extended + 15) & 0xffffffffffffffff) // 16 * 16) & 0xffffffff
        assert native_round == (pointer + 15) & 0xfffffff0
        assert (extended >= 0x10000000) == (pointer >= 0x10000000)
    report = {'commands': records,
              'n_env_pointer_roundtrips': 'compiled lwz/mr; upper bits unused',
              'taskman_alignment': 'unsigned64 round-up then low32 store, preserves high-bit pointer low32',
              'objdisplay': 'sign extension only enters diagnostic threshold; display-list address uses original lwz/stw',
              'lbparticle_shift': '16 banks constrain j to0..15; largest mask0x8000',
              'lbcommon_fake_uninitialized_read': 'source UB but dead read absent under pinned /O2; real matrix values stored',
              'mnvsresults_first_man': 'real reachable source UB; native uninitialized stack load before indexed reads',
              'source_changes': False, 'target_execution_verified': False}
    (OUT / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key:value for key,value in report.items() if key!='commands'}, indent=2))


if __name__ == '__main__': main()
