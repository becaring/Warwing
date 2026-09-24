from pathlib import Path
import runpy,subprocess,json,hashlib
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'scratch/libultra-xdk'
UP=ROOT/'upstream/BattleShip/libultraship'
def main():
    compiler,env=runpy.run_path(str(ROOT/'tests/json/run.py'))['host']()
    outputs=[]
    for label in ('original','generated'):
        folder=OUT/('host-'+label);folder.mkdir(parents=True,exist_ok=True)
        base=UP if label=='original' else OUT/'generated'
        registry=base/'src/libultraship/libultra/AudioDmaRegistry.cpp'
        dma=base/'src/libultraship/libultra/os_pi.cpp'
        if label=='original':
            # This test-only include reduction supplies the same actual C ABI
            # headers as production projection. Every original function body
            # remains byte-for-byte unchanged; no class/service test doubles.
            original=dma.read_text();assert original.count('#include "libultraship/libultraship.h"')==1
            dma=folder/'os_pi.cpp'
            dma.write_text(original.replace('#include "libultraship/libultraship.h"','#include "libultraship/libultra.h"\n#include <cstring>'))
        includes=[base/'src/libultraship/libultra',UP/'include',ROOT/'platform/xbox360/cpp-compat',ROOT.parent/'LibUltraShip+Fast3D360/sources',ROOT/'upstream/dependencies/spdlog/include']
        objects=[]
        for index,source in enumerate([registry,dma,ROOT/'tests/libultra-xdk/contract.cpp']):
            obj=folder/('source'+str(index)+'.obj');objects.append(obj)
            cmd=[compiler,'/nologo','/c','/std:c++20','/utf-8','/EHsc','/MD','/DNOMINMAX']+['/I'+str(p) for p in includes]+[source,'/Fo'+str(obj)]
            result=subprocess.run(list(map(str,cmd)),cwd=ROOT,env=env,capture_output=True,text=True)
            (folder/('compile'+str(index)+'.log')).write_text(result.stdout+result.stderr)
            if result.returncode:raise RuntimeError(result.stdout+result.stderr)
        result=subprocess.run(list(map(str,[compiler,'/nologo']+objects+['/Fe'+str(folder/'test.exe')])),cwd=ROOT,env=env,capture_output=True,text=True)
        (folder/'link.log').write_text(result.stdout+result.stderr)
        if result.returncode:raise RuntimeError(result.stdout+result.stderr)
        run=subprocess.run([str(folder/'test.exe')],capture_output=True)
        if run.returncode:raise RuntimeError('Actual DMA/time host contract failed')
        (folder/'output.txt').write_bytes(run.stdout);outputs.append(run.stdout)
    assert outputs[0]==outputs[1]
    (OUT/'host-verification.json').write_text(json.dumps({'same':True,'output_sha256':hashlib.sha256(outputs[0]).hexdigest(),'original_pi_include_reduced':True,'original_function_bodies_unchanged':True},indent=2)+'\n')
    print(outputs[0].decode().strip())
if __name__=='__main__':main()

