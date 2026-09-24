from pathlib import Path
import runpy,subprocess,json,hashlib
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'scratch/controllers-xdk'
UP=ROOT/'upstream/BattleShip/libultraship'
def main():
    host=runpy.run_path(str(ROOT/'tests/json/run.py'))['host'];compiler,env=host()
    results=[]
    for adapted in (False,True):
        name='defaults-generated' if adapted else 'defaults-original'
        folder=OUT/name;folder.mkdir(parents=True,exist_ok=True)
        include=[ROOT/'scratch/config-xdk/host-includes']
        base=UP
        if adapted:
            base=OUT/'generated'
            include=[base/'include',ROOT/'platform/xbox360/input',ROOT/'platform/xbox360/cpp-compat']+include
        include.append(UP/'include')
        source=[base/'src/ship/controller/controldevice/controller/mapping/ControllerDefaultMappings.cpp',base/'src/libultraship/controller/controldevice/controller/mapping/ControllerDefaultMappings.cpp',ROOT/'tests/controllers-xdk/defaults.cpp']
        common=[compiler,'/nologo','/std:c++20','/EHsc','/MD','/DNOMINMAX','/DSDL_MAIN_HANDLED']+['/I'+str(p) for p in include]
        objects=[]
        for index,unit in enumerate(source):
            obj=folder/('source'+str(index)+'.obj');objects.append(obj)
            command=common+['/c',unit,'/Fo'+str(obj)]
            build=subprocess.run(list(map(str,command)),cwd=ROOT,env=env,capture_output=True,text=True)
            (folder/('compile'+str(index)+'.log')).write_text(build.stdout+build.stderr)
            if build.returncode:raise RuntimeError(build.stdout+build.stderr)
        build=subprocess.run(list(map(str,[compiler,'/nologo']+objects+['/Fe'+str(folder/'test.exe')])),cwd=ROOT,env=env,capture_output=True,text=True)
        (folder/'link.log').write_text(build.stdout+build.stderr)
        if build.returncode:raise RuntimeError(build.stdout+build.stderr)
        run=subprocess.run([str(folder/'test.exe')],capture_output=True)
        if run.returncode:raise RuntimeError('Defaults runtime failure')
        (folder/'output.txt').write_bytes(run.stdout);results.append(run.stdout)
    assert results[0]==results[1], 'Actual default mapping constructor/setter behavior differs'
    (OUT/'defaults-verification.json').write_text(json.dumps({'same':True,'sha256':hashlib.sha256(results[0]).hexdigest(),'cases':'actual Ship/LUS default constructors; six mapping tables; custom keyboard and axis overrides; explicit empty-container constructor fallback'},indent=2)+'\n')
    print('Actual original/generated DefaultMappings constructors and six mapping tables PASS')
if __name__=='__main__':main()
