"""Execute the real shader-state block, observing metadata work and render calls."""
from pathlib import Path
import importlib
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
import runpy as _shipyard_runpy

SHIPYARD_BASE = _shipyard_runpy.run_path(str(ROOT / "tools/platform_base.py"))["resolve"](ROOT)
sys.path.insert(0,str(ROOT/'tools'))

def struct_body(text,name):
    start=text.index('struct '+name+' {')
    return text[start:text.index('\n};',start)+3]

class ShaderMetadataTests(unittest.TestCase):
    def test_shader_state_and_lifetime(self):
        source=(ROOT/'upstream/BattleShip/libultraship/src/fast/interpreter.cpp').read_text(encoding='utf-8-sig')
        header=(ROOT/'upstream/BattleShip/libultraship/include/fast/interpreter.h').read_text(encoding='utf-8-sig')
        # Baseline executes the real uncached path and fails the work-count check.
        if (ROOT/'tools/shader_metadata_projection.py').exists():
            projection=importlib.import_module('shader_metadata_projection')
            projected=projection.transform(source)
            projected_header=projection.header(header)
        else:
            projected=source;projected_header=header
        self.assertIn('#include "fast3d/shader_metadata_cache.h"', projected_header)
        self.assertIn('Shipyard::Fast3D::ShaderMetadataCache<16>', projected_header)
        self.assertNotIn('xboxShaderInfoBackend', projected_header)
        self.assertNotIn('xboxShaderInfoProgram', projected_header)
        functions=[]
        for name,text in [('Original',source),('Projected',projected)]:
            start=text.index('    struct ShaderProgram* prg = comb->prg[tm];')
            stop=text.index('    // PORT: G_ZS_PRIM source overrides',start)
            phase=text[start:stop]
            # The entire state block is authoritative: shader lookup, failure,
            # flushing, unload/load and alpha precede the metadata capture.
            functions.append('void '+name+'::Phase(unsigned tm,bool use_alpha) {\n'
                'ColorCombiner* comb=&mColorCombinerPool[0];\n'+phase+
                'result.valid=true;result.inputs=numInputs;result.used[0]=usedTextures[0];result.used[1]=usedTextures[1];result.clip=clip_parameters;\n}\n')
            init=text.split('    mRapi->Init();',1)[1].split('    mRapi->UpdateFramebufferParameters(',1)[0]
            functions.append('void '+name+'::Init(Backend* api) {mRapi=api;mRapi->Init();\n'+init+'}\n')
        old=struct_body(header,'ColorCombiner').replace('ColorCombiner','OriginalCombiner')
        new=struct_body(projected_header,'ColorCombiner').replace('ColorCombiner','ProjectedCombiner')
        driver=Path(__file__).with_name('shader_metadata_contract.cpp').read_text()
        driver=driver.replace('// EXTRACTED_COMBINERS',old+'\n'+new).replace('// EXTRACTED_FUNCTIONS','\n'.join(functions))
        out=ROOT/'scratch/fast3d-xdk/shader-metadata-tests';out.mkdir(parents=True,exist_ok=True)
        (out/'contract.cpp').write_text(driver)
        includes=[ROOT/'upstream/BattleShip/libultraship/include',ROOT/'platform/xbox360/cpp-compat',
                  SHIPYARD_BASE / 'sources',
                  SHIPYARD_BASE / 'sources/value_types',ROOT/'scratch/graphics-xdk/include']
        (out/'build.cmd').write_text('@echo off\ncall "C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Auxiliary/Build/vcvars32.bat" >nul\n'
            'cl /nologo /std:c++20 /O2 /fp:precise /EHsc /MT /DNOMINMAX '+
            ' '.join('/I"'+str(p)+'"' for p in includes)+' contract.cpp /Fe:contract.exe\nexit /b %errorlevel%\n')
        run=subprocess.run(['cmd','/d','/c',str(out/'build.cmd')],cwd=out,capture_output=True,text=True)
        (out/'compile.log').write_text(run.stdout+run.stderr)
        self.assertEqual(run.returncode,0,run.stdout+run.stderr)
        run=subprocess.run([str(out/'contract.exe')],cwd=out,capture_output=True,text=True)
        (out/'run.log').write_text(run.stdout+run.stderr)
        self.assertEqual(run.returncode,0,run.stdout+run.stderr)
        print(run.stdout.strip())

if __name__=='__main__':unittest.main()
