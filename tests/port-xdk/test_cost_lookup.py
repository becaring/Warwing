"""Differentials for the inline RCP cost count and the cached reloc-file lookup (ILP32)."""

from pathlib import Path
import re
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import rcp_cost_projection
import reloc_lookup_projection

UPSTREAM = ROOT / "upstream/BattleShip/port"
OUT = ROOT / "scratch/port-xdk/cost-lookup-tests"


def read(relative):
    return (UPSTREAM / relative).read_text(encoding="utf-8").replace("\r\n", "\n")


def between(text, start, end):
    first = text.index(start)
    return text[first:text.index(end, first) + len(end)]


def run(name, source):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / (name + ".cpp")).write_text(source, encoding="utf-8-sig")
    batch = OUT / (name + ".cmd")
    batch.write_text(
        '@echo off\ncall "C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Auxiliary/Build/vcvars32.bat" >nul\n'
        "cl /nologo /std:c++17 /O2 /EHsc /MT /Fe:" + name + ".exe " + name + ".cpp\nexit /b %errorlevel%\n"
    )
    built = subprocess.run(["cmd", "/d", "/c", str(batch)], cwd=OUT, capture_output=True, text=True)
    if built.returncode:
        raise AssertionError(built.stdout + built.stderr)
    ran = subprocess.run([str(OUT / (name + ".exe"))], cwd=OUT, capture_output=True, text=True, timeout=60)
    if ran.returncode:
        raise AssertionError(ran.stdout + ran.stderr)
    return ran.stdout.strip()


class CostLookupTest(unittest.TestCase):
    def test_rcp_cost_matches_callback(self):
        gameloop = read("gameloop.cpp")
        callback = between(gameloop, "static void gbi_trace_callback(", "\tdefault:\n\t\tbreak;\n\t}\n}")
        callback = callback.replace("gbi_trace_log_cmd((unsigned long long)w0, (unsigned long long)w1, dl_depth);", "")
        # The projected gameloop keeps logging only and aliases the shared counters.
        projected = rcp_cost_projection.port(gameloop)
        self.assertIn('extern "C" int gSmashRcpFrameTris = 0;\nstatic int& sFrameTriCount = gSmashRcpFrameTris;', projected)
        self.assertNotIn("sFrameTriCount += ", projected)
        source = """\
#include <stdint.h>
#include <stdio.h>
static int sFrameTriCount = 0, sFrameRectPx = 0, sFrameLoadBytes = 0;
@CALLBACK@
extern "C" int gSmashRcpFrameTris = 0, gSmashRcpFrameRectPx = 0, gSmashRcpFrameLoadBytes = 0;
extern "C" int gbi_trace_is_enabled(void) { return 0; }
@COUNT@
int main() {
    static_assert(sizeof(uintptr_t) == 4, "Xbox-width words");
    uint32_t rng = 0x5eed1234u;
    for (unsigned i = 0; i < 4000000; ++i) {
        rng = rng * 1664525u + 1013904223u; uintptr_t w0 = rng;
        rng = rng * 1664525u + 1013904223u; uintptr_t w1 = rng;
        if (i & 1) w0 = (w0 & 0x00FFFFFFu) | ((uintptr_t)"\\x05\\x06\\x07\\xE4\\xF6\\xF3\\xF4\\xE7"[i >> 1 & 7] << 24);
        gbi_trace_callback(w0, w1, 0);
        XboxCountRcpCost(w0, w1);
        if (sFrameTriCount != gSmashRcpFrameTris || sFrameRectPx != gSmashRcpFrameRectPx ||
            sFrameLoadBytes != gSmashRcpFrameLoadBytes) { printf("FAIL at %u\\n", i); return 1; }
    }
    printf("PASS inline RCP cost: tris=%d rect_px=%d load_bytes=%d\\n", gSmashRcpFrameTris,
           gSmashRcpFrameRectPx, gSmashRcpFrameLoadBytes);
}
""".replace("@CALLBACK@", callback).replace("@COUNT@", rcp_cost_projection.COUNT)
        print(run("rcp_cost", source))

    def test_reloc_lookup_matches_scan(self):
        text = reloc_lookup_projection.transform(read("bridge/lbreloc_bridge.cpp"))
        state = between(text, "struct PortRelocFileRange", "sPortRelocLookupNext = 0;\n")
        # The cached wrapper, the gap scan and the renamed upstream body, in order.
        lookup = between(text, "static bool portRelocFirstContainingFile(const void *ptr, uintptr_t *out_base, size_t *out_size);",
                         "\t\t}\n\t}\n\treturn FALSE;\n}\n")
        self.assertEqual(len(re.findall(r"\+\+gPortRelocFileRangesGen;", text)), 4)
        source = """\
#include <stdint.h>
#include <stdio.h>
#include <vector>
typedef uint32_t u32;
#define TRUE 1
#define FALSE 0
#define __declspec(x) thread_local
@STATE@
@LOOKUP@
static bool naive(uintptr_t a, uintptr_t* base, size_t* size) {
    for (const auto& r : sPortRelocFileRanges) if (a >= r.base && r.size && a - r.base < r.size) { *base = r.base; *size = r.size; return true; }
    return false;
}
int main() {
    uint32_t rng = 0x1234abcdu;
    for (unsigned i = 0; i < 2000000; ++i) {
        rng = rng * 1664525u + 1013904223u;
        if ((rng >> 24) < 3) {
            // Disjoint ranges, as the loaders guarantee by evicting overlaps first.
            sPortRelocFileRanges.clear();
            for (uintptr_t b = 0x10000 + (rng & 0xF00); b < 0x90000; b += 0x10000)
                if ((b >> 16) & (rng >> 8) & 1 ? 0 : 1) {
                    sPortRelocFileRanges.push_back({ b, (size_t)(0x800 + (rng & 0x7FF)), 0, "" });
                    // Empty ranges contain nothing and must not bound a gap.
                    if (rng & 0x10000) sPortRelocFileRanges.push_back({ b + 0x9000, 0, 0, "" });
                }
            ++gPortRelocFileRangesGen;
        }
        const uintptr_t a = 0x8000 + (rng % 0x90000);
        uintptr_t base = 0, nb = 0; size_t size = 0, ns = 0;
        const bool got = portRelocFindContainingFile((const void*)a, &base, &size);
        const bool want = naive(a, &nb, &ns);
        if (got != want || (got && (base != nb || size != ns))) { printf("FAIL addr=%x\\n", (unsigned)a); return 1; }
    }
    puts("PASS cached reloc lookup: matches the uncached scan across range-list changes");
}
""".replace("@STATE@", state).replace("@LOOKUP@", lookup)
        print(run("reloc_lookup", source))


if __name__ == "__main__":
    unittest.main()
