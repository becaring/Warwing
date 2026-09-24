"""Record full authoritative startup TU dependency failures without stand-ins."""
from pathlib import Path
import json, subprocess
ROOT=Path(__file__).resolve().parents[4]
OUT=ROOT/'scratch/startup-xdk'
SDK=Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')
def main():
    include=[OUT/'generated/port',ROOT/'scratch/config-xdk/generated/include',ROOT/'scratch/resources-xdk/generated/include',ROOT/'scratch/fast3d-xdk/overlay/libultraship/include',ROOT/'scratch/graphics-xdk/include',ROOT/'scratch/binary-reader-xdk/generated/include',ROOT/'scratch/audio-xdk/generated/include',ROOT/'scratch/logging-xdk/core-include',ROOT/'scratch/logging-xdk/include',ROOT/'scratch/imgui-xdk/source',ROOT/'platform/xbox360/imgui',ROOT.parent/'LibUltraShip+Fast3D360/sources',ROOT.parent/'LibUltraShip+Fast3D360/sources/value_types',ROOT.parent/'LibUltraShip+Fast3D360/sources/json/include',ROOT/'platform/xbox360/cpp-compat',ROOT/'platform/xbox360',ROOT/'upstream/dependencies/fmt-xdk',ROOT/'upstream/BattleShip/libultraship/include',ROOT/'upstream/BattleShip/libultraship/src',ROOT/'upstream/BattleShip/port',ROOT/'upstream/BattleShip/include',ROOT/'scratch/thread-pool-xdk',ROOT/'platform/xbox360/cpp-compat/thread-pool',ROOT/'platform/xbox360/cpp-compat/async',SDK/'include/xbox']
    report={}
    include += [ROOT/'upstream/dependencies/libzip/lib',ROOT/'scratch/resources-xdk/libzip-public',ROOT/'upstream/BattleShip/libultraship/extern/StormLib/src']
    for relative in ['port/port.cpp','libultraship/src/ship/Context.cpp']:
        source=OUT/'generated'/relative
        folder=OUT/'closure'/source.stem;folder.mkdir(parents=True,exist_ok=True)
        command=[SDK/'bin/win32/cl.exe','/nologo','/c','/TP','/EHsc','/MT','/W3','/D_XBOX','/DNOMINMAX','/DDISABLE_SCRIPTING','/DSSB64_O2R_NAME="BattleShip.o2r"']+['/I'+str(p) for p in include]+['/Fo'+str(folder/'test.obj'),source]
        result=subprocess.run(list(map(str,command)),cwd=ROOT,capture_output=True,text=True)
        log=result.stdout+result.stderr
        (folder/'result.log').write_text(log)
        errors=[line for line in log.splitlines() if 'error ' in line]
        report[relative]={'exit':result.returncode,'command':list(map(str,command)),'errors':errors}
        print(relative+': '+str(result.returncode)+'\n'+'\n'.join(errors[:6]))
    (OUT/'closure-verification.json').write_text(json.dumps(report,indent=2)+'\n')
    return all(item['exit']==0 for item in report.values())
if __name__=='__main__':
    raise SystemExit(0 if main() else 1)
