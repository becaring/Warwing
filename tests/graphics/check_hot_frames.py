"""Inspect linked PPC, ensuring cold scan/draw work leaves cached/rejected paths."""
from pathlib import Path
import importlib.util
import argparse
import json
import re

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('rdp',ROOT/'tests/graphics/check_rdp_value_init.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
build=ROOT/'scratch/application-xdk/native/build'
parser=argparse.ArgumentParser();parser.add_argument('--output-dir',type=Path,default=ROOT/'scratch/evidence/bounds-cull-lighting');args=parser.parse_args()
out=args.output_dir;out.mkdir(parents=True,exist_ok=True)
symbols=m.symbols_from_map(build/'Smash360.map')
names={'bounds':'port_dl_check_addr','cull':'?GfxSpTri1@Interpreter@Fast@@QAAXEEE_N@Z',
       'vertex':'?GfxSpVertex@Interpreter@Fast@@QAAXIIPBTF3DVtx@2@@Z',
       'dl':'?gfx_dl_handler_common@Fast@@YA_NPAPATF3DGfx@1@@Z'}
for name in symbols:
    if 'XboxCheckDLBoundsMiss' in name:names['bounds-miss']=name
    if 'XboxEmitTriangle' in name:names['emit']=name
assert 'bounds-miss' in names and 'emit' in names
results={};decoded={}
for label,name in names.items():
    asm,ops=m.dump_function(build/'Smash360.exe',m.DEFAULT_DUMPBIN,symbols,name)
    (out/(label+'.asm')).write_text(asm)
    frame=re.search(r'stwu\s+r1,-([0-9A-Fa-f]+)h\(r1\)',asm)
    results[label]={'symbol':name,'instructions':len(ops),'stackBytes':int(frame[1],16) if frame else 0,
                    'fctidz':sum(op=='fctidz' for _,op,_ in ops),'fctiwz':sum(op=='fctiwz' for _,op,_ in ops)}
    decoded[label]=ops
hot_ops=[op for _,op,_ in decoded['bounds']]
for forbidden in ('mflr','stwu','std','stw','stfd','bl'):
    assert forbidden not in hot_ops, 'Bounds cache still pays scan frame: '+forbidden
assert 'lwsync' in hot_ops, 'Generation acquire must remain'
assert results['cull']['stackBytes']<784, 'Rejected triangles still allocate original full frame'
assert results['vertex']['fctidz']>=3, 'Bounded RGB accumulation missing'
assert results['vertex']['fctiwz']>=3, 'Original integer fallback missing'
(out/'linked-verification.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results,indent=2))
