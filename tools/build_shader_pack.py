"""Build the prebuilt Xenos shader pack for Smash360 offline, without running the game.

    python tools/build_shader_pack.py [--jobs N]

Run after the prepare_*_xdk.py projections (scratch/fast3d-xdk, scratch/prism-xdk,
scratch/graphics-xdk) and prepare_assets.py. Harvests draw states from the native
display lists inside BattleShip.o2r's relocatable files and the decomp's constant
gDP calls, derives keys with the projected GenerateCC and the pinned option block,
generates and lowers each program (ABI 3) on the host, compiles it with the XDK's
fxc and writes scratch/shader-pack/warwing.shaderpack. package.ps1 copies it into shaders/ beside
the XEX; the XEX verifies every program it uses and compiles any mismatch itself.
"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parents[1]
from platform_base import resolve as resolve_platform_base

OUT = ROOT / "scratch/shader-pack"
UPSTREAM = ROOT / "upstream/BattleShip/libultraship"
INTERPRETER = ROOT / "scratch/fast3d-xdk/overlay/libultraship/src/fast/interpreter.cpp"
PRISM = ROOT / "scratch/prism-xdk"
GRAPHICS = ROOT / "platform/xbox360/graphics"
GRAPHICS_INCLUDE = ROOT / "scratch/graphics-xdk/include"
ARCHIVES = (ROOT / "scratch/assets/BattleShip.o2r", ROOT / "scratch/assets/f3d.o2r")
DECOMP = ROOT / "upstream/BattleShip/decomp/src"
TEMPLATE = "shaders/directx/default.shader.hlsl"
RELOCATABLE = 0x52454C4F
ABI = 3

ADAPTER = """#include "prism_shader_builder.h"
extern std::string Shipyard_ShaderPackTemplate;
// The production loader serves the same f3d.o2r template; includes are not offered.
bool Smash360_LoadShaderResource(const std::string& path, std::string& output) {
    if (path != "shaders/directx/default.shader.hlsl")
        return false;
    output = Shipyard_ShaderPackTemplate;
    return true;
}
namespace Fast {
const char* gfx_get_shader(int16_t) {
    return nullptr;
}
}
"""


def require(*paths):
    for path in paths:
        if not path.exists():
            raise FileNotFoundError(str(path) + " is missing; run the prepare_*_xdk.py projections and prepare_assets.py")


def build_generator(base, folder):
    from xbox360_platform import host_toolchain

    folder.mkdir(parents=True, exist_ok=True)
    (folder / "adapter.cpp").write_text(ADAPTER, encoding="utf-8")
    includes = [PRISM, ROOT / "platform/xbox360/cpp-compat/prism", base / "sources", base / "sources/value_types",
                GRAPHICS_INCLUDE, GRAPHICS, ROOT / "upstream/dependencies/spdlog/include"]
    common = ["cl", "/nologo", "/std:c++17", "/utf-8", "/EHsc", "/MT", "/O2", "/DNDEBUG", "/DSPDLOG_ACTIVE_LEVEL=2",
              "/D_CRT_SECURE_NO_WARNINGS", "/DNOMINMAX"] + ["/I" + str(path) for path in includes]
    sources = [PRISM / "prism" / name for name in ("lexer.cpp", "ast.cpp", "processor.cpp", "utils/gv.cpp")]
    sources += [PRISM / "shader_builder.cpp", PRISM / "test_shader_features.cpp", GRAPHICS / "shader_provider.cpp",
                folder / "adapter.cpp", base / "sources/graphics/shader_lower.cpp",
                base / "sources/graphics/shader_pack_sources.cpp"]
    executable = folder / "shader_pack_sources.exe"
    invoke, provider = folder / "invoke.obj", folder / "shipyard_shader_provider.obj"
    host_toolchain.run([["cl", "/nologo", "/TC", "/c", "/MT", PRISM / "prism/utils/invoke.c", "/Fo" + str(invoke)],
                        common + ["/c", base / "sources/graphics/shader_provider.cpp", "/Fo" + str(provider)],
                        common + sources + [invoke, provider, "/Fo:" + str(folder) + "/", "/Fe:" + str(executable)]],
                       folder, "generator")
    return executable


def c_state(folder):
    from xbox360_platform import host_toolchain, shader_pack_harvest as harvest

    folder.mkdir(parents=True, exist_ok=True)
    include = UPSTREAM / "include"
    calls = harvest.c_calls([DECOMP], harvest.defined_macros((include / "libultraship/libultra").glob("*.h")))
    program = folder / "dump.cpp"
    program.write_text(harvest.dump_program(None, calls), encoding="utf-8")
    executable = folder / "dump.exe"
    host_toolchain.run([["cl", "/nologo", "/EHsc", "/MD", "/O1", "/DF3DEX_GBI_2", "/I" + str(include), program,
                         "/Fe:" + str(executable)]], folder, "dump")
    output = subprocess.run([str(executable)], capture_output=True, text=True, check=True).stdout
    setups, modes, records = harvest.c_seeds(output, None, [DECOMP])
    print("C sources: %d constant state calls, %d modes" % (len(calls), len(modes)))
    return setups, modes, records


def build(base, jobs):
    from xbox360_platform import shader_pack, shader_pack_harvest as harvest, shader_pack_keys as keys

    header = UPSTREAM / "include/fast/interpreter.h"
    require(INTERPRETER, header, PRISM / "shader_builder.cpp", PRISM / "test_shader_features.cpp",
            GRAPHICS_INCLUDE / "fast/backends/gfx_rendering_api.h", *ARCHIVES)
    OUT.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ARCHIVES[1]) as archive:
        (OUT / "template.hlsl").write_bytes(archive.read(TEMPLATE))
    setups, modes, c_records = c_state(OUT / "c-state")
    lists, records = harvest.display_list_records(list(ARCHIVES), jobs, raw_types={RELOCATABLE})
    print("archives: %d display lists, %d distinct draw states" % (lists, len(records)))
    states = harvest.expand(records | c_records, setups, modes, jobs, keys.RELEVANT_OTHER_MODE)
    # The projection moved the option block into a cached builder; its text is the pinned one.
    source = keys.harness_source(INTERPRETER.read_text(encoding="utf-8"), header.read_text(encoding="utf-8"),
                                 options_text=(UPSTREAM / "src/fast/interpreter.cpp").read_text(encoding="utf-8"))
    harness = keys.build_harness(source, [UPSTREAM / "include"], OUT / "keys")
    program_keys = keys.derive(harness, states)
    print("draw states: %d, shader keys: %d" % (len(states), len(program_keys)))
    generator = build_generator(base, OUT / "generator")
    record = shader_pack.build(generator, OUT / "template.hlsl", program_keys, ABI, OUT, OUT / "warwing.shaderpack",
                               jobs)
    record.update(display_lists=lists, draw_states=len(states), archives=[str(a) for a in ARCHIVES])
    (OUT / "report.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print("shader pack: %(programs)d programs, %(unique_microcode)d unique microcode blobs, %(bytes)d bytes -> "
          "%(pack)s" % record)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    args = parser.parse_args()
    build(resolve_platform_base(ROOT), args.jobs)


if __name__ == "__main__":
    main()
