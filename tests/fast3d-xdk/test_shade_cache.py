from pathlib import Path
import importlib
import subprocess
import sys
import unittest
import test_vertex_transform as vertex

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from platform_base import resolve
PLATFORM_BASE=resolve(ROOT)
OUT=ROOT/'scratch/fast3d-xdk/shade-cache-tests'

class ShadeCacheTests(unittest.TestCase):
    extra_includes=('#include "fast3d/light_batch.h"\n#include "fast3d/shade_cache.h"\n' +
                    importlib.import_module('shade_cache_projection').COLOR_ACCESSOR +
                    '\nnamespace Fast {static unsigned observedCrossShade;}\n')
    @staticmethod
    def extra_projection(text):
        text=importlib.import_module('light_batch_projection').transform(text)
        text=importlib.import_module('shade_cache_projection').transform(text)
        return text.replace('            if(xboxCachedShade) {','            if(xboxCachedShade) {\n                ++observedCrossShade;')
    @staticmethod
    def extra_driver(text):
        text=text.replace('RSP* mRsp; bool mFbActive; bool mWidescreenActive; XYWidthHeight mGameWindowViewport;',
                          'RSP* mRsp; bool mFbActive; bool mWidescreenActive; XYWidthHeight mGameWindowViewport; Shipyard::Fast3D::ShadeCache xboxShadeCache;')
        # The same interpreter instance must execute two commands: caches are
        # per-owner, and destroying a temporary interpreter discards its cache.
        command='    a.GfxSpVertex(count,3,vertices);b.GfxSpVertex(count,3,vertices);'
        text=text.replace(command,command+'\n'+command)
        return text.replace('    const unsigned edges=exceptionalCases();',
                            '    require(Fast::observedCrossShade>0,"cross-command texgen cache was never used");\n    const unsigned edges=exceptionalCases();')

    def test_actual_vertex_composition(self):
        vertex.OUT.mkdir(parents=True,exist_ok=True)
        vertex.TransformTests.test_actual_vertex_composition(self)

    def test_key_ownership_and_xdk(self):
        OUT.mkdir(parents=True,exist_ok=True)
        source=Path(__file__).with_name('shade_cache_cases.cpp')
        batch=OUT/'build.cmd'
        batch.write_text('@echo off\ncall "C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Auxiliary/Build/vcvars32.bat" >nul\n'
            'cl /nologo /std:c++20 /O2 /fp:precise /arch:SSE2 /EHsc /MT /I"'+str(PLATFORM_BASE/'sources')+
            '" "'+str(source)+'" /Fe:cases.exe\nexit /b %errorlevel%\n')
        def run(command,label):
            p=subprocess.run(command,cwd=OUT,capture_output=True,text=True)
            (OUT/(label+'.log')).write_text(p.stdout+p.stderr)
            self.assertEqual(p.returncode,0,p.stdout+p.stderr)
            return p.stdout
        run(['cmd','/d','/c',str(batch)],'host-compile')
        print(run([str(OUT/'cases.exe')],'host-run'))
        sdk=Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')
        obj=OUT/'cases.obj'
        run([str(sdk/'bin/win32/cl.exe'),'/nologo','/c','/O2','/Ob2','/MT','/EHsc','/fp:precise','/D_XBOX',
            '/I'+str(PLATFORM_BASE/'sources'),'/I'+str(sdk/'include/xbox'),'/Fo'+str(obj),str(source)],'xdk-compile')
        asm=run([str(sdk/'bin/win32/dumpbin.exe'),'/disasm',str(obj)],'xdk-disasm')
        self.assertIn('NativeShadeProbe',asm)
        self.assertNotIn('__dyn_tls_init',asm)
        symbols=run([str(sdk/'bin/win32/dumpbin.exe'),'/symbols',str(obj)],'xdk-symbols')
        self.assertNotIn('.tls',symbols)

    def test_member_ownership_projection(self):
        module=importlib.import_module('shade_cache_projection')
        self.assertEqual(Path(module.project.__code__.co_filename).resolve(),
                         (PLATFORM_BASE/'python/xbox360_platform/shade_cache.py').resolve())
        original=(ROOT/'upstream/BattleShip/libultraship/include/fast/interpreter.h').read_text(encoding='utf-8-sig')
        header=module.header(original)
        self.assertTrue(header.startswith('#include "fast3d/shade_cache.h"\n'))
        self.assertIn('int mInterpolationIndexTarget;\n    Shipyard::Fast3D::ShadeCache xboxShadeCache;',header)
        source=(ROOT/'upstream/BattleShip/libultraship/src/fast/interpreter.cpp').read_text(encoding='utf-8-sig')
        for name in ('vertex_lighting_projection','vertex_reuse_projection','vertex_transform_projection','light_batch_projection','shade_cache_projection'):
            source=importlib.import_module(name).transform(source)
        self.assertNotIn('xboxShadeCache.initialized=false;',source)
        self.assertNotIn('__declspec(thread) Shipyard::Fast3D::ShadeCache',source)
        self.assertFalse((ROOT/'platform/xbox360/cpp-compat/fast3d/shade_cache.h').exists())
        self.assertFalse((ROOT/'scratch/application-xdk/native/source/platform/xbox360/cpp-compat/fast3d/shade_cache.h').exists())

if __name__=='__main__':unittest.main()
