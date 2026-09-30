"""Execute original/projected seg-E correction including token precedence."""

from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import command_work_projection


class StrideTest(unittest.TestCase):
    def test_exact_result_and_avoidable_scans(self):
        source = (ROOT / "upstream/BattleShip/libultraship/src/fast/interpreter.cpp").read_text(encoding="utf-8-sig")
        projected = command_work_projection.interpreter(source)
        functions = []
        for name, text in [("Original", source), ("Projected", projected)]:
            body = text.split("bool gfx_dl_handler_common(", 1)[1]
            body = body[
                body.index("    {\n        // A native host pointer") : body.index(
                    "    // Fallback for packed seg=0x0E"
                )
            ]
            functions.append(
                "template<size_t Stride> uintptr_t " + name + "(uintptr_t base,uintptr_t token,uintptr_t resolved) {\n"
                "struct F3DGfx {char bytes[Stride];}; struct Cmd {struct {uintptr_t w1;} words;}; Cmd command={{token}};Cmd* cmd=&command;\n"
                """\
struct Interpreter {uintptr_t mSegmentPointers[16];}; Interpreter \
instance={}; instance.mSegmentPointers[14]=base; Interpreter* \
gfx=&instance;
"""
                "F3DGfx* subGFX=(F3DGfx*)resolved;\n" + body + "return (uintptr_t)subGFX;\n}\n"
            )
        driver = """#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
enum {MAX_SEGMENT_POINTERS=16,PORT_PACKED_GFX_SIZE=8};
static bool inFile;static unsigned scans;
static bool portRelocFindContainingFile(const void*,uintptr_t* base,size_t* size){++scans;*base=123;*size=456;return inFile;}
// FUNCTIONS
static uint32_t state=0x365709;
static uint32_t Next(){state^=state<<13;state^=state>>17;return state^=state<<5;}
template<size_t Stride> void Test(){
 for(unsigned n=0;n<262144;++n){
  uintptr_t base=n%7?Next():0;uintptr_t token=0x0E000000|(Next()&0xFFFFFF);inFile=!!(n&1);
  // Match the actual resolver's low-bit tag handling; independently cover
  // token-resolved addresses that take precedence over segment resolution.
  uintptr_t resolved=base+(token&0xFFFFFE);
  if(n%3==0)resolved=Next();
  if(n%17==0)token=Next();
  scans=0;uintptr_t a=Original<Stride>(base,token,resolved);unsigned oldScans=scans;
  scans=0;uintptr_t b=Projected<Stride>(base,token,resolved);
  if(a!=b || scans>oldScans){printf("FAIL stride=%u case=%u\\n",unsigned(Stride),n);exit(1);}
  if((token&7)==0 && resolved==uintptr_t(base+(token&0xFFFFFF)/8*Stride) && scans){puts("FAIL redundant scan");exit(2);}
 }
}
int main(){Test<8>();Test<16>();puts("PASS 524288 original/projected stride cases: equal strides, widened lists, tokens, alignment, zero bases, overflow");}
""".replace(
            "// FUNCTIONS", "\n".join(functions)
        )
        out = ROOT / "scratch/fast3d-xdk/stride-tests"
        out.mkdir(parents=True, exist_ok=True)
        (out / "contract.cpp").write_text(driver, encoding="utf-8")
        (out / "build.cmd").write_text(
            """\
@echo off
call \"C:/Program Files/Microsoft Visual \
Studio/2022/Community/VC/Auxiliary/Build/vcvars32.bat\" >nul
cl /nologo /utf-8 /O2 /EHsc /MT contract.cpp /Fe:stride.exe
exit /b %errorlevel%
"""
        )
        result = subprocess.run(["cmd", "/d", "/c", str(out / "build.cmd")], cwd=out, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        result = subprocess.run([str(out / "stride.exe")], cwd=out, capture_output=True, text=True)
        (out / "run.log").write_text(result.stdout + result.stderr)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout.strip())


if __name__ == "__main__":
    unittest.main()
