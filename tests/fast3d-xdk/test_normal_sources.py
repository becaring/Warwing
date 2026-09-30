"""Ownership and PPC compile proof for within-command source-index reuse."""
from pathlib import Path
import importlib
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
import runpy as _shipyard_runpy

SHIPYARD_BASE = _shipyard_runpy.run_path(str(ROOT / "tools/platform_base.py"))["resolve"](ROOT)
SHIPYARD = SHIPYARD_BASE
sys.path.insert(0, str(ROOT / 'tools'))


class NormalSourcesTests(unittest.TestCase):
    def test_smash_projection_uses_shipyard_source_indices(self):
        module = importlib.import_module('vertex_reuse_projection')
        source = (ROOT / 'upstream/BattleShip/libultraship/src/fast/interpreter.cpp').read_text(encoding='utf-8-sig')
        projected = module.transform(source)
        self.assertTrue(projected.startswith('#include "fast3d/normal_sources.h"\n'),
                        'projected interpreter must include the Shipyard header')
        vertex = projected[projected.index('void Interpreter::GfxSpVertex('):
                           projected.index('void Interpreter::GfxSpModifyVertex(')]
        self.assertIn('Shipyard::Fast3D::BatchNormalSources(vertices,n_vertices,xboxShadeSources)', vertex)
        self.assertNotIn('SoH_BatchShadeSources', vertex)
        self.assertIn('!(mRsp->geometry_mode & G_LIGHTING_POSITIONAL)', vertex)
        self.assertIn('Shipyard::Fast3D::VertexSourceDisjoint(', vertex)

    def test_only_shipyard_header_is_available_and_ppc_compiles(self):
        header = SHIPYARD / 'sources/fast3d/normal_sources.h'
        self.assertTrue(header.exists())
        self.assertFalse((ROOT / 'platform/xbox360/cpp-compat/fast3d/shade_sources.h').exists())
        self.assertFalse((ROOT / 'scratch/application-xdk/native/source/platform/xbox360/cpp-compat/fast3d/shade_sources.h').exists())
        out = ROOT / 'scratch/fast3d-xdk/normal-sources-tests'
        out.mkdir(parents=True, exist_ok=True)
        probe = out / 'probe.cpp'
        probe.write_text('#include "fast3d/normal_sources.h"\n'
                         'extern "C" bool Probe(const void* vertices, unsigned count, unsigned char* indices) {'
                         ' return Shipyard::Fast3D::BatchNormalSources(vertices,count,indices); }\n')
        sdk = Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')
        result = subprocess.run([str(sdk / 'bin/win32/cl.exe'), '/nologo', '/c', '/O2', '/Ob2', '/MT',
                                 '/EHsc', '/D_XBOX', '/showIncludes',
                                 '/I' + str(ROOT / 'platform/xbox360/cpp-compat'),
                                 '/I' + str(SHIPYARD / 'sources'),
                                 '/I' + str(sdk / 'include/xbox'),
                                 '/Fo' + str(out / 'probe.obj'), str(probe)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(str(header).replace('\\', '/').casefold(),
                      (result.stdout + result.stderr).replace('\\', '/').casefold())


if __name__ == '__main__':
    unittest.main()
