from pathlib import Path
import subprocess,shutil
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'scratch/logging-xdk/core-tests';GEN=ROOT/'scratch/logging-xdk/core-include';QUEUE=ROOT/'scratch/logging-xdk/include'
def run(cmd,name):
    p=subprocess.run(cmd,capture_output=True,text=True,timeout=60);(OUT/(name+'.log')).write_text(p.stdout+p.stderr)
    if p.returncode:raise RuntimeError(p.stdout+p.stderr)
    return p.stdout
def main():
    OUT.mkdir(parents=True,exist_ok=True);subprocess.run(['C:/Python313/python.exe',str(ROOT/'tools/prepare_logging_xdk.py')],check=True)
    vs=subprocess.check_output(['C:/Program Files (x86)/Microsoft Visual Studio/Installer/vswhere.exe','-latest','-products','*','-requires','Microsoft.VisualStudio.Component.VC.Tools.x86.x64','-property','installationPath'],text=True).strip()
    source=ROOT/'tests/logging/core_cases.cpp';native=ROOT.parent/'LibUltraShip+Fast3D360/sources/async/native.cpp';chrono=ROOT.parent/'LibUltraShip+Fast3D360/sources/clock/chrono.cpp';results=[]
    for original in (1,0):
        target=OUT/str(original);target.mkdir(exist_ok=True);exe=target/'core.exe';batch=target/'build.cmd'
        for file in target.glob('rotation*.log'):file.unlink()
        includes=[ROOT/'upstream/dependencies/spdlog/include'] if original else [GEN,QUEUE,ROOT/'upstream/dependencies/fmt-xdk']
        batch.write_text(f'@echo off\ncall "{vs}/VC/Auxiliary/Build/vcvars64.bat" >nul\ncl /nologo /EHsc /std:c++20 /utf-8 /MT /D_CRT_SECURE_NO_WARNINGS /DORIGINAL_SPDLOG={original} /DSPDLOG_EOL=\\\"\\n\\\" /I"{ROOT}" /I"{ROOT.parent}/LibUltraShip+Fast3D360" /I"{ROOT.parent}/LibUltraShip+Fast3D360/sources" '+ ' '.join('/I"'+str(p)+'"' for p in includes)+f' "{source}" "{native}" "{chrono}" /Fo"{target}/" /Fe"{exe}"\nexit /b %errorlevel%\n')
        run(['cmd','/d','/c',str(batch)],str(original)+'-compile');results.append(run([str(exe),str(target)],str(original)+'-run'))
    if results[0]!=results[1]:raise RuntimeError('Original/generated logger outputs differ: '+repr(results))
    print(results[0])
    xdk=Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')
    print(run([str(xdk/'bin/win32/cl.exe'),'/nologo','/TP','/EHsc','/D_XBOX','/DORIGINAL_SPDLOG=0','/c','/I'+str(ROOT),'/I'+str(ROOT.parent/'LibUltraShip+Fast3D360'),'/I'+str(ROOT.parent/'LibUltraShip+Fast3D360/sources'),'/I'+str(GEN),'/I'+str(QUEUE),'/I'+str(ROOT/'upstream/dependencies/fmt-xdk'),'/I'+str(xdk/'include/xbox'),'/Fo'+str(OUT/'core-xdk.obj'),str(source)],'xdk-compile'))
    print('PASS exact original/generated current-core host differential and XDK compile. No Xbox execution.')
if __name__=='__main__':main()
