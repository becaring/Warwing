"""Compile/exercise extracted actual overlay helpers, not replacement algorithms.

BE-policy host execution checks bytes and deswizzle, NOT native PPC arithmetic.
"""

from pathlib import Path
import argparse
import json
import re
import subprocess
import sys
import zipfile
import struct

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "tests/endian/out"


def function(text, signature):
    start = text.index(signature)
    masked = re.sub(
        r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', lambda m: " " * len(m[0]), text, flags=re.S
    )
    pos = masked.index("{", start)
    level = 1
    end = pos + 1
    while level:
        level += (masked[end] == "{") - (masked[end] == "}")
        end += 1
    return text[start:end]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--overlay", type=Path, default=ROOT / "scratch/endian-xdk/source")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    overlay = args.overlay
    b = (overlay / "port/bridge/lbreloc_byteswap.cpp").read_text(encoding="utf-8")
    p = (overlay / "port/bridge/particle_bank_bridge.cpp").read_text(encoding="utf-8")
    lb = (overlay / "decomp/src/lb/lbparticle.c").read_text(encoding="utf-8")
    bridge = (overlay / "port/bridge/lbreloc_bridge.cpp").read_text(encoding="utf-8")
    fig = re.search(r"bool is_fighter_figatree =.*?;", bridge, re.S)[0]
    prefix = """#include <smash360_endian.h>
#include <decomp/include/config.h>
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <unordered_map>
#include <unordered_set>
#include <vector>
typedef unsigned char u8; typedef float f32; typedef unsigned int u32; typedef int s32;
static std::unordered_set<uintptr_t> sStructU16Fixups,sTexFixupWords,sDeswizzle4cFixups,sChainSlotAddrs;
static std::unordered_map<uintptr_t,unsigned int> sTexFixupExtent;
struct ProtectedRange { uintptr_t begin,end; };
static std::vector<ProtectedRange> sProtectedStructRanges;
static void *testBuffer;
extern "C" void *portRelocTryResolvePointer(uint32_t token) { return token == 123 ? testBuffer : NULL; }
static bool testAudit=false,testTexLog=false,testTexDump=false;
static bool stage_audit_enabled() { return testAudit; }
static bool tex_log_enabled() { return testTexLog; }
static bool tex_dump_enabled() { return testTexDump; }
static uintptr_t testRelocBase=0;
static size_t testRelocSize=0;
static unsigned testRangeQueries=0;
static int portRelocFindContainingFile(const void *p,uintptr_t *base,size_t *size) {
    ++testRangeQueries; uintptr_t address=(uintptr_t)p;
    if(address<testRelocBase || address-testRelocBase>=testRelocSize) return 0;
    *base=testRelocBase; *size=testRelocSize; return 1;
}
static bool portRelocDescribePointer(const void*,uintptr_t*,size_t*,unsigned*,const char**) { return false; }
#define port_log(...) ((void)0)
#define portStageAuditNoteTexDispatch(...) ((void)0)
#define portStageAuditNoteRuntimeTex(...) ((void)0)
#define portStageAuditNoteVtxDispatch(...) ((void)0)
#define portStageAuditNoteVtxDispatchFile(...) ((void)0)
#define portStageAuditNoteRuntimeVtx(...) ((void)0)
static int portRelocFindFileIdAndBase(const void*,uintptr_t*) { return -1; }
#define tex_log_emit(...) ((void)0)
#define tex_dump_known_dims(...) ((void)0)
static bool portRelocIsFighterFigatreeFile(unsigned file_id) { return file_id==1; }
static void check(bool value,const char *why) { if(!value) throw std::runtime_error(why); }
"""
    signatures = [
        "static void portRegisterProtectedStructRange",
        "static inline uint32_t rotate16",
        "static void apply_fixup_vertex",
        "static void apply_fixup_tex_u16",
        'extern "C" void portFixupStructU16',
        'extern "C" void portFixupStructU32',
        'extern "C" void portResetStructFixups',
        'extern "C" void portEvictStructFixupsInRange',
        "static void fixup_u16_u8u8",
        'extern "C" void *portFixupFTTexturePartContainer',
        'extern "C" void portFixupSpriteBitmapData',
        'extern "C" void portDeswizzleDecodedSprite4c',
        'extern "C" void portMarkSyntheticSprite',
    ]
    parts = [prefix] + [function(b, s) for s in signatures]
    parts += [
        function(b, 'extern "C" void portRelocFixupTextureAtRuntime'),
        function(b, 'extern "C" void portRelocFixupVertexAtRuntime'),
    ]
    parts += [(ROOT / "tests/endian/runtime_fixup_cases.cpp").read_text()]
    parts += [
        function(p, "static inline void bswap16At"),
        function(p, "static inline void bswap32At"),
        function(lb, "u8* lbParticleReadFloatBigEnd"),
    ]
    audio = (overlay / "port/bridge/audio_bridge.cpp").read_text(encoding="utf-8")
    parts += [
        "static void audioEnvelope(const u8 *src,u8 *dst) { memcpy(dst,src,4); "
        + function(audio, "for (s32 w = 1; w < 4; w++)")
        + " }"
    ]
    audio_game = overlay / "decomp/src/sys/audio.c"
    if not audio_game.exists():
        audio_game = ROOT / "upstream/BattleShip/decomp/src/sys/audio.c"
    audio_text = audio_game.read_text(encoding="utf-8")
    begin = audio_text.index("/* PORT: Byte-swap the ALCMidiHdr")
    end = audio_text.index("sSYAudioCSPlayerStatuses[port_i]++;", begin)
    parts += [
        "static void sequenceHeader(u32 *words) { u8 *sSYAudioBGMSequenceDatas[]={(u8*)words}; int port_i=0; "
        + audio_text[begin:end]
        + " }"
    ]
    parts += [
        "static bool figatree(bool force_figatree_fixup,unsigned file_id) { " + fig + " return is_fighter_figatree; }"
    ]
    archive = ROOT / "scratch/assets/BattleShip.o2r"
    with zipfile.ZipFile(archive) as z:
        fgm = z.read("audio/fgm_unk")[68:]
        particle = z.read("particles/efcommon_particle_scb")[68:]
        sbk = z.read("audio/S1_music_sbk")[68:]
    count = struct.unpack_from(">H", sbk, 2)[0]
    assert count == 47
    headers = []
    for index in range(count):
        offset, length = struct.unpack_from(">II", sbk, 4 + index * 8)
        assert length >= 68 and offset + length <= len(sbk)
        headers.append(struct.unpack_from(">17I", sbk, offset))
    parts += [
        "static const u32 sequenceHeaders[47][17]={"
        + ",".join("{" + ",".join(str(v) + "u" for v in row) + "}" for row in headers)
        + "};"
    ]
    assert fgm[:16].hex() == "00000064070c000042c80000433e0000"
    assert particle[:8].hex() == "00000077000001e0"
    parts += ["static unsigned char fgm[] = {" + ",".join(str(x) for x in fgm[:20]) + "};"]
    parts += ["static unsigned char particle[] = {" + ",".join(str(x) for x in particle[:8]) + "};"]
    parts += [(ROOT / "tests/endian/helper_cases.cpp").read_text()]
    test = OUT / "helpers.cpp"
    test.write_text("\n".join(parts), encoding="utf-8")
    vswhere = Path("C:/Program Files (x86)/Microsoft Visual Studio/Installer/vswhere.exe")
    vs = subprocess.check_output(
        [
            str(vswhere),
            "-latest",
            "-products",
            "*",
            "-requires",
            "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
            "-property",
            "installationPath",
        ],
        text=True,
    ).strip()
    for be in (1, 0):
        exe = OUT / f"helpers-{be}.exe"
        batch = OUT / f"build-{be}.cmd"
        flags = "/D_XBOX /D_M_PPC" if be else ""
        batch.write_text(
            f"""@echo off\n\
call "{vs}/VC/Auxiliary/Build/vcvars64.bat" >nul\n\
if errorlevel 1 exit /b 1\n\
cl /nologo /EHsc /MT /DPORT /DPOLICY_BE={be} {flags} /I"{overlay}" "{test}" /Fo"{OUT}/helpers-{be}.obj" /Fe"{exe}"\n\
exit /b %errorlevel%\n\
"""
        )
        compiled = subprocess.run(["cmd", "/d", "/c", str(batch)], capture_output=True, text=True)
        (OUT / f"compile-{be}.log").write_text(compiled.stdout + compiled.stderr)
        if compiled.returncode:
            print(compiled.stdout + compiled.stderr)
            return compiled.returncode
        run = subprocess.run([str(exe)], capture_output=True, text=True)
        (OUT / f"run-{be}.log").write_text(run.stdout + run.stderr)
        print(run.stdout + run.stderr)
        if run.returncode:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
