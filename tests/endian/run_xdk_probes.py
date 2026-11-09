"""Compile actual generated config/du and pinned representative ABI declarations.

Inspect XDK object bytes; do not execute a host simulation as Xbox proof.
"""

from pathlib import Path
import re
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/endian"))
from run_helpers import function

OUT = ROOT / "tests/endian/out"
OVERLAY = ROOT / "scratch/endian-xdk/source"


def declaration(text, signature):
    start = text.index(signature)
    end = start
    pos = text.index("{", start)
    level = 1
    end = pos + 1
    while level:
        level += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start : end + 1]


def symbol_bytes(obj, name, size):
    raw = obj.read_bytes()
    _, nsections, _, sympos, nsymbols, optional, _ = struct.unpack_from("<HHIIIHH", raw, 0)
    strings = sympos + nsymbols * 18
    sections = []
    for i in range(nsections):
        offset = 20 + optional + i * 40
        sections.append(struct.unpack_from("<I", raw, offset + 20)[0])
    i = 0
    while i < nsymbols:
        pos = sympos + i * 18
        encoded = raw[pos : pos + 8]
        if encoded[:4] == b"\0" * 4:
            textpos = strings + struct.unpack_from("<I", encoded, 4)[0]
            symbol = raw[textpos : raw.index(b"\0", textpos)].decode()
        else:
            symbol = encoded.rstrip(b"\0").decode()
        value, section, _, _, aux = struct.unpack_from("<IhHBB", raw, pos + 8)
        if symbol == name:
            assert section > 0, (name, section)
            offset = sections[section - 1] + value
            return raw[offset : offset + size]
        i += 1 + aux
    raise AssertionError("missing object symbol " + name)


def main():
    OUT.mkdir(exist_ok=True)
    source = """\
#include <smash360_endian.h>
#include <config.h>
typedef unsigned int u32; typedef int s32; typedef unsigned short u16;\
 typedef short s16; typedef unsigned int ub32; typedef float f32;
struct Vec2b { signed char x,y; };
"""
    for path, name in [
        ("sys/objtypes.h", "union AObjEvent16"),
        ("sys/objtypes.h", "union AObjEvent32"),
        ("ft/fttypes.h", "union FTKeyEvent"),
        ("ft/fttypes.h", "struct FTMotionEventMakeAttack1"),
    ]:
        source += declaration((ROOT / "upstream/BattleShip/decomp/src" / path).read_text(), name) + "\n"
    guint = (OVERLAY / "decomp/include/PR/guint.h").read_text()
    a = guint.index("#if !SMASH360_HOST_BIG_ENDIAN")
    b = guint.index("typedef union", guint.index("#define DU_INIT(hi_, lo_) { hi_, lo_ }"))
    source += guint[a:b]
    wp = OVERLAY / "decomp/src/wp/wptypes.h"
    wptext = wp.read_text()
    source += (
        "\nstruct Vec3h { s16 x,y,z; };\n"
        + declaration(wptext, "struct WPAttributes")
        + "\ntypedef char checkWPSize[(sizeof(WPAttributes)==0x34)?1:-1];\n"
    )
    it = (OVERLAY / "decomp/src/it/ittypes.h").read_text()
    source += declaration(it, "struct ITAttackEvent") + "\n" + declaration(it, "struct ITMonsterEvent") + "\n"
    sc = (OVERLAY / "decomp/src/sc/sctypes.h").read_text()
    source += (
        "typedef unsigned char u8; typedef int sb32; struct SCStaffrollName; typedef struct SCStaffrollName SCStaffrollName;\n"
        + declaration(sc, "struct SCStaffrollMatrix")
        + "\n"
        + declaration(sc, "struct SCStaffrollName")
        + "\n#define SC_PUN(a, b) ((u32)&((SCStaffrollMatrix*)0)->a == (u32)&((SCStaffrollName*)0)->b)\n"
        + "typedef char checkStaffrollPun[(SC_PUN(unk_gmcreditsmtx_0xC, offset_x)"
        + " && SC_PUN(unk_gmcreditsmtx_0x14, interpolation))?1:-1];\n"
    )
    source += """
extern "C" {
u32 it_layout[] = {sizeof(ITAttackEvent),sizeof(ITMonsterEvent),(u32)&((ITMonsterEvent*)0)->knockback_scale};
ITAttackEvent it_event = {4,361,30,300};
u32 endian_flags[] = {SMASH360_HOST_BIG_ENDIAN,IS_BIG_ENDIAN};
s32 signcheck[] = {BITFIELD_SEXT8(-1),BITFIELD_SEXT8(255),BITFIELD_SEXT10(-512),BITFIELD_SEXT10(512)};
u32 wp_size = sizeof(WPAttributes);
u32 wpScale(WPAttributes *p) { return p->knockback_scale; }
u32 wpDamage(WPAttributes *p) { return p->damage; }
s32 wpAngle(WPAttributes *p) { return ((s16)p->_angle_raw) >> 6; }
u32 sizes[] = {sizeof(AObjEvent16),sizeof(AObjEvent32),sizeof(FTKeyEvent),sizeof(FTMotionEventMakeAttack1),sizeof(void*)};
du du_one = DU_INIT(0x3ff00000,0x00000000); double native_one = 1.0;
FTMotionEventMakeAttack1 attack = {1,2,3,4,5,1,6};
u32 probe32(AObjEvent32 *p) { return p->command.opcode; }
u32 probe16(AObjEvent16 *p) { return p->command.opcode; }
u32 probeKey(FTKeyEvent *p) { return p->command.opcode; }
float probeFloat() { unsigned char b[4]={0x42,0xc8,0,0}; float f; smash360CopyBEFloatBytes(&f,b); return f; }
}
"""
    cpp = OUT / "layout-xdk.cpp"
    cpp.write_text(source)
    obj = OUT / "layout-xdk.obj"
    asm = OUT / "layout-xdk.asm"
    xdk = Path("C:/Program Files (x86)/Microsoft Xbox 360 SDK")
    command = [
        str(xdk / "bin/win32/cl.exe"),
        "/nologo",
        "/c",
        "/TP",
        "/O2",
        "/DPORT",
        "/D_XBOX",
        "/FAs",
        f"/I{OVERLAY}",
        f"/I{OVERLAY}/decomp/include",
        f"/Fo{obj}",
        f"/Fa{asm}",
        str(cpp),
    ]
    compile = subprocess.run(command, capture_output=True, text=True)
    (OUT / "layout-xdk.log").write_text(compile.stdout + compile.stderr)
    if compile.returncode:
        print(compile.stdout + compile.stderr)
        return 1
    assert symbol_bytes(obj, "endian_flags", 8) == bytes.fromhex("0000000100000001")
    assert symbol_bytes(obj, "signcheck", 16) == bytes.fromhex("fffffffffffffffffffffe00fffffe00")
    assert symbol_bytes(obj, "wp_size", 4) == bytes.fromhex("00000034")
    assert symbol_bytes(obj, "sizes", 20) == bytes.fromhex("0000000200000004000000020000000400000004")
    assert symbol_bytes(obj, "attack", 4) == bytes.fromhex("053080b6")
    # Explosion events are 8 bytes in ROM: timer:8 angle:10 damage:8, then size in the next high half.
    assert symbol_bytes(obj, "it_layout", 12) == bytes.fromhex("000000080000002400000008")
    assert symbol_bytes(obj, "it_event", 8) == bytes.fromhex("045a4780012c0000")
    assert symbol_bytes(obj, "du_one", 8) == bytes.fromhex("3ff0000000000000")
    assert symbol_bytes(obj, "du_one", 8) == symbol_bytes(obj, "native_one", 8)
    assembly = asm.read_text()

    def body(name):
        match = re.search(r"^" + name + r"\s+PROC\b(.*?)^" + name + r"\s+ENDP", assembly, re.M | re.S)
        assert match, name
        return match[1]

    for name, shift in [("probe32", 25), ("probe16", 11), ("probeKey", 12)]:
        assert re.search(r"\bsrwi\s+r3,r\d+," + str(shift) + r"\b", body(name)), name
    assert re.search(r"\blwz\s+r11,28h\(r3\)", body("wpScale"))
    assert re.search(r"\bsrwi\s+r3,r11,22\b", body("wpScale"))
    assert re.search(r"\blwz\s+r11,28h\(r3\)", body("wpDamage"))
    assert re.search(r"\brlwinm\s+r3,r11,18,24,31\b", body("wpDamage"))
    assert re.search(r"\blhz\s+r11,26h\(r3\)", body("wpAngle"))
    assert re.search(r"\bsrawi\s+r3,r10,6\b", body("wpAngle"))
    print(
        "PASS XDK actual generated endian config, native DU_INIT bytes, representative bitfield object layout. Object evidence only."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
