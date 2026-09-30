"""Meaningful compile-time compatibility and source-selection verification.

Creates host executables and XDK objects in scratch/game-xdk/verification only;
never creates an XEX. The host fixture verifies donor declaration lowering.
"""

from pathlib import Path
import json
import os
import re
import subprocess
import struct
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
from game_source_manifest import manifest, UPSTREAM, sha256
from prepare_game_xdk import PLATFORM_BASE, float_max_spelling, prepare_gbi_header

sys.path.insert(0, str(Path(__file__).resolve().parent))
from typed_generic import lower_port_generics, lower_rumble_initializers
from source_tree import stage_sources

OUT = ROOT / "scratch/game-xdk/verification"
OUT.mkdir(parents=True, exist_ok=True)
COMPAT = Path(__file__).resolve().parent


def run(command, **kwargs):
    return subprocess.run(command, capture_output=True, **kwargs)


def symbol_data(coff, requested, size):
    _, section_count, _, symbols, symbol_count, optional, _ = struct.unpack_from("<HHIIIHH", coff)
    strings = symbols + symbol_count * 18
    index = 0
    while index < symbol_count:
        offset = symbols + index * 18
        name = coff[offset : offset + 8]
        if name[:4] == b"\0" * 4:
            start = strings + struct.unpack_from("<I", name, 4)[0]
            name = coff[start : coff.index(b"\0", start)]
        name = name.rstrip(b"\0").decode()
        if name.lstrip("_") == requested:
            value, section = struct.unpack_from("<Ih", coff, offset + 8)
            assert 0 < section <= section_count
            header = 20 + optional + (section - 1) * 40
            raw = struct.unpack_from("<I", coff, header + 20)[0]
            return coff[raw + value : raw + value + size]
        index += 1 + coff[offset + 17]
    raise AssertionError("COFF symbol missing: " + requested)


def main():
    text = (UPSTREAM / "CMakeLists.txt").read_text(encoding="utf-8")
    # Evaluate audited CMake source statements with CMake itself, independently
    # of Python's glob and source-list parser.
    commands = re.findall(r"file\(GLOB_RECURSE SSB64_SRC_(?!PORT)[^\n]+\)", text)
    for variable in ("SSB64_DECOMP_SOURCES", "SSB64_LIBULTRA_PORT", "SSB64_NAUDIO_PORT"):
        commands += [re.search(r"set\(" + variable + r"\s+.*?\n\)", text, re.S)[0]]
    commands += [re.search(r"file\(GLOB SSB64_STUBS[^\n]+\)", text)[0]]
    commands += [re.search(r"file\(GLOB SSB64_DEBUG_TOOLS\s+.*?\n\)", text, re.S)[0]]
    commands += ['list(FILTER SSB64_DECOMP_SOURCES EXCLUDE REGEX "\\.inc\\.c$")']
    commands += ['file(GLOB_RECURSE PORT_C "port/*.c")', 'list(FILTER PORT_C EXCLUDE REGEX "port/stubs/")']
    commands += [
        "set(ALL_C ${SSB64_DECOMP_SOURCES} ${SSB64_LIBULTRA_PORT} "
        "${SSB64_NAUDIO_PORT} ${SSB64_STUBS} ${SSB64_DEBUG_TOOLS} ${PORT_C})",
        'list(FILTER ALL_C INCLUDE REGEX "\\.c$")',
        "list(SORT ALL_C)",
        'string(REPLACE ";" "\\n" ALL_C "${ALL_C}")',
        'file(WRITE "' + (OUT / "cmake-sources.txt").as_posix() + '" "${ALL_C}\\n")',
    ]
    script = OUT / "source-selection.cmake"
    script.write_text(
        "cmake_minimum_required(VERSION 3.20)\n"
        + 'set(CMAKE_CURRENT_SOURCE_DIR "'
        + UPSTREAM.as_posix()
        + '")\n'
        + "\n".join(commands)
        + "\n"
    )
    result = run(["cmake", "-P", str(script)], cwd=UPSTREAM)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    cmake_set = set()
    for item in (OUT / "cmake-sources.txt").read_text().splitlines():
        cmake_set.add(Path(item).relative_to(UPSTREAM).as_posix() if Path(item).is_absolute() else item)
    expected = {source["path"] for source in manifest()["sources"]}
    assert cmake_set == expected, (cmake_set - expected, expected - cmake_set)

    xdk = Path(os.environ.get("XEDK", r"C:\Program Files (x86)\Microsoft Xbox 360 SDK"))
    compiler = xdk / "bin/win32/cl.exe"
    common = [str(compiler), "/nologo", "/TC", "/MT", "/c", "/D_XBOX", "/FI" + str(COMPAT / "compiler_compat.h")]
    mirror_original = OUT / "mirror-original"
    mirror_overlay = OUT / "mirror-overlay"
    mirror_output = OUT / "mirror-output"
    for directory in (mirror_original, mirror_overlay):
        (directory / "port").mkdir(parents=True, exist_ok=True)
    (mirror_original / "port/settings.h").write_text("#define QUOTED_SETTING 1\n")
    (mirror_original / "port/api.h").write_text('#include "settings.h"\n')
    (mirror_original / "port/test.c").write_text(
        '#include "api.h"\n_Static_assert(QUOTED_SETTING == 2, "overlay must win");\n'
    )
    (mirror_overlay / "port/settings.h").write_text("#define QUOTED_SETTING 2\n")
    before_hash = sha256(mirror_original / "port/settings.h")
    # Sparse -I cannot override a quoted sibling. Observe failure first.
    result = run(
        common
        + [
            "/I" + str(mirror_overlay / "port"),
            "/Fo" + str(OUT / "sparse-quote.obj"),
            str(mirror_original / "port/test.c"),
        ]
    )
    assert result.returncode != 0 and b"C2118" in result.stdout + result.stderr
    stage_sources(mirror_original, mirror_output, ["port/test.c"], [mirror_overlay])
    result = run(common + ["/Fo" + str(OUT / "mirrored-quote.obj"), str(mirror_output / "port/test.c")])
    assert result.returncode == 0, (result.stdout + result.stderr).decode(errors="replace")
    assert sha256(mirror_original / "port/settings.h") == before_hash
    (mirror_original / "port/once.h").write_text(
        "/* actual initial comment */\n#pragma once\nstruct OnceOnly { int value; };\n"
    )
    (mirror_original / "port/fragment.txt").write_text("int included_fragment;\n")
    (mirror_original / "port/once.c").write_text('#include "once.h"\n#include "once.h"\n#include <fragment.txt>\n')
    stage_sources(mirror_original, mirror_output, ["port/once.c"])
    assert (mirror_output / "port/fragment.txt").is_file()
    result = run(
        [str(compiler), "/nologo", "/TC", "/E", "/I" + str(mirror_output / "port"), str(mirror_output / "port/once.c")]
    )
    assert result.returncode == 0
    assert result.stdout.count(b"struct OnceOnly") == 1
    (OUT / "once-preprocessed.c").write_bytes(result.stdout)
    result = run(common + ["/Fo" + str(OUT / "once.obj"), str(OUT / "once-preprocessed.c")])
    assert result.returncode == 0, (result.stdout + result.stderr).decode(errors="replace")
    positive = OUT / "assert-positive.c"
    positive.write_text(
        '_Static_assert(sizeof(void*) == 4, "ILP32 pointer");\n'
        '_Static_assert(sizeof(long) == 4, "ILP32 long");\n'
        '_Static_assert(sizeof(int) == 4, "ILP32 int");\n'
        '_Static_assert(sizeof(long long) == 8, "64-bit integer");\n'
        "static inline int twice(int x) { return x * 2; }\n"
        "int check(void) { return twice(3); }\n"
    )
    result = run(common + ["/Fo" + str(OUT / "assert-positive.obj"), str(positive)])
    (OUT / "assert-positive.log").write_bytes(result.stdout + result.stderr)
    assert result.returncode == 0, result.stdout.decode(errors="replace")
    negative = OUT / "assert-negative.c"
    negative.write_text('_Static_assert(sizeof(void*) == 8, "intentional false width");\n')
    result = run(common + ["/Fo" + str(OUT / "assert-negative.obj"), str(negative)])
    (OUT / "assert-negative.log").write_bytes(result.stdout + result.stderr)
    assert result.returncode != 0 and b"C2118" in result.stdout + result.stderr, "False assertion was not enforced"

    spelling_input = b'float x = 3.40282346639e+38F; const char *s = "3.40282346639e+38F";\n'
    spelling_output, changes = float_max_spelling(spelling_input)
    assert changes == 1 and b'"3.40282346639e+38F"' in spelling_output
    assert spelling_output.count(b"\n") == spelling_input.count(b"\n")
    maxima = OUT / "float-max.c"
    maxima.write_text("float maxima[2] = {3.402823466e+38F, -3.402823466e+38F};\n")
    max_object = OUT / "float-max.obj"
    result = run(common + ["/Fo" + str(max_object), str(maxima)])
    assert result.returncode == 0, (result.stdout + result.stderr).decode(errors="replace")
    coff = max_object.read_bytes()
    machine, sections = struct.unpack_from("<HH", coff)
    assert machine == 0x1F2, "Expected Xbox PowerPC COFF"
    data_sections = []
    for index in range(sections):
        offset = 20 + index * 40
        name, _, _, size, raw = struct.unpack_from("<8sIIII", coff, offset)
        if name.rstrip(b"\0") == b".data":
            data_sections.append(coff[raw : raw + size])
    assert any(
        section[:8] == bytes.fromhex("7f7fffffff7fffff") for section in data_sections
    ), "XDK float data bytes differ"

    sys.path.insert(0, str(ROOT / "scratch/host-python"))
    from xbox360_platform import c89_lower

    # Scope shadowing, evaluation order, continue/break, nested loops, and jumps
    # past a declaration with a side effect are checked against the C11 original.
    fixture = b"""static int effects;
static int step(int n) { effects++; return n; }
static int calculate(void) {
    int total = 0;
    for (int i = step(0); i < 7; ++i) {
        total += i;
        int late = step(i * 3);
        if (i == 2) continue;
        for (int j = step(0); j < 3; ++j) {
            total += late + j;
            if (j == 1) break;
        }
        if (i == 4) break;
    }
    { total += 1; int total = step(7); effects += total; }
    goto done;
    int skipped = step(99);
    total += skipped;
done:
    return total * 100 + effects;
}
int main(void) {
    union { float f; unsigned int u; } a, b;
    a.f = 3.40282346639e+38F;
    b.f = 3.402823466e+38F;
    return calculate() == 6318 && a.u == 0x7f7fffffU && b.u == a.u ? 0 : 1;
}
"""
    # Derive no expected value from the transformer: original and lowered both
    # execute a fixed hand-calculated result (63, 18 side-effect units).
    original = OUT / "lower-original.c"
    lowered = OUT / "lower-converted.c"
    original.write_bytes(fixture)
    converted, changes = c89_lower.lower(fixture)
    assert changes >= 4
    lowered.write_bytes(converted)
    vcvars = Path(
        os.environ.get(
            "SMASH_HOST_VCVARS",
            r"C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat",
        )
    )
    assert vcvars.is_file(), "Set SMASH_HOST_VCVARS to the host VS vcvars64.bat"
    generic_original = OUT / "generic-original.c"
    generic_lowered = OUT / "generic-converted.c"
    # Use XDK's /E output to exercise the same declaration/type universe as the
    # production driver, then remove only the verified generic selections.
    generic_fixture = COMPAT / "generic_fixture.c"
    preprocessed = run(
        [
            str(compiler),
            "/nologo",
            "/TC",
            "/E",
            "/D_XBOX",
            "/FI" + str(COMPAT / "compiler_compat.h"),
            str(generic_fixture),
        ]
    )
    assert preprocessed.returncode == 0
    generic_original.write_bytes(preprocessed.stdout)
    generic_code, selected, unknown = lower_port_generics(preprocessed.stdout, c89_lower.PARSER)
    assert len(selected) == 11 and not unknown, (selected, unknown)
    assert [item["helper"] for item in selected].count("portRefGfxToken") == 6
    assert [item["helper"] for item in selected].count("portRefDObjDLLinkToken") == 1
    assert generic_code.count(b"\n") == preprocessed.stdout.count(b"\n")
    generic_lowered.write_bytes(generic_code)
    result = run(common + ["/Fo" + str(OUT / "generic-converted.obj"), str(generic_lowered)])
    (OUT / "generic-xdk.log").write_bytes(result.stdout + result.stderr)
    assert result.returncode == 0, (result.stdout + result.stderr).decode(errors="replace")
    # Unknown expression types must remain visible, never select the scalar
    # helper as a guess. The fixture lacks a declaration for missing().
    unknown_code = preprocessed.stdout.replace(b"next_gfx()", b"missing()")
    _, _, unknown = lower_port_generics(unknown_code, c89_lower.PARSER)
    assert unknown, "Unproven expression was silently assigned a helper"
    gbi_header = prepare_gbi_header(ROOT / "scratch/game-xdk")
    gbi_flags = [
        "/DPORT=1",
        "/D_LANGUAGE_C",
        "/DF3DEX_GBI_2=1",
        "/I" + str(gbi_header.parents[1]),
        "/I" + str(UPSTREAM / "decomp/include"),
        "/I" + str(xdk / "include/xbox"),
    ]
    gbi_obj = OUT / "gbi-xdk.obj"
    result = run(common + gbi_flags + ["/Fo" + str(gbi_obj), str(COMPAT / "gbi_fixture.c")])
    (OUT / "gbi-xdk.log").write_bytes(result.stdout + result.stderr)
    assert result.returncode == 0, (result.stdout + result.stderr).decode(errors="replace")
    coff = gbi_obj.read_bytes()
    assert symbol_data(coff, "mode_words", 32) == symbol_data(coff, "explicit_words", 32)
    # Independently encoded RDP rectangle plus its two continuation packets.
    # Comparing both generated arrays alone missed identical bad Gfx strides.
    assert symbol_data(coff, "rectangle_words", 24).hex() == ("e40780a000028050e100000000200040f100000004000800")
    # Host executes both the original conforming macro and donor rescan macro;
    # it verifies runtime pkt++ evaluation and both command words as well.
    gbi_original = OUT / "gbi-original.c"
    gbi_modified = OUT / "gbi-modified.c"
    gbi_original.write_bytes((COMPAT / "gbi_fixture.c").read_bytes())
    gbi_modified.write_bytes((COMPAT / "gbi_fixture.c").read_bytes())
    rumble_sources = []
    for name, declaration, expected_bytes in (
        ("opcode-first", "u16 opcode:3; u16 param:13;", "7f40a002"),
        ("param-first", "u16 param:13; u16 opcode:3;", "fa030015"),
    ):
        fixture = (
            "typedef unsigned short u16;\n"
            "typedef struct GMRumbleEventDefault GMRumbleEventDefault;\n"
            "struct GMRumbleEventDefault {" + declaration + "};\n"
            "GMRumbleEventDefault rumble_rows[2] = {\n"
            "{.opcode=(3), .param=(8000)}, {.opcode=(5), .param=(2)} };\n"
            "int main(void) { return sizeof(rumble_rows)==4 && "
            "rumble_rows[0].opcode==3 && rumble_rows[0].param==8000 && "
            "rumble_rows[1].opcode==5 && rumble_rows[1].param==2 ? 0 : 1; }\n"
        ).encode()
        converted, stats = lower_rumble_initializers(fixture, c89_lower.PARSER)
        assert stats["rows"] == 2 and converted.count(b"\n") == fixture.count(b"\n")
        before, after = OUT / ("rumble-" + name + "-original.c"), OUT / ("rumble-" + name + "-converted.c")
        before.write_bytes(fixture)
        after.write_bytes(converted)
        obj = after.with_suffix(".obj")
        result = run(common + ["/Fo" + str(obj), str(after)])
        assert result.returncode == 0, (result.stdout + result.stderr).decode(errors="replace")
        assert symbol_data(obj.read_bytes(), "rumble_rows", 4).hex() == expected_bytes
        rumble_sources.extend([before, after])
    for source in (original, lowered, generic_original, generic_lowered, gbi_original, gbi_modified, *rumble_sources):
        exe = source.with_suffix(".exe")
        extra_flags = ""
        if source in (gbi_original, gbi_modified):
            extra_flags = " /Zc:preprocessor /DPORT=1 /D_LANGUAGE_C /DF3DEX_GBI_2=1"
            if source == gbi_modified:
                extra_flags += (
                    ' /D_XBOX /FI"' + str(COMPAT / "compiler_compat.h") + '" /I"' + str(gbi_header.parents[1]) + '"'
                )
            extra_flags += ' /I"' + str(UPSTREAM / "decomp/include") + '"'
        command = (
            'call "'
            + str(vcvars)
            + '" >nul && cl /nologo /TC /std:c11 /MT /Od'
            + extra_flags
            + ' /Fe:"'
            + str(exe)
            + '" /Fo:"'
            + str(source.with_suffix(".obj"))
            + '" "'
            + str(source)
            + '"'
        )
        batch = OUT / "build-host.cmd"
        batch.write_text("@echo off\n" + command + "\n")
        result = run(["cmd.exe", "/d", "/c", str(batch)], cwd=OUT)
        source.with_suffix(".log").write_bytes(result.stdout + result.stderr)
        assert result.returncode == 0, result.stdout.decode(errors="replace")
        result = run([str(exe)], cwd=OUT)
        assert result.returncode == 0, f"Control-flow fixture failed: {source.name}"
    report = {
        "source_selection_count": len(expected),
        "cmake_selection_equal": True,
        "positive_xdk_width_asserts": True,
        "negative_xdk_assert_rejected": True,
        "donor_lowering_host_control_flow": True,
        "lowering_changes": changes,
        "float_max_host_original_equals_xdk_spelling": True,
        "xdk_float_max_object_bytes": "7f7fffff ff7fffff",
        "typed_generic_host_and_xdk": True,
        "typed_generic_unknown_type_left_unresolved": True,
        "gbi_original_and_rescan_host_execution": True,
        "gbi_xdk_command_words_equal_explicit_lerp": True,
        "rumble_initializer_host_fields_and_xdk_bitfield_bytes": True,
        "quoted_sibling_overlay_native_compiler": True,
        "pragma_once_preprocessing_and_nonheader_include_closure": True,
        "compiler_compat_sha256": sha256(COMPAT / "compiler_compat.h"),
        "lowering_source": str((PLATFORM_BASE / "python/xbox360_platform/c89_lower.py").resolve()),
        "lowering_sha256": sha256(PLATFORM_BASE / "python/xbox360_platform/c89_lower.py"),
    }
    (OUT / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
