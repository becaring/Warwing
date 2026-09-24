from pathlib import Path
import json,subprocess
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'scratch/context-xdk/tests'
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    vs=subprocess.check_output(['C:/Program Files (x86)/Microsoft Visual Studio/Installer/vswhere.exe','-latest','-products','*','-requires','Microsoft.VisualStudio.Component.VC.Tools.x86.x64','-property','installationPath'],text=True).strip()
    results=[]
    for label in ('original','projected'):
        target=OUT/label;target.mkdir(exist_ok=True)
        tree=ROOT/('upstream/BattleShip' if label=='original' else 'scratch/context-xdk/compile-tree')
        inc=[tree/'libultraship/include',tree/'libultraship/src',ROOT/'platform/xbox360/cpp-compat',ROOT.parent/'LibUltraShip+Fast3D360',ROOT.parent/'LibUltraShip+Fast3D360/sources']
        inc+= [ROOT/'upstream/dependencies/spdlog/include'] if label=='original' else [ROOT/'scratch/logging-xdk/core-include',ROOT/'scratch/logging-xdk/include',ROOT/'upstream/dependencies/fmt-xdk']
        files=[ROOT/'tests/context-xdk/contract.cpp',tree/'libultraship/src/ship/events/EventSystem.cpp',tree/'libultraship/src/libultraship/log/luslog.cpp',ROOT.parent/'LibUltraShip+Fast3D360/sources/async/native.cpp',ROOT.parent/'LibUltraShip+Fast3D360/sources/clock/chrono.cpp']
        batch=target/'build.cmd';exe=target/'contract.exe'
        batch.write_text('@echo off\ncall "'+vs+'/VC/Auxiliary/Build/vcvars64.bat" >nul\ncl /nologo /EHsc /std:c++20 /utf-8 /MT /DSPDLOG_EOL=\\\"\\n\\\" '+ ' '.join('/I"'+str(p)+'"' for p in inc)+' '+ ' '.join('"'+str(p)+'"' for p in files)+' /Fo"'+str(target)+'/" /Fe"'+str(exe)+'"\nexit /b %errorlevel%\n')
        p=subprocess.run(['cmd','/d','/c',str(batch)],capture_output=True,text=True);(target/'compile.log').write_text(p.stdout+p.stderr)
        if p.returncode:raise RuntimeError(p.stdout+p.stderr)
        p=subprocess.run([str(exe)],capture_output=True,text=True);assert p.returncode==0,p.stderr;results.append(p.stdout)
    assert results[0]==results[1];print(results[0]);print('PASS actual original/projected host differential; no Xbox execution')
if __name__=='__main__':main()
