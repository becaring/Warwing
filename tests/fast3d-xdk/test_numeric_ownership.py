"""The selected Fast3D numeric path has one physical Shipyard owner."""
from pathlib import Path
import re
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[2]
SHARED = ROOT.parent / 'LibUltraShip+Fast3D360' / 'sources' / 'fast3d' / 'numeric.h'
LOCAL = ROOT / 'platform' / 'xbox360' / 'cpp-compat' / 'fast3d'


class NumericOwnershipTests(unittest.TestCase):
    def test_single_numeric_owner(self):
        shared = SHARED.read_text()
        self.assertIn('SignedShortFloat', shared)
        self.assertIn('TruncateLightChannel', shared)
        self.assertIn('DivideNormal127', shared)
        self.assertIn('DeferredVertexBytes', shared)
        self.assertIn('VertexColorLimit', shared)
        self.assertIn('VertexFogReciprocalFinite', shared)

        for name in ('vertex_lighting.h', 'light_batch.h'):
            text = (LOCAL / name).read_text()
            self.assertNotIn('static const float soh_', text, name)
            self.assertNotIn('__fctidz', text, name)
            self.assertNotIn('__stfiwx', text, name)
            self.assertNotIn('__fsel', text, name)
            self.assertNotIn('1.0/127.0', text, name)
        self.assertFalse((LOCAL / 'vertex_bytes.h').exists())
        self.assertFalse((LOCAL / 'vertex_select.h').exists())

    def test_xdk_publication_primitives(self):
        sdk = Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')
        out = ROOT / 'scratch/fast3d-xdk/numeric-tests'
        out.mkdir(parents=True, exist_ok=True)
        source = out / 'probe.cpp'
        source.write_text('''#include "fast3d/numeric.h"
extern "C" __declspec(noinline) void StoreWord(float v, unsigned i, Shipyard::Fast3D::DeferredVertexBytes* b) { b->Store(i,v); }
extern "C" __declspec(noinline) float FogReciprocal(float w) { return Shipyard::Fast3D::VertexFogReciprocalFinite(w); }
extern "C" __declspec(noinline) float ColorLimit(float v) { return Shipyard::Fast3D::VertexColorLimit(v); }
''')
        obj = out / 'probe.obj'
        result = subprocess.run([str(sdk / 'bin/win32/cl.exe'), '/nologo', '/c', '/O2', '/Ob2', '/MT',
                                 '/EHsc', '/fp:precise', '/D_XBOX', '/DNOMINMAX',
                                 '/I' + str(SHARED.parents[1]), '/I' + str(sdk / 'include/xbox'),
                                 '/Fo' + str(obj), str(source)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        result = subprocess.run([str(sdk / 'bin/win32/dumpbin.exe'), '/disasm', str(obj)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        (out / 'probe.asm').write_text(result.stdout)
        for name, required in [('StoreWord', ('fctiwz', 'stfiwx')),
                               ('FogReciprocal', ('fsel',)), ('ColorLimit', ('fsel',))]:
            block = re.search(r'(?m)^' + name + r':\s*\n(.*?)(?=^\S|\Z)', result.stdout, re.S | re.M)
            self.assertIsNotNone(block, name)
            ops = re.findall(r'(?m)^\s*[0-9A-Fa-f]+:\s+[0-9A-Fa-f]{8}\s+(\S+)', block[1])
            for opcode in required:
                self.assertIn(opcode, ops, name)


if __name__ == '__main__':
    unittest.main()
