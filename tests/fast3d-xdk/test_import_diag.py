"""Compare real import-log acceptance, stages and quota use; observe lazy payload reads."""
from pathlib import Path
import re
import subprocess
import sys
import unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import import_diag_projection as projection

class ImportDiagTests(unittest.TestCase):
    def test_acceptance_and_lazy_payload(self):
        source=(ROOT/'upstream/BattleShip/libultraship/src/fast/interpreter.cpp').read_text(encoding='utf-8-sig')
        projected=projection.transform(source)
        self.assertIn('Ssb64RenderDiagShouldLogImport',projected)
        pattern=r'(?m)^([ ]*)Ssb64RenderDiagLogImport\("(?:import|cache-hit|cache-miss)"[\s\S]*?importReplacement\);'
        original_calls=[m.group(0).strip() for m in re.finditer(pattern,source)]
        projected_calls=[m.group(0).strip() for m in re.finditer(pattern,projected)]
        self.assertEqual(len(original_calls),3)
        normalize=lambda calls:['\n'.join(line.lstrip() for line in call.splitlines()) for call in calls]
        self.assertEqual(normalize(original_calls),normalize(projected_calls),'all diagnostic arguments must remain identical apart from indentation')
        def functions(text,name):
            start=text.index('static bool Ssb64RenderDiagShouldLogImport') if name=='Projected' else text.index('static void Ssb64RenderDiagLogImport(')
            end=text.index('    uint32_t tileW =',start)
            log=text[start:end]+'    Record(stage);\n}\n'
            # Extract actual production call blocks; use the same cache hit/miss selection.
            calls=[]
            for match in re.finditer(pattern,text):
                call=match.group(0).strip()
                if name=='Projected':
                    prefix=text[:match.start()].rstrip()
                    self.assertTrue(prefix.endswith('if (Ssb64RenderDiagShouldLogImport(metadata, origAddr)) {'))
                    call='if (Ssb64RenderDiagShouldLogImport(metadata, origAddr)) {\n'+call+'\n}'
                calls.append(call)
            return 'namespace '+name+' {\n'+STATE+log+'''void Run(bool hit) {
 RawTexMetadata* metadata=0;const void* origAddr=0;int i=0,tile=0,tmemIdex=0;
 uint8_t fmt=0,siz=0;uint32_t origSizeBytes=64;bool importReplacement=false;
 Rdp rdp={};Rdp* mRdp=&rdp;
 '''+calls[0]+'\nif(hit){'+calls[1]+'}else{'+calls[2]+'}\n}\n}\n'
        driver='''#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
struct RawTexMetadata {};
static unsigned payloadReads;
struct Payload {operator uint32_t()const {++payloadReads;return 4;}};
struct Tile {uint8_t cms,cmt,masks,maskt,shifts,shiftt;uint32_t line_size_bytes;Payload uls,ult,lrs,lrt;};
struct Loaded {uint32_t line_size_bytes,full_image_line_size_bytes,size_bytes;};
struct Rdp {Tile texture_tile[1];Loaded loaded_texture[1];};
'''+functions(source,'Original')+functions(projected,'Projected')+'''
int main(){unsigned cases=0;
 for(int enabled=0;enabled<2;++enabled)for(int match=0;match<2;++match)
 for(int armed=0;armed<6;++armed)for(int quota=0;quota<5;++quota)for(int hit=0;hit<2;++hit){
  Original::Reset(enabled,match,armed,quota);Projected::Reset(enabled,match,armed,quota);
  for(int n=0;n<8;++n){
   payloadReads=0;Original::Run(hit!=0);if(payloadReads!=8)abort();
   int previous=Projected::records;payloadReads=0;Projected::Run(hit!=0);
   if(payloadReads!=unsigned((Projected::records-previous)*4))abort();
   if(Original::credits!=Projected::credits || Original::quota!=Projected::quota ||
      Original::matchChecks!=Projected::matchChecks || Original::slotChecks!=Projected::slotChecks ||
      Original::records!=Projected::records || Original::stages!=Projected::stages)abort();
   ++cases;
  }
 }
 printf("PASS %u original/projected diagnostic stages: armed capture, filters, quotas, lazy payload\\n",cases);
}
'''
        out=ROOT/'scratch/fast3d-xdk/import-diag-tests';out.mkdir(parents=True,exist_ok=True)
        (out/'contract.cpp').write_text(driver,encoding='utf-8')
        (out/'build.cmd').write_text('@echo off\ncall "C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Auxiliary/Build/vcvars32.bat" >nul\ncl /nologo /O2 /EHsc /MT contract.cpp /Fe:contract.exe\nexit /b %errorlevel%\n')
        result=subprocess.run(['cmd','/d','/c',str(out/'build.cmd')],cwd=out,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        result=subprocess.run([str(out/'contract.exe')],cwd=out,capture_output=True,text=True)
        (out/'run.log').write_text(result.stdout+result.stderr)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        print(result.stdout.strip())

STATE='''static int enabled,matching,credits,quota,matchChecks,slotChecks,records;
static unsigned stages;
static bool Ssb64RenderDiagArmedTake(){if(credits>0){--credits;return true;}return false;}
static bool Ssb64RenderDiagMatches(const RawTexMetadata*,const void*){++matchChecks;return enabled && matching;}
static bool Ssb64RenderDiagTakeSlot(){++slotChecks;if(quota>0){--quota;return true;}return false;}
static void Record(const char* stage){++records;stages=stages*7+(strcmp(stage,"import")==0?1:strcmp(stage,"cache-hit")==0?2:3);}
static void Reset(int e,int m,int c,int q){enabled=e;matching=m;credits=c;quota=q;matchChecks=slotChecks=records=0;stages=0;}
'''
if __name__=='__main__':unittest.main()
