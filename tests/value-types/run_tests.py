from pathlib import Path
import argparse,subprocess,sys,re
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'scratch/value-types/tests';INCLUDE=ROOT.parent/'LibUltraShip+Fast3D360/sources/value_types';PRISM=ROOT/'upstream/dependencies/prism/src/prism'
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    shapes=OUT/'prism_shapes';shapes.mkdir(exist_ok=True)
    for name in ('ast.h','processor.h'):
        text=(PRISM/name).read_text()
        for token in ('variant','optional','holds_alternative','get'):
            text=text.replace('std::'+token+'<','V::'+token+'<')
        (shapes/name).write_text(text)
    widgets=(ROOT/'upstream/BattleShip/port/gui/UIWidgets.hpp').read_text()
    widgets=widgets[widgets.index('typedef enum ColorPickerModifiers'):widgets.index('struct RadioButtonsOptions')]
    menu=(ROOT/'upstream/BattleShip/port/gui/MenuTypes.h').read_text()
    aliases=menu[menu.index('using CVarVariant ='):menu.index('// All the info needed')].replace('std::variant<','V::variant<')
    gui='#include <map>\n#include <unordered_map>\n#include <imgui.h>\n#include <ship/utils/color.h>\ntypedef int32_t s32;\nnamespace UIWidgets {\n'+widgets+'\n}\n'+aliases
    (shapes/'gui.h').write_text(gui)
    file_header=(ROOT/'upstream/BattleShip/libultraship/include/ship/resource/File.h').read_text()
    manager=(ROOT/'upstream/BattleShip/libultraship/include/ship/resource/ResourceManager.h').read_text()
    reader=re.search(r'std::variant<[^;]+> Reader;',file_header)[0].replace('std::variant','V::variant')
    error=re.search(r'typedef enum class ResourceLoadError[^;]+;',manager)[0]
    lus='namespace tinyxml2 { class XMLDocument; }\nnamespace Ship { class BinaryReader; class IResource; }\nnamespace lus_shapes { using Ship::BinaryReader;\n'+error+'\ntypedef '+reader+'\ntypedef V::variant<ResourceLoadError,std::shared_ptr<Ship::IResource> > Cache;\n}\n'
    (shapes/'lus.h').write_text(lus)

    vswhere=Path('C:/Program Files (x86)/Microsoft Visual Studio/Installer/vswhere.exe')
    vs=subprocess.check_output([str(vswhere),'-latest','-products','*','-requires','Microsoft.VisualStudio.Component.VC.Tools.x86.x64','-property','installationPath'],text=True).strip()
    source=ROOT/'tests/value-types/value_cases.cpp';results=[]
    for standard in (1,0):
        exe=OUT/f'values-{standard}.exe';batch=OUT/f'build-{standard}.cmd'
        batch.write_text(f'@echo off\ncall "{vs}/VC/Auxiliary/Build/vcvars64.bat" >nul\nif errorlevel 1 exit /b 1\ncl /nologo /EHsc /std:c++17 /MT /DUSE_STD={standard} /I"{INCLUDE}" /I"{OUT}" /I"{PRISM}" /I"{ROOT}/upstream/dependencies/imgui" /I"{ROOT}/upstream/BattleShip/libultraship/include" "{source}" /Fo"{OUT}/values-{standard}.obj" /Fe"{exe}"\nexit /b %errorlevel%\n')
        run=subprocess.run(['cmd','/d','/c',str(batch)],capture_output=True,text=True);(OUT/f'compile-{standard}.log').write_text(run.stdout+run.stderr)
        if run.returncode: print(run.stdout+run.stderr);return 1
        run=subprocess.run([str(exe)],capture_output=True,text=True);(OUT/f'run-{standard}.log').write_text(run.stdout+run.stderr)
        if run.returncode: print(run.stdout+run.stderr);return 1
        results.append(run.stdout)
    if results[0]!=results[1]:print('Differential output mismatch:',results);return 1
    print(results[0]);print('PASS identical std / xbox_compat host outcomes with actual Prism shapes.')
    xdk=Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')
    command=[str(xdk/'bin/win32/cl.exe'),'/nologo','/TP','/EHsc','/D_XBOX','/DUSE_STD=0','/c','/I'+str(INCLUDE),'/I'+str(xdk/'include/xbox'),'/Fo'+str(OUT/'values-xdk.obj'),str(source)]
    run=subprocess.run(command,capture_output=True,text=True);(OUT/'compile-xdk.log').write_text(run.stdout+run.stderr)
    if run.returncode: print(run.stdout+run.stderr);return 1
    print('PASS XDK object compilation of19-alternative/copy/move/failure/optional instantiations. No Xbox execution.')
    return 0
if __name__=='__main__':raise SystemExit(main())
