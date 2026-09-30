"""Compare the actual BattleShip cost callback before/after Xbox projection."""

from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))


class CommandWorkTests(unittest.TestCase):
    def test_disabled_trace_keeps_cost_model(self):
        import command_work_projection as projection

        text = (ROOT / "upstream/BattleShip/port/gameloop.cpp").read_text(encoding="utf-8-sig")
        begin = text.index("static void gbi_trace_callback(")
        end = text.index("\n}", begin) + 2
        original = text[begin:end]
        changed = projection.port(original)
        preamble = """#include <stdint.h>
#include <assert.h>
#include <stdio.h>
static int enabled, logs;
static void gbi_trace_log_cmd(unsigned long long, unsigned long long, int) { ++logs; }
static int gbi_trace_is_enabled() { return enabled; }
"""
        body = preamble
        for name, callback in [("before", original), ("after", changed)]:
            body += (
                "namespace "
                + name
                + " {\nstatic int sFrameTriCount,sFrameRectPx,sFrameLoadBytes;\n"
                + callback
                + "\n}\n"
            )
        body += """int main() {
  uint32_t rng=71;
  for(int mode=0;mode<2;++mode) {
    enabled=mode;
    for(unsigned i=0;i<65536;++i) {
      rng=rng*1664525u+1013904223u;
      uintptr_t w0=(uintptr_t(i&255)<<24)|(rng&0xffffff);
      uintptr_t w1=rng^0x518ecafeu;
      logs=0;before::gbi_trace_callback(w0,w1,3);assert(logs==1);
      logs=0;after::gbi_trace_callback(w0,w1,3);if(logs!=mode) { puts("disabled trace still entered logger");return 1; }
      assert(before::sFrameTriCount==after::sFrameTriCount);
      assert(before::sFrameRectPx==after::sFrameRectPx);
      assert(before::sFrameLoadBytes==after::sFrameLoadBytes);
    }
  }
  puts("131072 actual callback comparisons; disabled text calls eliminated, RCP counts identical");
}
"""
        out = ROOT / "scratch/command-work-tests"
        out.mkdir(exist_ok=True)
        (out / "callback.cpp").write_text(body, encoding="utf-8")
        (out / "build.cmd").write_text(
            """\
@echo off
call \"C:/Program Files/Microsoft Visual \
Studio/2022/Community/VC/Auxiliary/Build/vcvars32.bat\" >nul
cl /nologo /utf-8 /O2 /EHsc /MT callback.cpp /Fe:callback.exe
exit /b %errorlevel%
"""
        )
        run = subprocess.run(["cmd", "/d", "/c", str(out / "build.cmd")], cwd=out, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        run = subprocess.run([str(out / "callback.exe")], cwd=out, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        (out / "result.log").write_text(run.stdout + run.stderr)
        print(run.stdout.strip())


if __name__ == "__main__":
    unittest.main()
