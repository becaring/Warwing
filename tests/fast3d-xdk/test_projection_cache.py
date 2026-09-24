"""Compare extracted BattleShip culling/area arithmetic with the Xbox projection."""
from pathlib import Path
import importlib
import subprocess
import sys
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))

class ProjectionTests(unittest.TestCase):
    def test_authoritative_cull_and_area(self):
        self.assertTrue((ROOT/'tools/cull_projection.py').exists(), 'projection reuse is missing')
        transform=importlib.import_module('cull_projection').transform
        source=(ROOT/'upstream/BattleShip/libultraship/src/fast/interpreter.cpp').read_text(encoding='utf-8-sig')
        projected=transform(source)
        functions=[]
        for name,text in [('original',source),('cached',projected)]:
            tri=text.split('void Interpreter::GfxSpTri1(',1)[1]
            cull=tri.split('    if ((mRsp->geometry_mode & cull_both) != 0) {',1)[1].split('    // PORT: on the RDP,',1)[0]
            cull='    if ((mRsp->geometry_mode & cull_both) != 0) {'+cull
            cull=cull.replace('return;', 'return true;')
            area=tri.split('        float sx[3], sy[3];',1)[1].split('    for (int i = 0; i < 3; i++) {\n        float z',1)[0]
            area='    {\n        float sx[3], sy[3];'+area
            setup='''Vertex *v1=&v[gIndices[0]], *v2=&v[gIndices[1]], *v3=&v[gIndices[2]];
                Vertex* v_arr[3]={v1,v2,v3};
                unsigned char vtx1_idx=gIndices[0],vtx2_idx=gIndices[1],vtx3_idx=gIndices[2];
                Rsp* mRsp=&rsp; unsigned cull_both=3,cull_front=1,cull_back=2;
                int ucode_handler_index=ucode; Dimensions mNativeDimensions={320,240};
            '''
            functions.append('bool '+name+'_cull(Vertex* v,Rsp rsp,int ucode) {\n'+setup+cull+'return false;\n}')
            functions.append('void '+name+'_area(Vertex* v,float& mFrameTriAreaPx) {\n'+setup.replace('int ucode_handler_index=ucode;', 'int ucode_handler_index=0;').replace('Rsp* mRsp=&rsp;', 'Rsp rsp={0,0}; Rsp* mRsp=&rsp;')+area+'\n}')
        driver=Path(__file__).with_name('projection_contract.cpp').read_text()
        out=ROOT/'scratch/fast3d-xdk/projection-tests';out.mkdir(parents=True,exist_ok=True)
        (out/'contract.cpp').write_text(driver.replace('// EXTRACTED_FUNCTIONS', '\n'.join(functions)))
        batch=out/'build.cmd'
        batch.write_text('@echo off\ncall "C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Auxiliary/Build/vcvars32.bat" >nul\ncl /nologo /O2 /fp:precise /arch:SSE2 /EHsc /MT /I"'+str(ROOT.parent/'LibUltraShip+Fast3D360/sources')+'" /I"'+str(ROOT/'platform/xbox360/cpp-compat')+'" contract.cpp /Fe:projection.exe\nexit /b %errorlevel%\n')
        result=subprocess.run(['cmd','/d','/c',str(batch)],cwd=out,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        result=subprocess.run([str(out/'projection.exe')],cwd=out,capture_output=True,text=True)
        (out/'run.log').write_text(result.stdout+result.stderr)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        print(result.stdout.strip())

if __name__=='__main__':unittest.main()
