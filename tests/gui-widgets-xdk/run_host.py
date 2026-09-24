"""Execute real GuiElement and pure Console methods against original headers.

Console::Run needs actual application Context and is excluded from this host
closure; its complete production TU is separately XDK compiled. No production
dependency is replaced by a mock class or successful service stub.
"""
from pathlib import Path
import subprocess,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from prepare_gui_widgets_xdk import prepare, lower_source, PARSER,walk,field,tx
OUT=ROOT/'scratch/gui-widgets-xdk/host-tests'
UP=ROOT/'upstream/BattleShip/libultraship'

def bodies(text, predicate):
    data=text.encode();result=[]
    for node in walk(PARSER.parse(data).root_node):
        if node.type=='function_definition' and predicate(tx(field(node,'declarator'))):result.append(tx(node))
    return '\n'.join(result)

def run(command,log):
    p=subprocess.run(command,capture_output=True,text=True);log.write_text(p.stdout+p.stderr)
    if p.returncode:raise RuntimeError(p.stdout+p.stderr)
    return p.stdout

def main():
    prepare();OUT.mkdir(parents=True,exist_ok=True)
    vs=subprocess.check_output(['C:/Program Files (x86)/Microsoft Visual Studio/Installer/vswhere.exe','-latest','-products','*','-requires','Microsoft.VisualStudio.Component.VC.Tools.x86.x64','-property','installationPath'],text=True).strip()
    results=[]
    for mode in ['original','adapted']:
        target=OUT/mode;target.mkdir(exist_ok=True)
        console=(UP/'src/ship/debug/Console.cpp').read_text(encoding='utf-8-sig')
        element=(UP/'src/ship/window/gui/GuiElement.cpp').read_text(encoding='utf-8-sig')
        if mode=='adapted':console=lower_source(console,'Console.cpp');element=lower_source(element,'GuiElement.cpp')
        console=bodies(console,lambda d:d.lstrip('&* ').startswith('Console::') and not d.startswith('Console::Run('))
        element=bodies(element,lambda d:d.startswith('GuiElement::'))
        helper=(UP/'src/ship/utils/StringHelper.cpp').read_text(encoding='utf-8-sig')
        helper=bodies(helper,lambda d:d.startswith('StringHelper::Sprintf('))
        fixture=target/'actual_methods.cpp'
        fixture.write_text('#include "prism/compat.h"\n#include "ship/debug/Console.h"\n#include "ship/window/gui/GuiElement.h"\n#include "ship/utils/StringHelper.h"\n#include <spdlog/spdlog.h>\n#include <cstdio>\n#include <cstdarg>\nnamespace Ship {\n'+element+'\n'+console+'\n}\n'+helper+'\n')
        headers=[UP/'include'] if mode=='original' else [ROOT/'scratch/gui-widgets-xdk/generated/include',ROOT/'scratch/config-xdk/generated/include',UP/'include']
        includes=headers+[ROOT/'platform/xbox360/cpp-compat',ROOT.parent/'LibUltraShip+Fast3D360',ROOT.parent/'LibUltraShip+Fast3D360/sources',ROOT/'scratch/imgui-xdk/source',ROOT/'platform/xbox360/imgui',ROOT/'upstream/dependencies/spdlog/include']
        batch=target/'build.cmd';exe=target/'cases.exe'
        batch.write_text('@echo off\ncall "'+vs+'/VC/Auxiliary/Build/vcvars64.bat" >nul\ncl /nologo /std:c++20 /utf-8 /EHsc /MT /W4 /DSPDLOG_ACTIVE_LEVEL=6 /D_CRT_SECURE_NO_WARNINGS '+ ' '.join('/I"'+str(p)+'"' for p in includes)+' "'+str(ROOT/'tests/gui-widgets-xdk/cases.cpp')+'" "'+str(fixture)+'" /Fo"'+str(target)+'/" /Fe"'+str(exe)+'"\nexit /b %errorlevel%\n')
        run(['cmd','/d','/c',str(batch)],target/'compile.log')
        results.append(run([str(exe)],target/'run.log'))
    if results[0]!=results[1]:raise RuntimeError('Original/adapted widget behavior differs')
    print(results[0].strip());print('PASS real original/adapted GuiElement lifecycle and Console method closure')

if __name__=='__main__':main()


