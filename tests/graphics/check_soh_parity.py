"""Verify the linked production executable contains the transferred Xbox paths.

This is native code-generation evidence, not a timing or hardware rendering test.
"""
from pathlib import Path
import importlib.util
import json
import re

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('rdp_check',ROOT/'tests/graphics/check_rdp_value_init.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
build=ROOT/'scratch/application-xdk/native/build'
out=ROOT/'scratch/evidence/soh-parity/linked';out.mkdir(parents=True,exist_ok=True)
symbols=m.symbols_from_map(build/'Smash360.map')

def dump(label,prefix):
    matches=[name for name in symbols if name.startswith(prefix)]
    assert len(matches)==1,(prefix,matches)
    name=matches[0]
    assembly,ops=m.dump_function(build/'Smash360.exe',m.DEFAULT_DUMPBIN,symbols,name)
    (out/(label+'.asm')).write_text(assembly)
    return name,assembly,ops

def calls(ops,name):
    address=symbols[name]
    for _,op,args in ops:
        if op not in ('bl','b'):continue
        value=args.strip()
        if value==name:return True
        try:
            if int(value,16)==address:return True
        except ValueError:pass
    return False

paths={}
for label,prefix in [('vertex','?GfxSpVertex@Interpreter@'),('matrix','?GfxSpMatrix@Interpreter@'),
                     ('transform','?TransformPositions@Fast3D@Shipyard@@'),('quantize','?QuantizeMatrix@Fast3D@Shipyard@@'),
                     ('clip','?ClipVertices@Fast3D@Shipyard@@'),('finite-clip','?ClipFiniteVertices@Fast3D@Shipyard@@'),
                     ('combiner-miss','?XboxLookupColorCombinerCold@Interpreter@'),
                     ('constant-build','?XboxBuildTriangleConstants@'),('emit','?XboxEmitTriangle@Interpreter@')]:
    paths[label]=dump(label,prefix)
for label in ('transform','clip','finite-clip'):
    assert calls(paths['vertex'][2],paths[label][0]),'Real vertex does not call '+label
assert calls(paths['matrix'][2],paths['quantize'][0]),'Real replacement matrix does not call VMX quantization'
vertex_ops=[op for _,op,_ in paths['vertex'][2]]
assert vertex_ops.count('stfiwx')>=3,'Deferred FPR RGB stores missing from real vertex routine'
assert 'fsel' in vertex_ops,'Finite donor fog/byte selects missing'
for label in ('transform','quantize','clip','finite-clip'):
    opcodes=[op for _,op,_ in paths[label][2]]
    assert not any(op.startswith(('vmadd','vnmsub')) for op in opcodes),'Unexpected fused VMX '+label
for label in ('clip','finite-clip'):
    opcodes=[op for _,op,_ in paths[label][2]]
    assert 'stvebx' in opcodes and 'stvewx' not in opcodes,'Clip must preserve adjacent padding'
asm=paths['combiner-miss'][1]
assert 'memset' in asm and re.search(r'li\s+r4,0\b',asm),'POD combiner certificate must be zero-initialized'
# Current Xbox POD includes all 16 metadata certificates and 28 constants.
assert re.search(r'li\s+r5,408\b',asm),'Re-audit complete ColorCombiner zeroing extent'
report={label:{'symbol':name,'instructions':len(ops)} for label,(name,asm,ops) in paths.items()}
(out/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
print('PASS linked production VMX transforms/clip/quantization, delayed RGB stores, finite selects and zeroed combiner certificates')
