"""Prove that the real XDK compiler erases disabled production scopes."""
from pathlib import Path
import re
import subprocess
import unittest
ROOT=Path(__file__).resolve().parents[2]

class CompileModeTests(unittest.TestCase):
    def test_xdk_erases_scopes(self):
        out=ROOT/'scratch/perf-compile-mode';out.mkdir(parents=True,exist_ok=True)
        source=out/'probe.cpp'
        source.write_text('''#include "runtime/perf_trace.h"
extern "C" __declspec(noinline) unsigned ProfileProbe(unsigned value) {
    Smash360PerfScope outer(SMASH_PERF_DL_STEP);
    Smash360PerfScope inner(SMASH_PERF_INSTANCE_ACQUIRE,smash360_perf_detail);
    Smash360_PerfCount(SMASH_COUNT_COMMANDS);
    Smash360_PerfDetailCount(SMASH_COUNT_BOUNDS_HIT);
    return value+1;
}
''')
        sdk=Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')
        for mode in (1,0):
            obj=out/('probe%d.obj'%mode)
            args=[str(sdk/'bin/win32/cl.exe'),'/nologo','/c','/O2','/Ob2','/MT','/EHsc','/D_XBOX',
                  '/DSMASH360_ENABLE_FULL_PROFILING='+str(mode),'/I'+str(ROOT/'platform/xbox360'),
                  '/I'+str(sdk/'include/xbox'),'/Fo'+str(obj),str(source)]
            run=subprocess.run(args,capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)
            run=subprocess.run([str(sdk/'bin/win32/dumpbin.exe'),'/disasm',str(obj)],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)
            (out/('probe%d.asm'%mode)).write_text(run.stdout)
            block=re.search(r'(?m)^ProfileProbe:\s*\n(.*?)(?=^[^\s$]|\Z)',run.stdout,re.S|re.M)
            self.assertIsNotNone(block)
            ops=re.findall(r'(?m)^\s*[0-9A-Fa-f]+:\s+[0-9A-Fa-f]{8}\s+(\S+)',block[1])
            if mode:self.assertIn('mftb',ops,'positive control lacks real instrumentation')
            else:self.assertEqual(ops[:ops.index('blr')+1],['addi','blr'],'disabled scopes still execute work')

if __name__=='__main__':unittest.main()
