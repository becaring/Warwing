"""Verify actual generated Config/CVar against same original consumer bodies."""
from pathlib import Path
import json,re,runpy,subprocess,hashlib,shutil
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'scratch/config-xdk'
LUS=ROOT/'upstream/BattleShip/libultraship'
M=runpy.run_path(str(ROOT/'tests/json/run.py'))
def execute(args,folder,env=None):
    folder.mkdir(parents=True,exist_ok=True)
    result=subprocess.run(list(map(str,args)),cwd=folder,env=env,text=True,capture_output=True)
    (folder/'command.json').write_text(json.dumps(list(map(str,args)),indent=2)+'\n')
    (folder/'result.log').write_text(result.stdout+result.stderr)
    if result.returncode:raise RuntimeError(result.stdout+result.stderr)
    return result

def build(consumer,adapted):
    label=('generated-' if adapted else 'original-')+consumer; folder=OUT/label
    folder.mkdir(parents=True,exist_ok=True)
    sdl=OUT/'host-includes/SDL2';sdl.mkdir(parents=True,exist_ok=True)
    for header in (ROOT/'upstream/dependencies/SDL/include').glob('*.h'):shutil.copyfile(header,sdl/header.name)
    cvars=(LUS/'cmake/cvars.cmake').read_text()
    (folder/'cvars.h').write_text('\n'.join('#define '+key+' "'+value+'"' for key,value in re.findall(r'set\((CVAR_\w+) "([^"\n]+)" CACHE STRING ""\)',cvars))+'\n')
    compiler,env=M['host']()
    sdk=Path('C:/Program Files (x86)/Windows Kits/10/Include/10.0.26100.0')
    env['INCLUDE'] += ';'+str(sdk/'winrt')+';'+str(sdk/'cppwinrt')
    base=ROOT.parent/'LibUltraShip+Fast3D360'
    paths=[base/'sources/json/include',base/'sources',ROOT/'platform/xbox360/cpp-compat',ROOT/'scratch/json-xdk/backend-generated']
    if adapted: paths=[OUT/'generated/include',ROOT/'scratch/audio-xdk/generated/include',base]+paths
    paths += [LUS/'include',LUS/'src',ROOT/'upstream/dependencies/spdlog/include',ROOT/'upstream/dependencies/imgui',OUT/'host-includes',ROOT/'upstream/dependencies/tinyxml2',ROOT/'upstream/dependencies/thread-pool/include',ROOT/'upstream/BattleShip/torch/lib/n64graphics']
    source_root=OUT/'generated' if adapted else LUS
    sources=[source_root/'src/ship/config/Config.cpp',source_root/'src/ship/utils/StringHelper.cpp',(ROOT/'tests/config-xdk/legacy_contract.cpp' if consumer=='legacy' else ROOT/'tests/json-consumers'/(consumer+'_contract.cpp')),ROOT.parent/'LibUltraShip+Fast3D360/sources/json/json.cpp']
    sources += [ROOT/'tests/json-consumers/unused_services.cpp'] if consumer=='config' else [source_root/'src/ship/config/ConsoleVariable.cpp',ROOT/'tests/json-consumers/context_fixture.cpp']
    if adapted:sources += [ROOT.parent/'LibUltraShip+Fast3D360/sources/filesystem/filesystem.cpp',
                          ROOT.parent/'LibUltraShip+Fast3D360/sources/async/native.cpp']
    args=[compiler,'/nologo','/std:c++20','/utf-8','/EHsc','/MD','/Gy','/O1','/W3','/DNOMINMAX','/DDISABLE_SCRIPTING','/DSDL_MAIN_HANDLED','/D_CRT_SECURE_NO_WARNINGS','/FI'+str(folder/'cvars.h')]+['/I'+str(p) for p in paths]+sources+['/Fo'+str(folder)+'\\','/Fe'+str(folder/'test.exe'),'/link','/OPT:REF']
    execute(args,folder,env)
    execute([folder/'test.exe',folder/'settings.json'],folder/'run')
    return (folder/'settings.json').read_bytes()
def helper():
    module=runpy.run_path(str(ROOT/'platform/xbox360/cpp-compat/config/lowering.py'))
    source=ROOT/'tests/config-xdk/helper_contract.cpp'
    generated=OUT/'helper_generated.cpp'
    generated.write_bytes(module['lower_ranges'](source.read_bytes()))
    compiler,env=M['host']()
    outputs=[]
    for name,fixture in [('helper-original',source),('helper-generated',generated)]:
        folder=OUT/name
        execute([compiler,'/nologo','/std:c++20','/EHsc','/MD','/DNOMINMAX','/I'+str(ROOT/'platform/xbox360/cpp-compat'),'/I'+str(ROOT.parent/'LibUltraShip+Fast3D360'),'/I'+str(ROOT.parent/'LibUltraShip+Fast3D360/sources'),fixture,'/Fo'+str(folder/'test.obj'),'/Fe'+str(folder/'test.exe')],folder,env)
        outputs.append(execute([folder/'test.exe'],folder/'run').stdout)
    assert outputs[0]==outputs[1]
    print('helper original/generated lifetime/hash contract PASS')

def main():
    helper()
    results={}
    for consumer in ('config','cvar','legacy'):
        a=build(consumer,False);b=build(consumer,True)
        assert a==b,consumer+' persisted bytes changed'
        results[consumer]=hashlib.sha256(b).hexdigest()
        print(consumer+': actual original/generated methods and persisted bytes PASS')
    (OUT/'host-verification.json').write_text(json.dumps(results,indent=2)+'\n')
if __name__=='__main__':main()
