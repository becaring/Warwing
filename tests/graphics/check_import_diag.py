"""Verify the linked production import avoids log payloads when acceptance is false."""
from pathlib import Path
import importlib.util
import argparse
import json

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('rdp',ROOT/'tests/graphics/check_rdp_value_init.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
build=ROOT/'scratch/application-xdk/native/build'
parser=argparse.ArgumentParser();parser.add_argument('--output-dir',type=Path,default=ROOT/'scratch/evidence/import-diagnostic');args=parser.parse_args()
out=args.output_dir;out.mkdir(parents=True,exist_ok=True)
symbols=m.symbols_from_map(build/'Smash360.map')
def resolve(prefix):
    names=[name for name in symbols if name.startswith(prefix)]
    assert len(names)==1,(prefix,names)
    return names[0]
predicate=resolve('?Ssb64RenderDiagShouldLogImport@')
logger=resolve('?Ssb64RenderDiagLogImport@')
importer=resolve('?ImportTexture@Interpreter@')
asm,ops=m.dump_function(build/'Smash360.exe',m.DEFAULT_DUMPBIN,symbols,importer)
(out/'after-ImportTexture.asm').write_text(asm)
def target(args):
    value=args.split(',')[-1].strip()
    try:return int(value,16)
    except ValueError:return symbols.get(value,-1)
calls=[i for i,(_,op,args) in enumerate(ops) if op=='bl' and target(args)==symbols[predicate]]
logs=[i for i,(_,op,args) in enumerate(ops) if op=='bl' and target(args)==symbols[logger]]
assert len(calls)==len(logs)==3
results=[]
for call,log in zip(calls,logs):
    assert log>call
    # Fail closed if XDK changes the boolean-result/conditional branch layout.
    assert [op for _,op,_ in ops[call+1:call+4]]==['clrlwi','cmplwi','beq']
    branch=call+3
    assert target(ops[branch][2])>ops[log][0], 'false predicate must bypass the log call'
    payload=ops[branch+1:log]
    assert sum(op=='fctidz' for _,op,_ in payload)==4
    results.append({'guard':hex(ops[branch][0]),'skippedPayloadInstructions':len(payload),
                    'skippedFloatConversions':4})
asm,guard=m.dump_function(build/'Smash360.exe',m.DEFAULT_DUMPBIN,symbols,predicate)
(out/'after-Ssb64RenderDiagShouldLogImport.asm').write_text(asm)
reservation=next(i for i,(_,op,_) in enumerate(guard) if op=='lwarx')
skip=next(i for i,(_,op,_) in enumerate(guard[:reservation]) if op=='ble')
assert target(guard[skip][2])>guard[reservation][0]
assert [op for _,op,_ in guard[skip-2:skip]]==['lwz','cmpwi']
assert not any(op in ('lwarx','stwcx.','sync','lwsync','mfmsr','mtmsree') for _,op,_ in guard[:skip])
receipt={'importStages':results,'zeroCaptureSkipsReservation':True}
(out/'linked-verification.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
