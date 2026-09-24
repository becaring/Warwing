"""Execute the original and Xbox-projected real triangle packing loop."""
from pathlib import Path
import importlib
import subprocess
import sys
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from platform_base import resolve

class PackingTests(unittest.TestCase):
    def test_constant_cache_storage_comes_from_shipyard(self):
        source=(ROOT/'upstream/BattleShip/libultraship/include/fast/interpreter.h').read_text(encoding='utf-8-sig')
        projected=importlib.import_module('triangle_constants_projection').header(source)
        shared=resolve(ROOT)/'sources/fast3d/material_value_cache.h'
        self.assertTrue(shared.is_file())
        self.assertFalse((ROOT/'platform/xbox360/cpp-compat/fast3d/material_value_cache.h').exists())
        self.assertFalse((ROOT/'scratch/application-xdk/native/source/platform/xbox360/cpp-compat/fast3d/material_value_cache.h').exists())
        self.assertIn('#include "fast3d/material_value_cache.h"',projected)
        self.assertIn('Shipyard::Fast3D::MaterialValueCache<',projected)
        self.assertNotIn('xboxConstantsValid',projected)
        body=(ROOT/'upstream/BattleShip/libultraship/src/fast/interpreter.cpp').read_text(encoding='utf-8-sig')
        for name in ('vertex_packing_projection','material_math_projection','triangle_pack_projection'):
            body=importlib.import_module(name).transform(body)
        body=importlib.import_module('triangle_constants_projection').helpers(body)
        self.assertIn('comb->xboxConstants.Load(key,builder)',body)
        self.assertNotIn('xboxConstantsValid',body)

    def test_authoritative_vertex_stream(self):
        self.assertTrue((ROOT/'tools/vertex_packing_projection.py').exists(),'packing adapter is missing')
        module=importlib.import_module('vertex_packing_projection')
        source=(ROOT/'upstream/BattleShip/libultraship/src/fast/interpreter.cpp').read_text(encoding='utf-8-sig')
        projected=module.transform(source)
        projected=importlib.import_module('material_math_projection').transform(projected)
        pack=importlib.import_module('triangle_pack_projection')
        projected=pack.transform(projected)
        self.assertEqual(projected.count('#include "fast3d/coordinate.h"'),1)
        self.assertEqual(pack.HELPERS.count('Shipyard::Fast3D::Coordinate('),3)
        self.assertNotIn('float x=v0/32.0f',pack.HELPERS)
        constants=importlib.import_module('triangle_constants_projection')
        helpers='#include "fast3d/coordinate.h"\n'+constants.helpers(projected).replace('// TEST CONSTANT BUILD','++constantBuilds;')+pack.HELPERS
        projected=constants.transform(projected)
        functions=[]
        for name,text in [('Original',source),('Projected',projected)]:
            tri=text.split('void Interpreter::GfxSpTri1(',1)[1]
            start=tri.index('    // SoH packs the same attribute' if name=='Projected' else '    for (int i = 0; i < 3; i++) {\n        float z')
            end=tri.index('    if (++mBufVboNumTris == MAX_TRI_BUFFER)')
            functions.append('void Harness::'+name+'() {\n'+tri[start:end]+'\n}')
        driver=Path(__file__).with_name('vertex_packing_contract.cpp').read_text()
        out=ROOT/'scratch/fast3d-xdk/packing-tests';out.mkdir(parents=True,exist_ok=True)
        unit_color=resolve(ROOT)/'sources/fast3d/unit_color.h'
        self.assertTrue(unit_color.is_file())
        self.assertTrue(unit_color.with_name('coordinate.h').is_file())
        self.assertFalse((ROOT/'platform/xbox360/cpp-compat/fast3d/unit_color.h').exists())
        self.assertFalse((ROOT/'platform/xbox360/cpp-compat/fast3d/coordinate.h').exists())
        self.assertFalse((ROOT/'scratch/application-xdk/native/source/platform/xbox360/cpp-compat/fast3d/unit_color.h').exists())
        self.assertFalse((ROOT/'scratch/application-xdk/native/source/platform/xbox360/cpp-compat/fast3d/coordinate.h').exists())
        (out/'contract.cpp').write_text(driver.replace('// COMBINER_FIELDS',constants.FIELDS).replace('// EXTRACTED_FUNCTIONS',helpers+'\n'.join(functions)))
        batch=out/'build.cmd'
        batch.write_text('@echo off\ncall "C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Auxiliary/Build/vcvars32.bat" >nul\ncl /nologo /O2 /fp:precise /arch:SSE2 /EHsc /MT /I"'+str(unit_color.parent.parent)+'" /I"'+str(ROOT/'platform/xbox360/cpp-compat')+'" contract.cpp /Fe:packing.exe\nexit /b %errorlevel%\n')
        result=subprocess.run(['cmd','/d','/c',str(batch)],cwd=out,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        result=subprocess.run([str(out/'packing.exe')],cwd=out,capture_output=True,text=True)
        (out/'run.log').write_text(result.stdout+result.stderr)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        print(result.stdout.strip())

if __name__=='__main__':unittest.main()
