"""Compile original and projected real checker as separate ILP32 translation units."""

from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import profile_projections
import bounds_cache_projection
from platform_base import resolve as resolve_platform_base


class BoundsCacheTest(unittest.TestCase):
    def test_production_checker(self):
        out = ROOT / "scratch/port-xdk/bounds-tests"
        out.mkdir(parents=True, exist_ok=True)
        upstream = ROOT / "upstream/BattleShip/port"
        text = (upstream / "port_dl_ranges.cpp").read_text()
        candidate = profile_projections.port("port/port_dl_ranges.cpp", text)
        candidate = bounds_cache_projection.transform(candidate)
        # Count only the generated candidate's gap operations; production stays uninstrumented.
        instrumented = "extern thread_local unsigned testBoundsExcludes;\n" + candidate.replace(
            "unknownGap.Exclude(", "++testBoundsExcludes; unknownGap.Exclude("
        )
        (out / "candidate.cpp").write_text(instrumented)
        names = {
            "port_dl_range_register": "original_register",
            "port_dl_range_unregister": "original_unregister",
            "port_dl_check_addr": "original_check",
            "port_dl_range_classify_str": "original_classify",
            "port_dl_ranges_init": "original_init",
        }
        (out / "original.cpp").write_text("\n".join("#define " + a + " " + b for a, b in names.items()) + "\n" + text)
        (out / "fast").mkdir(exist_ok=True)
        (out / "runtime").mkdir(exist_ok=True)
        (out / "fast/interpreter.h").write_text(
            """\
#pragma once
namespace Fast { inline void RegisterDLBoundsCheck(int(*)(uintptr_t)) \
{} inline void RegisterAddressClassifier(int(*)(uintptr_t,char*,\
size_t)) {} }
"""
        )
        (out / "runtime/perf_trace.h").write_text(
            """#pragma once
enum { SMASH_PERF_BOUNDS_GENERATION, SMASH_PERF_BOUNDS_SCAN,
SMASH_COUNT_BOUNDS_HIT,SMASH_COUNT_BOUNDS_MISS,SMASH_COUNT_BOUNDS_VISITS,
SMASH_COUNT_BOUNDS_FOUND,SMASH_COUNT_BOUNDS_PAST,SMASH_COUNT_BOUNDS_UNKNOWN,
SMASH_COUNT_BOUNDS_UNKNOWN_HIT };
static const bool smash360_perf_detail=true;
extern thread_local unsigned testBoundsScans;
struct Smash360PerfScope { Smash360PerfScope(int section,bool) { if(section==SMASH_PERF_BOUNDS_SCAN) ++testBoundsScans; } };
inline void Smash360_PerfDetailCount(int) {}
"""
        )
        (out / "counter.cpp").write_text(
            "thread_local unsigned testBoundsScans=0;\nthread_local unsigned testBoundsExcludes=0;\n"
        )
        sources = [
            out / "original.cpp",
            out / "candidate.cpp",
            out / "counter.cpp",
            Path(__file__).with_name("bounds_cache_contract.cpp"),
        ]
        batch = out / "build.cmd"
        shipyard = resolve_platform_base(ROOT)
        self.assertFalse((ROOT / "platform/xbox360/cpp-compat/port/bounds_gap.h").exists())
        self.assertIn('#include "memory/address_gap.h"', candidate)
        batch.write_text(
            """\
@echo off
call \"C:/Program Files/Microsoft Visual \
Studio/2022/Community/VC/Auxiliary/Build/vcvars32.bat\" >nul
cl /nologo /std:c++17 /O2 /EHsc /MT /I\""""
            + str(out)
            + '" /I"'
            + str(upstream)
            + '" /I"'
            + str(shipyard / "sources")
            + '" /Fe:bounds.exe '
            + " ".join('"' + str(x) + '"' for x in sources)
            + "\nexit /b %errorlevel%\n"
        )
        result = subprocess.run(["cmd", "/d", "/c", str(batch)], cwd=out, capture_output=True, text=True)
        (out / "build.log").write_text(result.stdout + result.stderr)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        result = subprocess.run([str(out / "bounds.exe")], cwd=out, capture_output=True, text=True, timeout=60)
        (out / "run.log").write_text(result.stdout + result.stderr)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout.strip())


if __name__ == "__main__":
    unittest.main()
