from pathlib import Path
import subprocess,sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tools'))
from prepare_postprocess_xdk import prepare
UP=ROOT/'upstream/BattleShip/libultraship';OUT=ROOT/'scratch/postprocess-xdk/host-tests'
def run(command,log):
    p=subprocess.run(command,capture_output=True,text=True);log.write_text(p.stdout+p.stderr)
    if p.returncode:raise RuntimeError(p.stdout+p.stderr)
    return p.stdout
def main():
    prepare();OUT.mkdir(parents=True,exist_ok=True)
    vs=subprocess.check_output(['C:/Program Files (x86)/Microsoft Visual Studio/Installer/vswhere.exe','-latest','-products','*','-requires','Microsoft.VisualStudio.Component.VC.Tools.x86.x64','-property','installationPath'],text=True).strip()
    names=['PostProcessPreset','PostProcessGlslNormalizer','PostProcessSlangSource','PostProcessSlangTranspiler','PostProcessTranspiler','PostProcessChain'];results=[]
    assets=sorted((UP/'src/fast/shaders/postprocess').glob('**/*.glsl'))
    for mode in ['original','adapted']:
        target=OUT/mode;target.mkdir(exist_ok=True)
        base=UP if mode=='original' else ROOT/'scratch/postprocess-xdk/generated'
        headers=[UP/'include'] if mode=='original' else [ROOT/'scratch/fast3d-xdk/compile-tree/libultraship/include']
        sources=[base/'src/fast/postprocess'/(name+'.cpp') for name in names]+[base/'src/fast/debug/GfxDebugger.cpp',ROOT/'tests/postprocess-xdk/cases.cpp']
        loader=(base/'src/fast/postprocess/PostProcessSourceLoader.cpp').read_text()
        marker='namespace {\n\n// Runtime diagnostics state.'
        if loader.count(marker)!=1:raise ValueError('Changed source-loader diagnostic closure')
        diagnostics=target/'runtime_diagnostics.cpp'
        diagnostics.write_text('#include "fast/postprocess/PostProcessSourceLoader.h"\n#include <mutex>\n#include "async/native.h"\nnamespace Fast {\n'+loader[loader.index(marker):])
        sources.extend([diagnostics,ROOT.parent/'LibUltraShip+Fast3D360/sources/async/native.cpp'])
        includes=headers+[ROOT/'platform/xbox360/cpp-compat',ROOT.parent/'LibUltraShip+Fast3D360',ROOT.parent/'LibUltraShip+Fast3D360/sources',ROOT/'scratch/imgui-xdk/source',ROOT/'platform/xbox360/imgui',ROOT/'upstream/dependencies/spdlog/include']
        batch=target/'build.cmd';exe=target/'cases.exe'
        batch.write_text('@echo off\ncall "'+vs+'/VC/Auxiliary/Build/vcvars64.bat" >nul\ncl /nologo /std:c++20 /utf-8 /EHsc /Gy /MT /DSPDLOG_ACTIVE_LEVEL=6 /D_CRT_SECURE_NO_WARNINGS '+ ' '.join('/I"'+str(p)+'"' for p in includes)+' '+ ' '.join('"'+str(p)+'"' for p in sources)+' /Fo"'+str(target)+'/" /Fe"'+str(exe)+'" /link /OPT:REF\nexit /b %errorlevel%\n')
        run(['cmd','/d','/c',str(batch)],target/'compile.log');results.append(run([str(exe),*map(str,assets)],target/'run.log'))
    if results[0]!=results[1]:raise RuntimeError('Original/projected postprocess outputs differ')
    print('PASS original/projected parser, normalizer, disabled transpiler, inactive chain and debugger outputs: '+str(len(results[0]))+' bytes; '+str(len(assets))+' actual bundled GLSL files')
if __name__=='__main__':main()

