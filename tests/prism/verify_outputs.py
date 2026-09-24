from pathlib import Path
import hashlib
import json
import subprocess

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'scratch/prism-xdk'
reference=OUT/'host-reference'
adapted=OUT/'host-adapted'
files=sorted(reference.glob('shader-*.hlsl'))+[reference/'results.txt']
assert len(files)==1405,('Incomplete shader matrix',len(files))
for path in files:
    assert path.read_bytes()==(adapted/path.name).read_bytes(),('Differential mismatch',path.name)
print('Unchanged Prism vs generated Prism: 702 real shader and lowering outputs plus behavior results byte-identical')
compiler=Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK/bin/win32/fxc.exe')
results=[]
# Compile each unique real output; filter NONE/LINEAR often share the same HLSL.
seen=set()
for path in sorted(adapted.glob('*-xenos.hlsl')):
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    if digest in seen:continue
    seen.add(digest)
    for profile,entry in [('vs_3_0','VSMain'),('ps_3_0','PSMain')]:
        result=subprocess.run([str(compiler),'/nologo','/T',profile,'/E',entry,'/Fo',str(path.with_suffix('.'+profile+'.bin')),str(path)],capture_output=True,text=True)
        log=result.stdout+result.stderr
        path.with_suffix('.'+profile+'.log').write_text(log)
        results.append({'source':path.name,'profile':profile,'exit':result.returncode,'log':log})
(OUT/'shader-compile-results.json').write_text(json.dumps(results,indent=2))
failures=[r for r in results if r['exit']]
for failure in failures[:8]:print(failure)
print('Real generated Xenos shader compilation:',len(results)-len(failures),'passed,',len(failures),'failed')
raise SystemExit(bool(failures))
