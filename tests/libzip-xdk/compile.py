"""Build the same generated native libzip C sources on Windows and XDK."""
from pathlib import Path
import json,runpy,subprocess,sys
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'scratch/libzip-xdk'
PLATFORM_BASE=runpy.run_path(str(ROOT/'tools/platform_base.py'))['resolve'](ROOT)
XDK=Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')
def main():
    manifest=runpy.run_path(str(ROOT/'tools/prepare_libzip_xdk.py'))['prepare']()
    host,env=runpy.run_path(str(ROOT/'tests/json/run.py'))['host']()
    records=[]
    for mode,compiler,environment in [('host',host,env),('xdk',XDK/'bin/win32/cl.exe',None)]:
        folder=OUT/mode;folder.mkdir(parents=True,exist_ok=True);objects=[]
        flags=['/nologo','/c','/MT','/W3','/DNOMINMAX','/D_CRT_SECURE_NO_WARNINGS','/I'+str(OUT/'generated'),'/I'+str(ROOT/'platform/xbox360/cpp-compat'),'/I'+str(PLATFORM_BASE),'/I'+str(PLATFORM_BASE/'sources'),'/I'+str(ROOT/'upstream/dependencies/zlib')]
        if mode=='xdk':flags+=['/D_XBOX','/I'+str(XDK/'include/xbox')]
        sources=[OUT/'generated'/unit for unit in manifest['units']]+[PLATFORM_BASE/'sources/libzip/native_boundary.cpp']
        for source in sources:
            obj=folder/(source.stem+'.obj');objects.append(obj)
            command=[str(compiler)]+flags+(['/TP','/EHsc'] if source.suffix=='.cpp' else ['/TC'])+[str(source),'/Fo'+str(obj)]
            result=subprocess.run(command,cwd=ROOT,env=environment,text=True,capture_output=True)
            (folder/(source.stem+'.log')).write_text(result.stdout+result.stderr)
            records.append({'mode':mode,'unit':source.name,'exit':result.returncode,'command':command})
        if not any(r['exit'] for r in records if r['mode']==mode):
            command=[str(compiler.parent/'lib.exe'),'/nologo','/OUT:'+str(folder/'zip.lib')]+list(map(str,objects))
            result=subprocess.run(command,cwd=ROOT,env=environment,text=True,capture_output=True)
            (folder/'archive.log').write_text(result.stdout+result.stderr)
            records.append({'mode':mode,'unit':'archive','exit':result.returncode,'command':command})
        zobjects=[]
        for unit in runpy.run_path(str(ROOT/'tests/resources-xdk/dependencies.py'))['ZLIB_UNITS']:
            obj=folder/('zlib-'+unit+'.obj');zobjects.append(obj)
            command=[str(compiler)]+flags+['/TC',str(ROOT/'upstream/dependencies/zlib'/(unit+'.c')),'/Fo'+str(obj)]
            result=subprocess.run(command,cwd=ROOT,env=environment,text=True,capture_output=True)
            (folder/('zlib-'+unit+'.log')).write_text(result.stdout+result.stderr)
            records.append({'mode':mode,'unit':'zlib-'+unit,'exit':result.returncode,'command':command})
        if not any(r['exit'] for r in records if r['mode']==mode and r['unit'].startswith('zlib-')):
            command=[str(compiler.parent/'lib.exe'),'/nologo','/OUT:'+str(folder/'zlib.lib')]+list(map(str,zobjects))
            result=subprocess.run(command,cwd=ROOT,env=environment,text=True,capture_output=True)
            (folder/'zlib-archive.log').write_text(result.stdout+result.stderr)
            records.append({'mode':mode,'unit':'zlib-archive','exit':result.returncode,'command':command})
    (OUT/'compile-results.json').write_text(json.dumps(records,indent=2)+'\n')
    failures=[r['mode']+':'+r['unit'] for r in records if r['exit']]
    print('Failures: '+', '.join(failures) if failures else 'PASS host/XDK actual libzip C library')
    return bool(failures)
if __name__=='__main__':sys.exit(main())
