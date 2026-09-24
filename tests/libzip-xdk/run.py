"""Differential runtime tests: upstream libzip versus the native source projection."""
from pathlib import Path
import hashlib,json,runpy,struct,subprocess,zipfile
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'scratch/libzip-xdk'
def execute(command,log,env):
    result=subprocess.run(list(map(str,command)),cwd=ROOT,env=env,text=True,capture_output=True,timeout=120)
    log.write_text(result.stdout+result.stderr)
    if result.returncode:raise RuntimeError(result.stdout+result.stderr)
    return result.stdout
def fixture(root):
    root.mkdir(parents=True,exist_ok=True)
    payload=bytes((i*37+i//173)%256 for i in range(700000))
    with zipfile.ZipFile(root/'input.zip','w') as z:
        z.writestr('stored.bin',payload,compress_type=zipfile.ZIP_STORED)
        z.writestr('deflated.bin',payload,compress_type=zipfile.ZIP_DEFLATED)
        z.writestr('empty',b'')
        z.writestr('folder/',b'')
        z.writestr('folder/caf\u00e9.txt',b'entry names keep UTF-8')
        with z.open('zip64-local','w',force_zip64=True) as entry:entry.write(b'ZIP64 local header')
    with zipfile.ZipFile(root/'corrupt.zip','w') as z:z.writestr('data',b'bad CRC payload')
    raw=bytearray((root/'corrupt.zip').read_bytes());offset=raw.index(b'PK\x01\x02')+16
    struct.pack_into('<I',raw,offset,struct.unpack_from('<I',raw,offset)[0]^0xffffffff)
    (root/'corrupt.zip').write_bytes(raw)
    (root/'truncated.zip').write_bytes(raw[:15])
    with zipfile.ZipFile(root/'unsupported.zip','w',compression=zipfile.ZIP_BZIP2) as z:z.writestr('data',b'unsupported method')
    with zipfile.ZipFile(root/'blocked.zip','w') as z:z.writestr('data',b'original')
    return payload
def main():
    compiler,env=runpy.run_path(str(ROOT/'tests/json/run.py'))['host']()
    deps=ROOT/'scratch/resources-xdk/host-dependencies'
    results=[]
    for mode in ('original','adapted'):
        folder=OUT/('test-'+mode);folder.mkdir(parents=True,exist_ok=True);expected=fixture(folder/'data')
        includes=[OUT/'generated',ROOT/'platform/xbox360/cpp-compat',ROOT.parent/'LibUltraShip+Fast3D360',ROOT.parent/'LibUltraShip+Fast3D360/sources'] if mode=='adapted' else [ROOT/'upstream/dependencies/libzip/lib',deps/'libzip-ninja']
        sources=[ROOT/'tests/libzip-xdk/contract.cpp']
        if mode=='adapted':sources += [ROOT.parent/'LibUltraShip+Fast3D360/sources/filesystem/filesystem.cpp',
                                      ROOT.parent/'LibUltraShip+Fast3D360/sources/async/native.cpp']
        objects=[]
        for source in sources:
            obj=folder/(source.stem+'.obj');objects.append(obj)
            command=[compiler,'/nologo','/c','/TP','/std:c++17','/EHsc','/MT','/W4','/WX','/DNOMINMAX','/D_CRT_SECURE_NO_WARNINGS']+['/I'+str(i) for i in includes]
            if mode=='adapted':command+=['/DADAPTED_LIBZIP','/DSHIPYARD_TEST_LOGICAL_CWD']
            execute(command+[source,'/Fo'+str(obj)],folder/(source.stem+'.log'),env)
        library=OUT/'host/zip.lib' if mode=='adapted' else deps/'libzip-ninja/lib/zip.lib'
        exe=folder/'test.exe'
        compression=OUT/'host/zlib.lib' if mode=='adapted' else deps/'zlib/zlib.lib'
        execute([compiler.parent/'link.exe','/nologo','/OUT:'+str(exe)]+objects+[library,compression,'advapi32.lib'],folder/'link.log',env)
        print(mode,execute([exe,folder/'data',folder/'result.bin'],folder/'run.log',env).strip())
        actual=(folder/'result.bin').read_bytes()
        if actual!=expected:raise RuntimeError('Payload mismatch: '+mode)
        results.append(actual)
    if results[0]!=results[1]:raise RuntimeError('Native boundary changed archive result')
    resources=runpy.run_path(str(ROOT/'tests/resources-xdk/run.py'))
    resource_result=resources['build'](True,OUT/'host/zip.lib')
    expected_resource=(ROOT/'scratch/resources-xdk/integration-original/result.json').read_bytes()
    if resource_result!=expected_resource:raise RuntimeError('Actual resource/ZIP integration diverged')
    result={'passed':True,'payload_sha256':hashlib.sha256(results[0]).hexdigest(),'resource_result_sha256':hashlib.sha256(resource_result).hexdigest(),'scope':'Actual libzip/zlib source runtime and current ResourceManager/Loader/O2r classes; same native file backend projection on Windows; no Xbox execution'}
    (OUT/'runtime-results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS byte-identical original/adapted libzip payload',result['payload_sha256'])
if __name__=='__main__':main()
