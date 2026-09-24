"""Donor VMX lane-model differential, actual vertex composition, XDK codegen.

The host lane model exercises imported source, not a substitute production path.
Native instruction checks prove compilation only; hardware validation is separate.
"""
from pathlib import Path
import importlib
import re
import subprocess
import sys
import unittest
from test_vertex_lighting import extract, accumulation_probe

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
HERE = Path(__file__).parent
OUT = ROOT / 'scratch/fast3d-xdk/transform-tests'
NATIVE = ROOT.parent / 'LibUltraShip+Fast3D360/sources/fast3d/vertex_transform.cpp'
SHIPYARD = ROOT.parent / 'LibUltraShip+Fast3D360/sources'
CLIP = SHIPYARD / 'fast3d/clip_quantize.cpp'


def run(command, label, cwd=OUT):
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    (OUT / (label + '.log')).write_text(result.stdout + result.stderr)
    if result.returncode:
        raise AssertionError(result.stdout + result.stderr)
    return result.stdout


def host(source, name):
    includes = [HERE / 'vmx_model', SHIPYARD, ROOT / 'platform/xbox360',
                ROOT / 'platform/xbox360/cpp-compat',
                ROOT / 'upstream/BattleShip/libultraship/include',
                ROOT.parent / 'LibUltraShip+Fast3D360/sources/value_types', ROOT / 'scratch/graphics-xdk/include']
    batch = OUT / (name + '.cmd')
    batch.write_text('@echo off\ncall "C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Auxiliary/Build/vcvars32.bat" >nul\n'
                     'cl /nologo /std:c++20 /O2 /fp:precise /arch:SSE2 /EHsc /MT /DNOMINMAX ' +
                     ' '.join('/I"' + str(p) + '"' for p in includes) +
                     ' "' + str(source) + '" "' + str(NATIVE) + '" "' + str(CLIP) + '" /Fe:' + name + '.exe\nexit /b %errorlevel%\n')
    run(['cmd', '/d', '/c', str(batch)], name + '-compile')
    print(run([str(OUT / (name + '.exe'))], name + '-run'))


class TransformTests(unittest.TestCase):
    def setUp(self):
        OUT.mkdir(parents=True, exist_ok=True)

    def test_imported_donor_arithmetic(self):
        host(HERE / 'vertex_transform_donor_cases.cpp', 'donor')

    def test_xdk_instructions(self):
        sdk = Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK')
        assembly = ''
        for source in (NATIVE, CLIP):
            obj = OUT / (source.stem + '.obj')
            run([str(sdk / 'bin/win32/cl.exe'), '/nologo', '/c', '/O2', '/Ob2', '/MT', '/EHsc',
                 '/fp:precise', '/D_XBOX', '/DNOMINMAX', '/I' + str(sdk / 'include/xbox'),
                 '/I' + str(SHIPYARD), '/I' + str(ROOT / 'platform/xbox360'),
                 '/Fo' + str(obj), str(source)], source.stem + '-xdk-compile')
            assembly += run([str(sdk / 'bin/win32/dumpbin.exe'), '/disasm', str(obj)], source.stem + '-xdk-disasm')
        for symbol in ('TransformPositions@Fast3D@Shipyard', 'QuantizeMatrix@Fast3D@Shipyard',
                       'ClipVertices@Fast3D@Shipyard', 'ClipFiniteVertices@Fast3D@Shipyard'):
            self.assertIn(symbol, assembly)
        ops = re.findall(r'(?m)^\s*[0-9A-Fa-f]+:\s+[0-9A-Fa-f]{8}\s+(\S+)', assembly)
        for needed in ('vupkhsh', 'vcsxwfp', 'vcfpsxws', 'vmulfp', 'vaddfp', 'stvebx'):
            self.assertTrue(any(op.startswith(needed) for op in ops), needed)
        self.assertFalse(any(op.startswith(('vmadd', 'vnmsub', 'vmsum')) for op in ops),
                         'native vector positions changed scalar rounding/order')
        self.assertEqual(sum(op.startswith('vmulfp') for op in ops), 3)
        self.assertEqual(sum(op.startswith('vaddfp') for op in ops), 3)
        self.assertEqual(sum(op.startswith('vcfpsxws') for op in ops), 4)
        self.assertGreaterEqual(sum(op.startswith('stvebx') for op in ops), 4,
                         'both clip policies must preserve the adjacent bytes')
        self.assertNotIn('stvewx', ops, 'clip store overwrites LoadedVertex padding')

    def test_actual_vertex_composition(self):
        original = (ROOT / 'upstream/BattleShip/libultraship/src/fast/interpreter.cpp').read_text(encoding='utf-8-sig')
        lighting = importlib.import_module('vertex_lighting_projection')
        reuse = importlib.import_module('vertex_reuse_projection')
        transform = importlib.import_module('vertex_transform_projection')
        projected = transform.transform(reuse.transform(lighting.transform(original)))
        accumulation_source = projected
        extra_projection = getattr(self, 'extra_projection', None)
        if extra_projection:
            projected = extra_projection(projected)
        projected = projected.replace(reuse.COPY_MARKER, reuse.COPY_MARKER + '\n                ++observedShadeReuse;')
        signatures = ['void Interpreter::NormalizeVector(', 'void Interpreter::TransposedMatrixMul(',
                      'void Interpreter::CalculateNormalDir(', 'float Interpreter::GetWidescreenClipXScale(',
                      'float Interpreter::AdjXForAspectRatio(', 'void Interpreter::GfxSpVertex(']
        functions = []
        for name, text in [('Original', original), ('Projected', projected)]:
            for signature in signatures:
                functions.append(extract(text, signature).replace('Interpreter::', name + '::'))
        driver = (HERE / 'vertex_lighting_contract.cpp').read_text()
        driver = '#include "fast3d/clip_quantize.h"\n' + driver
        driver = getattr(self, 'extra_includes', '') + driver
        utils = (ROOT / 'upstream/BattleShip/libultraship/src/ship/utils/Utils.cpp').read_text()
        driver = driver.replace('// EXTRACTED_SHIP_CLAMP', extract(utils, 'float clamp('))
        driver = driver.replace('// EXTRACTED_FUNCTIONS', '\n\n'.join(functions))
        driver = driver.replace('// EXTRACTED_ACCUMULATION', accumulation_probe(original, 'AccumulationOriginal') +
                                accumulation_probe(accumulation_source, 'AccumulationProjected'))
        extra = r'''
static void batchEdges() {
    // Counts outside the optimized range still have legitimate backing memory
    // in this harness; the original code, not the batch helper, owns them.
    for(unsigned variant=0;variant<8;++variant) {
        Fast::RSP a={};
        a.modelview_matrix_stack_size=1;
        for(unsigned axis=0;axis<4;++axis) a.MP_matrix[axis][axis]=1.0f;
        a.MP_matrix[3][3]=32.0f;
        a.texture_scaling_factor.s=a.texture_scaling_factor.t=65535;
        Fast::F3DVtx vertices[65]={};
        for(unsigned i=0;i<65;++i) {
            vertices[i].v.ob[0]=(short)(i*271-1000);
            vertices[i].v.ob[1]=(short)(i*31+29);
            vertices[i].v.ob[2]=(short)(i*197-17);
            vertices[i].v.cn[0]=(uint8_t)i;vertices[i].v.cn[3]=(uint8_t)(i+23);
        }
        memset(a.loaded_vertices,0xa5,sizeof(a.loaded_vertices));
        if(variant==0) memcpy(a.loaded_vertices,vertices,8*sizeof(Fast::F3DVtx));
        if(variant==1) a.MP_matrix[0][0]=fromBits(1); // donor range rejection
        if(variant==2) a.MP_matrix[0][0]=fromBits(0x7fc01234); // general IEEE clip
        Fast::RSP b=a;
        Fast::Original original={&a,false,true,{0,0,1280,720}};
        Fast::Projected adapted={&b,false,true,{0,0,1280,720}};
        unsigned count=variant==3?65:variant==4?0:variant==5?1:8;
        unsigned dest=variant==5?65:variant==3?0:3;
        const Fast::F3DVtx* av=variant==0?(const Fast::F3DVtx*)a.loaded_vertices:variant==6?NULL:vertices;
        const Fast::F3DVtx* bv=variant==0?(const Fast::F3DVtx*)b.loaded_vertices:variant==6?NULL:vertices;
        original.GfxSpVertex(count,dest,av);adapted.GfxSpVertex(count,dest,bv);
        require(memcmp(&a,&b,sizeof(a))==0,"alias/null/invalid-count/exceptional matrix output changed");
    }
    const uint32_t accepted[]={0,0x80000000,1,0x80000001,0x3f800000,0xbf800000};
    const uint32_t rejected[]={0x3f800001,0xbf800001,0x7f800000,0xff800000,0x7fc01234};
    for(unsigned i=0;i<sizeof(accepted)/4;++i)require(Shipyard::Fast3D::FiniteUnitClipScale(fromBits(accepted[i])),"finite scale accepted");
    for(unsigned i=0;i<sizeof(rejected)/4;++i)require(!Shipyard::Fast3D::FiniteUnitClipScale(fromBits(rejected[i])),"nonbounded scale rejected");
}
'''
        driver = driver.replace('int main() {', extra + '\nint main() {\n    batchEdges();')
        extra_driver = getattr(self, 'extra_driver', None)
        if extra_driver:
            driver = extra_driver(driver)
        (OUT / 'composed.cpp').write_text(driver)
        host(OUT / 'composed.cpp', 'composed')


if __name__ == '__main__':
    unittest.main()
