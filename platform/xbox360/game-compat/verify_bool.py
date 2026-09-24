"""Execute original C11 versus closed boolean lowering; inspect native PPC ABI."""
import json
import os
from pathlib import Path
import subprocess
import sys
from verify import ROOT, COMPAT, UPSTREAM, symbol_data
from semantic_bool import lower_booleans

OUT = ROOT / 'scratch/game-xdk/verification/bool'


def run(command):
    result = subprocess.run(command, cwd=OUT, capture_output=True)
    if result.returncode:
        raise RuntimeError((result.stdout + result.stderr).decode(errors='replace'))
    return result


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(ROOT / 'scratch/game-xdk/python-tools'))
    from xbox360_platform import c89_lower
    fixture = b'''typedef struct { _Bool Cancelled; } IEvent;
typedef struct { IEvent Event; int value; } ActualShape;
int calls;
int next(void) { calls++; return 256; }
_Bool result(int x) { return x; }
int main(void) {
    int value = 1; void *pointer = &value; volatile double zero = 0.0;
    _Bool a = 256, b = -512, c = 0.25;
    IEvent event = {256}; ActualShape derived = {{512}, 7};
    if (!a || !b || !c || !event.Cancelled || !derived.Event.Cancelled) return 1;
    a = next(); if (a != 1 || calls != 1) return 2;
    a = 0; if (a) return 3;
    a = pointer; if (!a) return 4;
    event.Cancelled = -256; if (event.Cancelled != 1) return 5;
    if (result(512) != 1 || result(0) != 0 || (_Bool)-256 != 1) return 6;
    { int a = 256; a = 512; if (a != 512) return 7; }
    if (sizeof(IEvent) != 1 || sizeof(_Bool) != 1) return 8;
    a = zero / zero; if (a != 1) return 9;
    return 0;
}
'''
    lowered, stats = lower_booleans(fixture, c89_lower.PARSER)
    for bad in (b'_Bool *p;', b'_Bool a[2];', b'_Bool f(_Bool a);',
                b'void f(void) { _Bool a; a += 2; }',
                b'void f(void) { _Bool a; void *p = &a; }',
                b'void f(void) { _Bool a; a++; }'):
        try:
            lower_booleans(bad, c89_lower.PARSER)
        except ValueError:
            pass
        else:
            raise AssertionError('Unsupported bool accepted: ' + repr(bad))
    vcvars = Path('C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Auxiliary/Build/vcvars64.bat')
    for name, contents in [('original', fixture), ('lowered', lowered)]:
        source = OUT / (name + '.c')
        source.write_bytes(contents)
        batch = OUT / 'host.cmd'
        batch.write_text('@echo off\ncall "' + str(vcvars) + '" >nul\ncl /nologo /TC /std:c11 /MT /Od /Fe:' + name + '.exe /Fo:' + name + '.obj ' + name + '.c\n')
        run(['cmd.exe', '/d', '/c', str(batch)])
        run([str(OUT / (name + '.exe'))])
    xdk = Path(os.environ.get('XEDK', 'C:/Program Files (x86)/Microsoft Xbox 360 SDK'))
    cl = str(xdk / 'bin/win32/cl.exe')
    flags = [cl, '/nologo', '/MT', '/O2', '/D_XBOX', '/I' + str(COMPAT / 'include'),
             '/I' + str(UPSTREAM / 'libultraship/src'), '/I' + str(UPSTREAM / 'libultraship/include'),
             '/I' + str(UPSTREAM / 'include'), '/I' + str(UPSTREAM / 'port'), '/I' + str(xdk / 'include/xbox')]
    # Same actual header and functions are compiled in C11-lowered C and native
    # C++. Assembly and COFF are retained, including the unresolved C ABI call.
    code = '''#include <stddef.h>
#include "hooks/list/FighterEvent.h"
#include "ship/events/WindowEvents.h"
#ifdef __cplusplus
extern "C" {
#endif
extern bool external_bool(int);
bool bool_return(int value) { return value; }
int bool_call(int value) { return external_bool(value); }
int event_read(IEvent *event) { return event->Cancelled; }
void event_store(IEvent *event, int value) { event->Cancelled = value; }
void focus_store(WindowFocusEvent *event, int value) { event->Focused = value; }
unsigned int layout[] = {sizeof(IEvent), sizeof(FighterParentKindResolveEvent), offsetof(FighterParentKindResolveEvent, Event), offsetof(FighterParentKindResolveEvent, fkind), offsetof(FighterParentKindResolveEvent, resolved_fkind), sizeof(WindowFocusEvent), offsetof(WindowFocusEvent, Focused)};
#ifdef __cplusplus
}
#endif
'''
    source = OUT / 'native.c'
    source.write_text(code)
    pp = run(flags + ['/TC', '/E', str(source)]).stdout
    # offsetof itself takes a synthetic null-based field address. It is an ABI
    # assertion, not game code or a bool store; keep outside the conservative
    # escape audit, then compile against the transformed actual declarations.
    body, layout = pp.split(b'unsigned int layout[]', 1)
    converted, abi_stats = lower_booleans(body, c89_lower.PARSER)
    converted += b'unsigned int layout[]' + layout
    (OUT / 'converted.c').write_bytes(converted)
    for mode, filename in [('c', 'converted.c'), ('cpp', 'native.c')]:
        result = run(flags + (['/TC'] if mode == 'c' else ['/TP']) + ['/c', '/FAs', '/Fa' + mode + '.asm', '/Fo' + mode + '.obj', filename])
        (OUT / (mode + '.log')).write_bytes(result.stdout + result.stderr)
        coff = (OUT / (mode + '.obj')).read_bytes()
        assert coff[:2] == b'\xf2\x01'
        assert symbol_data(coff, 'layout', 28).hex() == '000000010000000c0000000000000004000000080000000200000001'
    # Byte-identical machine code proves return canonicalization, r3 low-byte
    # caller interpretation, and actual event byte load/store for these pairs.
    asm_c, asm_cpp = [(OUT / (mode + '.asm')).read_text() for mode in ('c', 'cpp')]
    import re
    def instructions(assembly, name):
        body = re.search(r'^' + name + r' PROC(.*?)^' + name + r' ENDP', assembly, re.S | re.M)[1]
        return [line.strip() for line in body.splitlines() if line.startswith('\t') and not line.lstrip().startswith(';')]
    evidence = {}
    for name in ('bool_return', 'bool_call', 'event_read', 'event_store', 'focus_store'):
        left, right = instructions(asm_c, name), instructions(asm_cpp, name)
        assert left == right, (name, left, right)
        evidence[name] = left
    report = {'host_original_and_lowered': True, 'unsupported_rejected': True,
              'actual_event_powerpc_layout': [1, 12, 0, 4, 8, 2, 1], 'native_cpp_c_assembly_equal': evidence,
              'fixture_lowering': stats, 'actual_header_lowering': abi_stats}
    (OUT / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
