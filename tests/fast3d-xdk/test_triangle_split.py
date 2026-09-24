"""Reject-path execution and exact preservation of the extracted emitter."""
from pathlib import Path
import subprocess
import sys
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import triangle_split_projection as split
SIGNATURE=split.fast3d_triangle_split.SIGNATURE

class SplitTests(unittest.TestCase):
    def test_original_cull_to_emit_and_scope_lifetime(self):
        source=(ROOT/'upstream/BattleShip/libultraship/src/fast/interpreter.cpp').read_text(encoding='utf-8-sig')
        # Use the unchanged upstream culling front; production additionally
        # uses the separately tested projection cache. Substitute only the
        # heavy suffix with a test observer after checking byte preservation.
        source=source.replace(SIGNATURE,SIGNATURE+'\n    SmashTriangleTrace triangleTrace;')
        projected=split.transform(source)
        a=source[source.index(SIGNATURE):source.index('\nvoid Interpreter::GfxSpGeometryMode(')]
        b=projected[projected.index(SIGNATURE):projected.index('\nvoid Interpreter::GfxSpGeometryMode(')]
        self.assertEqual(a[a.index(split.BOUNDARY):],b[b.index(split.BOUNDARY):])
        original=a[:a.index(split.BOUNDARY)]+'    Observe(vtx1_idx,vtx2_idx,vtx3_idx,is_rect,triangleTrace);\n}\n'
        candidate=b[:b.index(split.BOUNDARY)]+'    Observe(vtx1_idx,vtx2_idx,vtx3_idx,is_rect,triangleTrace);\n}\n'
        functions=original.replace('Interpreter::','Original::')+candidate.replace('Interpreter::','Projected::')
        driver='''#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static unsigned liveTrace,createdTrace,observed;
struct SmashTriangleTrace {SmashTriangleTrace(){++liveTrace;++createdTrace;}~SmashTriangleTrace(){--liveTrace;}};
struct LoadedVertex {float x,y,z,w;unsigned clip_rej;};
struct RSP {LoadedVertex loaded_vertices[68];unsigned geometry_mode,extra_geometry_mode;};
namespace UcodeHandlers {enum {ucode_f3dex2=1};}
enum {CULL_BOTH=3,CULL_FRONT=1,CULL_BACK=2,G_EX_INVERT_CULLING=1};
static unsigned get_attr(unsigned a){return a;}
static int ucode_handler_index;
static void Observe(uint8_t a,uint8_t b,uint8_t c,bool rect,SmashTriangleTrace&) {
 if(liveTrace!=1 || createdTrace!=1)abort(); observed=1+a*3+b*7+c*13+rect*1024;
}
#define HARNESS(name) struct name {RSP* mRsp;void GfxSpTri1(uint8_t,uint8_t,uint8_t,bool);void XboxEmitTriangle(uint8_t,uint8_t,uint8_t,bool,SmashTriangleTrace&);};
HARNESS(Original) HARNESS(Projected)
// FUNCTIONS
static uint32_t randomState=0x732184;
static uint32_t Next(){randomState^=randomState<<13;randomState^=randomState>>17;return randomState^=randomState<<5;}
int main(){RSP rsp={};Original a={&rsp};Projected b={&rsp};
 for(unsigned n=0;n<131072;++n){
  for(unsigned i=0;i<68;++i){rsp.loaded_vertices[i].x=int(Next()%8193)-4096.0f;rsp.loaded_vertices[i].y=int(Next()%8193)-4096.0f;
   rsp.loaded_vertices[i].w=(int(Next()%1025)-512)*0.25f;rsp.loaded_vertices[i].clip_rej=(n&1)?Next()%32:0;}
  rsp.geometry_mode=(n>>1)%4;rsp.extra_geometry_mode=(n>>3)%2;ucode_handler_index=(n>>4)%2;
  uint8_t x=Next()%68,y=Next()%68,z=Next()%68;bool rect=!!(n&32);
  createdTrace=observed=0;a.GfxSpTri1(x,y,z,rect);unsigned expect=observed;if(liveTrace || createdTrace!=1)abort();
  createdTrace=observed=0;b.GfxSpTri1(x,y,z,rect);
  if(liveTrace || createdTrace!=1 || observed!=expect){printf("FAIL %u\\n",n);return 1;}
 } puts("PASS 131072 actual cull-to-emit cases, indices/rect forwarding and one trace lifetime; emit body unchanged");}
'''.replace('// FUNCTIONS',functions)
        out=ROOT/'scratch/fast3d-xdk/triangle-split-tests';out.mkdir(parents=True,exist_ok=True)
        (out/'contract.cpp').write_text(driver,encoding='utf-8')
        (out/'build.cmd').write_text('@echo off\ncall "C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Auxiliary/Build/vcvars32.bat" >nul\ncl /nologo /utf-8 /O2 /fp:precise /EHsc /MT contract.cpp /Fe:split.exe\nexit /b %errorlevel%\n')
        result=subprocess.run(['cmd','/d','/c',str(out/'build.cmd')],cwd=out,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        result=subprocess.run([str(out/'split.exe')],cwd=out,capture_output=True,text=True)
        (out/'run.log').write_text(result.stdout+result.stderr)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        print(result.stdout.strip())
if __name__=='__main__':unittest.main()
