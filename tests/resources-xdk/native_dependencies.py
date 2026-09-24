"""Real XDK compression objects and explicit libzip desktop-backend API probe."""
from pathlib import Path
import json,re,runpy,subprocess
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'scratch/resources-xdk/native-dependencies'
XDK=Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    units=runpy.run_path(str(ROOT/'tests/resources-xdk/dependencies.py'))['ZLIB_UNITS']
    records=[]
    flags=[str(XDK/'bin/win32/cl.exe'),'/nologo','/c','/MT','/W3','/D_XBOX','/DNOMINMAX','/I'+str(XDK/'include/xbox')]
    for unit in units:
        source=ROOT/'upstream/dependencies/zlib'/(unit+'.c')
        command=flags+['/TC','/I'+str(source.parent),str(source),'/Fo'+str(OUT/(unit+'.obj'))]
        result=subprocess.run(command,cwd=ROOT,text=True,capture_output=True)
        (OUT/(unit+'.log')).write_text(result.stdout+result.stderr)
        records.append({'unit':unit,'exit':result.returncode,'command':command})
    # These are operations directly required by libzip's unmodified desktop
    # backends, not replacement implementations. Expected failures are retained.
    probes={'desktop_headers':'#include <windows.h>\n#include <aclapi.h>\n',
            'file_type':'#include <xtl.h>\nDWORD probe(HANDLE h) { return GetFileType(h); }\n',
            'desktop_wide_files':'#include <xtl.h>\nHANDLE probe(const WCHAR* path) { return CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL); }\n',
            'local_free':'#include <xtl.h>\nvoid probe(void* p) { LocalFree(p); }\n'}
    for name,text in probes.items():
        source=OUT/(name+'.cpp');source.write_text(text)
        command=flags+['/TP',str(source),'/Fo'+str(OUT/(name+'.obj'))]
        result=subprocess.run(command,cwd=ROOT,text=True,capture_output=True)
        (OUT/(name+'.log')).write_text(result.stdout+result.stderr)
        records.append({'unit':name,'exit':result.returncode,'command':command})
    (OUT/'results.json').write_text(json.dumps(records,indent=2)+'\n')
    failed=[r['unit'] for r in records[:len(units)] if r['exit']]
    if failed:raise SystemExit('Native zlib blockers: '+', '.join(failed))
    print('PASS actual zlib core XDK objects; libzip desktop API failures inventoried separately')

if __name__=='__main__':main()
