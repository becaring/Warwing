"""Fail-closed state-key and exact cold-block preservation checks."""
from pathlib import Path
import importlib
import re
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
SHIPYARD=ROOT.parent/'LibUltraShip+Fast3D360'
TRAITS=ROOT/'platform/xbox360/cpp-compat/fast3d/triangle_traits.h'
sys.path.insert(0,str(ROOT/'tools'))

def projected_input():
    source=(ROOT/'upstream/BattleShip/libultraship/src/fast/interpreter.cpp').read_text(encoding='utf-8-sig')
    for name in ('vertex_packing_projection','material_math_projection','triangle_trace_projection',
                 'triangle_split_projection','shader_metadata_projection','triangle_pack_projection',
                 'triangle_constants_projection','combiner_lookup_projection','texture_binding_projection'):
        source=importlib.import_module(name).transform(source)
    return source

def remove_invalidations(text):
    projection=importlib.import_module('triangle_pipeline_projection')
    matches=list(re.finditer(r'\((?:gfx->)?mXboxPipelineKey.valid=false, (?:gfx->)?mRapi->\w+\(',text))
    for match in reversed(matches):
        end=projection._call_end(text,match.end()-1)
        if text[end+1]!=')':raise ValueError('changed invalidation expression')
        prefix=text[match.start():match.end()].split(', ',1)[1]
        text=text[:end+1]+text[end+2:]
        text=text[:match.start()]+prefix+text[match.end():]
    return text

def compile_run(test,driver,name):
    out=ROOT/'scratch/fast3d-xdk/triangle-pipeline-tests'/name;out.mkdir(parents=True,exist_ok=True)
    (out/'contract.cpp').write_text(driver)
    includes=[ROOT/'upstream/BattleShip/libultraship/include',ROOT/'platform/xbox360/cpp-compat',
              ROOT.parent/'LibUltraShip+Fast3D360/sources/value_types',
              ROOT.parent/'LibUltraShip+Fast3D360/sources',ROOT/'scratch/graphics-xdk/include']
    (out/'build.cmd').write_text('@echo off\ncall "C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Auxiliary/Build/vcvars32.bat" >nul\n'
        'cl /nologo /std:c++20 /O2 /fp:precise /EHsc /MT /DNOMINMAX '+
        ' '.join('/I"'+str(p)+'"' for p in includes)+' contract.cpp /Fe:contract.exe\nexit /b %errorlevel%\n')
    run=subprocess.run(['cmd','/d','/c',str(out/'build.cmd')],cwd=out,capture_output=True,text=True)
    (out/'compile.log').write_text(run.stdout+run.stderr)
    test.assertEqual(run.returncode,0,run.stdout+run.stderr)
    run=subprocess.run([str(out/'contract.exe')],cwd=out,capture_output=True,text=True)
    (out/'run.log').write_text(run.stdout+run.stderr)
    test.assertEqual(run.returncode,0,run.stdout+run.stderr)
    print(run.stdout.strip())

class TrianglePipelineTests(unittest.TestCase):
    def test_real_reconciliation_outputs_and_native_calls(self):
        projection=importlib.import_module('triangle_pipeline_projection')
        source=projected_input();transformed=projection.transform(source)
        method=transformed.split('__declspec(noinline) bool Interpreter::XboxPrepareTrianglePipeline(',1)[1]
        method=method.split('void Interpreter::GfxSpTri1(',1)[0]
        cold='bool Projected::XboxPrepareTrianglePipeline('+method
        publish=cold.split('// XBOX ORIGINAL RECONCILIATION END\n',1)[1]
        publish=publish.replace('    mXboxPipelineKey.Capture(*this,p);\n','')
        original=source[source.index(projection.BEGIN):source.index(projection.END)]
        original=original.replace('        return; // Shader compile failed — skip this draw call',
                                  '        return false; // Shader compile failed — skip this draw call')
        original='bool Original::Phase(SmashTriangleTrace& triangleTrace) {\n'+original+publish
        warm=transformed[transformed.index('    triangleTrace.Mark(SMASH_TRI_STATE);',
                                         transformed.index('void Interpreter::GfxSpTri1(')):]
        warm=warm.split('    const XboxTrianglePipelineResult& xboxPipeline=',1)[0]
        warm=warm.replace('if(!XboxPrepareTrianglePipeline(triangleTrace))return;',
                          'if(!XboxPrepareTrianglePipeline(triangleTrace))return false;')
        warm='bool Projected::Phase(SmashTriangleTrace& triangleTrace) {\n'+warm+'    return true;\n}\n'
        header=(ROOT/'upstream/BattleShip/libultraship/include/fast/interpreter.h').read_text(encoding='utf-8-sig')
        for name in ('shader_metadata_projection','triangle_constants_projection'):
            header=importlib.import_module(name).header(header)
        start=header.index('struct ColorCombiner {');combiner=header[start:header.index('\n};',start)+3]
        material=source.split('// XBOX MATERIAL MATH BEGIN\n',1)[1].split('// XBOX MATERIAL MATH END',1)[0]
        driver=Path(__file__).with_name('triangle_pipeline_phase_contract.cpp').read_text()
        driver=driver.replace('// EXTRACTED_COMBINER',combiner)
        driver=driver.replace('// CACHE_DECLARATIONS',TRAITS.read_text()+'\n'+(SHIPYARD/'sources/fast3d/triangle_pipeline.h').read_text())
        driver=driver.replace('// EXTRACTED_MATERIAL_HELPERS',material)
        driver=driver.replace('// EXTRACTED_PHASES',original+'\n'+cold+'\n'+warm)
        compile_run(self,driver,'phases')

    def test_extracted_cold_block_and_live_suffix_are_unchanged(self):
        source=projected_input()
        projection=importlib.import_module('triangle_pipeline_projection')
        transformed=projection.transform(source)
        cold=transformed.split('// XBOX ORIGINAL RECONCILIATION BEGIN\n',1)[1].split('// XBOX ORIGINAL RECONCILIATION END',1)[0]
        cold=remove_invalidations(cold)
        original=source[source.index(projection.BEGIN):source.index(projection.END)]
        expected=original.replace('    triangleTrace.Mark(SMASH_TRI_STATE);\n','').replace(
            '        return; // Shader compile failed — skip this draw call',
            '        return false; // Shader compile failed — skip this draw call')
        self.assertEqual(expected,cold,'cold state/import/flush/shader ordering changed')
        suffix=lambda text:text[text.index(projection.END):text.index('\nvoid Interpreter::GfxSpGeometryMode(')]
        self.assertEqual(suffix(source),suffix(transformed),'primitive depth/UV/diagnostics/area/packing changed')
        self.assertIn('if(!XboxPrepareTrianglePipeline(triangleTrace))return;',transformed)
        self.assertNotIn('textures_changed[0]=false',transformed)
        # Every explicit native-state operation gets a conservative invalidation
        # before it executes, including operations outside reconciliation.
        for operation in ('StartDrawToFramebuffer','SetColorWriteMask','CopyFramebuffer','UpdateFramebufferParameters'):
            self.assertIn('mXboxPipelineKey.valid=false, mRapi->'+operation+'(',transformed)
        warm=transformed.split('    if(!mXboxPipelineKey.Certify(*this)) {',1)[1].split('    const XboxTrianglePipelineResult&',1)[0]
        phases=re.findall(r'triangleTrace.Mark\((SMASH_TRI_\w+)\)',warm)
        self.assertEqual(phases,['SMASH_TRI_COMBINER','SMASH_TRI_TEXTURE','SMASH_TRI_SHADER'])

    def test_unbraced_native_calls_remain_one_statement(self):
        projection=importlib.import_module('triangle_pipeline_projection')
        source=projected_input().replace('        mRapi->SetUseAlpha(use_alpha);',
            '        if (use_alpha)\n            mRapi->SetUseAlpha(use_alpha);\n        else\n            mRapi->SetUseAlpha(false);')
        transformed=projection.transform(source)
        self.assertIn('if (use_alpha)\n            (mXboxPipelineKey.valid=false, mRapi->SetUseAlpha(use_alpha));\n        else\n            (mXboxPipelineKey.valid=false, mRapi->SetUseAlpha(false));',transformed)

    def test_complete_real_state_key(self):
        driver=Path(__file__).with_name('triangle_pipeline_contract.cpp').read_text()
        header=SHIPYARD/'sources/fast3d/triangle_pipeline.h'
        self.assertFalse((ROOT/'platform/xbox360/cpp-compat/fast3d/triangle_pipeline.h').exists())
        declarations=TRAITS.read_text()+'\n'+header.read_text()
        driver=driver.replace('// CACHE_DECLARATIONS',declarations)
        out=ROOT/'scratch/fast3d-xdk/triangle-pipeline-tests';out.mkdir(parents=True,exist_ok=True)
        (out/'contract.cpp').write_text(driver)
        includes=[ROOT/'upstream/BattleShip/libultraship/include',ROOT/'platform/xbox360/cpp-compat',
                  ROOT.parent/'LibUltraShip+Fast3D360/sources/value_types',ROOT/'scratch/graphics-xdk/include']
        (out/'build.cmd').write_text('@echo off\ncall "C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Auxiliary/Build/vcvars32.bat" >nul\n'
            'cl /nologo /std:c++20 /O2 /EHsc /MT /DNOMINMAX '+
            ' '.join('/I"'+str(p)+'"' for p in includes)+' contract.cpp /Fe:contract.exe\nexit /b %errorlevel%\n')
        run=subprocess.run(['cmd','/d','/c',str(out/'build.cmd')],cwd=out,capture_output=True,text=True)
        (out/'compile.log').write_text(run.stdout+run.stderr)
        self.assertEqual(run.returncode,0,run.stdout+run.stderr)
        run=subprocess.run([str(out/'contract.exe')],cwd=out,capture_output=True,text=True)
        (out/'run.log').write_text(run.stdout+run.stderr)
        self.assertEqual(run.returncode,0,run.stdout+run.stderr)
        print(run.stdout.strip())

if __name__=='__main__': unittest.main()
