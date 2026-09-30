"""Compare extracted real cache/import dispatch against delayed-flush projection."""
from pathlib import Path
import importlib
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
import runpy as _shipyard_runpy

SHIPYARD_BASE = _shipyard_runpy.run_path(str(ROOT / "tools/platform_base.py"))["resolve"](ROOT)
sys.path.insert(0,str(ROOT/'tools'))

def function(text,signature):
    start=text.index(signature); brace=text.index('{',start); end=brace+1; depth=1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]

class TextureBindings(unittest.TestCase):
    def test_import_and_external_boundaries_remain_explicit(self):
        source=(ROOT/'upstream/BattleShip/libultraship/src/fast/interpreter.cpp').read_text(encoding='utf-8-sig')
        projection=importlib.import_module('texture_binding_projection')
        projected=projection.transform(source)
        # All decode/mask/UV behavior remains literally authoritative. Only
        # the existing framebuffer bind gains certificate invalidation.
        for method in ('ImportTextureMask','ImportTextureRgba16','ImportTextureRgba32',
                       'ImportTextureIA4','ImportTextureIA8','ImportTextureIA16',
                       'ImportTextureI4','ImportTextureI8','ImportTextureCi4','ImportTextureCi8',
                       'ImportTextureRaw','ImportTextureImg'):
            signature='void Interpreter::'+method+'('
            self.assertEqual(function(source,signature),function(projected,signature))
        imported=function(projected,'void Interpreter::ImportTexture(')
        inserted='''                // This API selects backend slot zero, even when the
                // source import tracks another tile. Invalidate all six.
                XboxInvalidateTextureBindings();
'''
        self.assertEqual(imported.replace(inserted,''),function(source,'void Interpreter::ImportTexture('))
        for signature in ('Interpreter::Interpreter()', 'void Interpreter::SpReset()', 'void Interpreter::Init('):
            self.assertIn('XboxInvalidateTextureBindings();',function(projected,signature))
        custom=function(projected,'bool gfx_set_timg_fb_handler_custom(')
        self.assertLess(custom.index('XboxInvalidateTextureBindings'),custom.index('SelectTextureFb'))
        gui=(ROOT/'upstream/BattleShip/libultraship/src/ship/window/gui/Gui.cpp').read_text(encoding='utf-8-sig')
        actual=function(projection.gui(gui),'void Gui::ImGuiRenderDrawData(')
        self.assertIn('interpreter->Flush();\n        interpreter->XboxInvalidateTextureBindings();',actual)
        self.assertIn('Shipyard::Fast3D::TextureBindings<SHADER_MAX_TEXTURES> mXboxTextureBindings;',
            projection.header((ROOT/'upstream/BattleShip/libultraship/include/fast/interpreter.h').read_text(encoding='utf-8-sig')))

    def test_real_cache_and_batch_order(self):
        source=(ROOT/'upstream/BattleShip/libultraship/src/fast/interpreter.cpp').read_text(encoding='utf-8-sig')
        path=ROOT/'tools/texture_binding_projection.py'
        module=importlib.import_module('texture_binding_projection') if path.exists() else None
        projected=module.transform(source) if module else source
        driver=Path(__file__).with_name('texture_binding_contract.cpp').read_text()
        classes=[]
        for name,text in [('Original',source),('Projected',projected)]:
            functions=[]
            for signature in ('bool Interpreter::TextureCacheLookup(', 'void Interpreter::TextureCacheClear(',
                              'void Interpreter::TextureCacheDelete(', 'void Interpreter::TextureCacheDeleteRange('):
                functions.append(function(text,signature).replace('Interpreter::',name+'::'))
            if 'void Interpreter::XboxInvalidateTextureBindings()' in text:
                functions.append(function(text,'void Interpreter::XboxInvalidateTextureBindings()').replace('Interpreter::',name+'::'))
            else: functions.append('void '+name+'::XboxInvalidateTextureBindings() {}')
            getter=function(text,'GfxRenderingAPI* Interpreter::GetCurrentRenderingAPI()')
            getter=getter.replace('GfxRenderingAPI* Interpreter::','Backend* '+name+'::')
            functions.append(getter)
            group=function(text,'if (mRdp->textures_changed[i])')
            functions.append('void '+name+'::ImportGroup() {for(int i=0;i<2;++i) {int tile=i;'+group+'}}')
            shader=function(text.split('    struct ShaderProgram* prg = comb->prg[tm];',1)[1], 'if (prg == NULL) {')
            functions.append('void '+name+'::Shader(unsigned tm) {Combiner* comb=&combiner;int* prg=comb->prg[tm];'+shader+'}')
            classes.append(driver.split('// ENGINE_BEGIN',1)[1].split('// ENGINE_END',1)[0].replace('ENGINE',name)+'\n'+'\n'.join(functions))
        driver=driver[:driver.index('// ENGINE_BEGIN')]+ '\n'.join(classes)+driver.split('// ENGINE_END',1)[1]
        hashfn=function(source,'static uint64_t PortTextureContentHash(')
        hashfn=hashfn.replace('    uint64_t h =','    ++hashCalls;\n    uint64_t h =')
        driver=driver.replace('// REAL_HASH',hashfn)
        out=ROOT/'scratch/fast3d-xdk/texture-binding-tests';out.mkdir(parents=True,exist_ok=True)
        (out/'contract.cpp').write_text(driver)
        includes=[ROOT/'upstream/BattleShip/libultraship/include',ROOT/'platform/xbox360/cpp-compat',
                  SHIPYARD_BASE / 'sources/value_types',
                  SHIPYARD_BASE / 'sources',ROOT/'scratch/graphics-xdk/include']
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
