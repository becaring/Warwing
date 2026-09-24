from pathlib import Path
import subprocess,json,hashlib,re,sys
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'scratch/input-xdk/tests';BASE=ROOT/'platform/xbox360/input';OVER=ROOT/'scratch/input-xdk/source/libultraship'
sys.path.insert(0,str(ROOT/'tools'))
from platform_base import resolve as resolve_platform_base
def run(cmd,log):
    p=subprocess.run(cmd,capture_output=True,text=True);(OUT/log).write_text(p.stdout+p.stderr)
    if p.returncode:raise RuntimeError(p.stdout+p.stderr)
    print(p.stdout)
def main():
    shared=resolve_platform_base(ROOT)/'sources'
    OUT.mkdir(parents=True,exist_ok=True)
    subprocess.run(['C:/Python313/python.exe',str(ROOT/'tools/prepare_input_xdk.py')],check=True)
    (OUT/'spdlog').mkdir(exist_ok=True)
    (OUT/'spdlog/spdlog.h').write_text('#pragma once\n#define SPDLOG_ERROR(...) ((void)0)\n#define SPDLOG_WARN(...) ((void)0)\n#define SPDLOG_INFO(...) ((void)0)\n#define SPDLOG_TRACE(...) ((void)0)\n')
    # Execute exact pinned methods with test-only Context/physical seams. These
    # are behavioral fixtures, not an alternate application implementation.
    up=ROOT/'upstream/BattleShip/libultraship'
    def body(path,signature,source_root=up):
        p=source_root/path;t=p.read_text();start=t.index(signature);brace=t.index('{',start);depth=1;end=brace+1
        while depth:
            depth+=(t[end]=='{')-(t[end]=='}');end+=1
        return '#line '+str(t[:brace].count('\n')+1)+' "'+p.as_posix()+'"\n'+t[brace:end]+'\n'
    fixtures=''
    fixtures+='void UpdateMappedButton(uint16_t& padButtons,uint8_t mPortIndex,uint16_t mBitmask,SDL_GameControllerButton mControllerButton)\n'+body('src/ship/controller/controldevice/controller/mapping/sdl/SDLButtonToButtonMapping.cpp','void SDLButtonToButtonMapping::UpdatePad')
    fixtures+='float MappedAxis(uint8_t mPortIndex,SDL_GameControllerAxis mControllerAxis,int mAxisDirection)\n'+body('src/ship/controller/controldevice/controller/mapping/sdl/SDLAxisDirectionToAxisDirectionMapping.cpp','float SDLAxisDirectionToAxisDirectionMapping::GetNormalizedAxisDirectionValue')
    fixtures+='void osContGetReadData(OSContPad* pad)\n'+body('src/libultraship/libultra/os.cpp','void osContGetReadData')
    fixtures+='void RefreshGuiDevices()\n'+body('src/ship/controller/physicaldevice/SDLAddRemoveDeviceEventHandler.cpp','void SDLAddRemoveDeviceEventHandler::UpdateElement',OVER)
    (OUT/'mapping_methods.h').write_text(fixtures)
    os=(up/'src/libultraship/libultra/os.cpp').read_text();pad=re.search(r'    struct GameContPad \{.*?\n    \};',os,re.S)[0]
    abi=OUT/'pad_abi.cpp';abi.write_text('#include <stdint.h>\n#include <stddef.h>\n'+pad+'\nstatic_assert(sizeof(GameContPad)==6,"game pad stride");\nstatic_assert(offsetof(GameContPad,err_no)==4,"error offset");\n')
    vs=subprocess.check_output(['C:/Program Files (x86)/Microsoft Visual Studio/Installer/vswhere.exe','-latest','-products','*','-requires','Microsoft.VisualStudio.Component.VC.Tools.x86.x64','-property','installationPath'],text=True).strip()
    batch=OUT/'host.cmd';exe=OUT/'input.exe'
    sources=[ROOT/'tests/input/physical_cases.cpp',shared/'input/physical.cpp',OVER/'src/ship/controller/physicaldevice/ConnectedPhysicalDeviceManager.cpp']
    batch.write_text(f'@echo off\ncall "{vs}/VC/Auxiliary/Build/vcvars64.bat" >nul\ncl /nologo /EHsc /std:c++20 /MT /I"{BASE}" /I"{shared}" /I"{OVER}/include" /I"{up}/include" /I"{OUT}" '+ ' '.join(f'"{p}"' for p in sources)+f' /Fo"{OUT}/" /Fe"{exe}"\nexit /b %errorlevel%\n')
    run(['cmd','/d','/c',str(batch)],'host-compile.log');run([str(exe)],'host-run.log')
    xdk=Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')
    for name in ('physical','xinput','window_input'):
        source=(BASE if name=='window_input' else shared/'input')/(name+'.cpp')
        run([str(xdk/'bin/win32/cl.exe'),'/nologo','/TP','/EHsc','/D_XBOX','/D_XBOX_VER=200','/c','/I'+str(xdk/'include/xbox'),'/I'+str(BASE),'/I'+str(shared),'/Fo'+str(OUT/(name+'.obj')),str(source)],name+'-xdk.log')
    run([str(xdk/'bin/win32/cl.exe'),'/nologo','/TP','/c','/I'+str(xdk/'include/xbox'),'/Fo'+str(OUT/'pad_abi.obj'),str(abi)],'pad-abi-xdk.log')
    print('PASS XDK native bridge object compilation; no target execution claimed.')
if __name__=='__main__':main()

