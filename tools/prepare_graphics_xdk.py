"""Prepare pinned Fast3D interfaces and compile the physical Shipyard Xenos sources."""

from pathlib import Path
import argparse
import difflib
import hashlib
import json
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parents[1]
from platform_base import resolve as resolve_platform_base

PLATFORM_BASE = resolve_platform_base(ROOT)
BASE = ROOT / "platform/xbox360/graphics"
UPSTREAM = ROOT / "upstream/BattleShip/libultraship"
OUT = ROOT / "scratch/graphics-xdk"


def check_bytes(data, expected, name):
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError("SHA-256 source drift: " + name)


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError("expected exactly one source anchor: " + old[:90])
    return text.replace(old, new, 1)


def mapped(path, text, line=1):
    path = path.replace("\\", "/")
    # Keep exact upstream line origins for unchanged lines. Adapted spans name
    # the generated file and their actual physical line; never attribute an
    # inserted block to a made-up upstream line number.
    source = ROOT / path
    original = source.read_text(encoding="utf-8-sig").splitlines(keepends=True)
    changed = text.splitlines(keepends=True)
    origins = {}
    for block in difflib.SequenceMatcher(
        None, original, changed, autojunk=False
    ).get_matching_blocks():
        for offset in range(block.size):
            origins[block.b + offset] = block.a + offset + 1
    generated_path = "scratch/graphics-xdk/" + (
        "include/" + path.split("/include/", 1)[1] if "/include/" in path else Path(path).name
    )
    if path.endswith("/perf_trace.h"):
        generated_path = "scratch/graphics-xdk/include/metrics.h"
    if path.endswith("/interpreter.h"):
        generated_path = "scratch/graphics-xdk/include/fast/cc_features.h"
    output = []
    guard = None
    if path.endswith(".h"):
        guard = "SMASH360_GENERATED_" + hashlib.sha256(path.encode()).hexdigest().upper()
        output = ["#ifndef " + guard + "\n", "#define " + guard + "\n"]
    block_comment = False
    quote = None
    continued = False
    depth = 0
    last_file = None
    last_line = 0
    for index, current in enumerate(changed):
        filename = path if index in origins else generated_path
        # Generated lines map to themselves: this line, or the one after a directive.
        number = origins.get(index, len(output) + 1)
        # No directive inside an open call; a macro's arguments cannot hold one.
        safe = not block_comment and quote is None and not continued and depth == 0
        if safe and (filename != last_file or number != last_line + 1):
            if index not in origins:
                number += 1
            output.append('#line %d "%s"\n' % (number, filename))
            last_file = filename
            last_line = number - 1
        output.append(current)
        last_line += 1
        cursor = 0
        while cursor < len(current):
            pair = current[cursor : cursor + 2]
            char = current[cursor]
            if block_comment:
                if pair == "*/":
                    block_comment = False
                    cursor += 2
                    continue
            elif quote:
                if char == "\\":
                    cursor += 2
                    continue
                if char == quote:
                    quote = None
            elif pair == "//":
                break
            elif pair == "/*":
                block_comment = True
                cursor += 2
                continue
            elif char in ('"', "'"):
                quote = char
            elif char == "(":
                depth += 1
            elif char == ")":
                depth = max(depth - 1, 0)
            cursor += 1
        continued = current.rstrip("\r\n").endswith("\\")
    result = "".join(output)
    if guard:
        result += "\n#endif\n"
    return result


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def modern_members(text, name):
    """Move only in-class data initializers into that type's constructor."""
    begin = (
        text.index("struct " + name + " {")
        if "struct " + name + " {" in text
        else text.index("class " + name + " {")
    )
    start = text.index("{", begin)
    depth = 1
    end = start + 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    body = text[start + 1 : end - 1]
    initializers = []

    def member(match):
        initializers.append((match[2], match[3]))
        return match[1] + match[2] + ";"

    body = re.sub(
        r"(?m)^(    (?:uint\w+|int\w*|bool|float|size_t|FilteringMode|PostProcess\w+|const struct"
        r" PostProcessExtraBinding\*)\s+)(\w+)\s*=\s*([^;\n]+);",
        member,
        body,
    )
    if initializers:
        ctor = (
            "\n  public:\n    "
            + name
            + "() : "
            + ", ".join(n + "(" + v.replace("nullptr", "NULL") + ")" for n, v in initializers)
            + " {}\n"
        )
        body = ctor + body
    return text[: start + 1] + body + text[end - 1 :]


def lower_api(text):
    text = replace_once(text, "#include <compare>", "#include <stddef.h>")
    text = text.replace(" noexcept", "")
    text = replace_once(
        text,
        "auto operator<=>(const ShaderProgramKey&) const = default;",
        """bool operator==(const ShaderProgramKey& k) const {
        return shaderId0==k.shaderId0 && shaderId1==k.shaderId1 && filteringMode==k.filteringMode && srgbMode==k.srgbMode;
    }
    bool operator<(const ShaderProgramKey& k) const {
        if(shaderId0!=k.shaderId0)return shaderId0<k.shaderId0;
        if(shaderId1!=k.shaderId1)return shaderId1<k.shaderId1;
        if(filteringMode!=k.filteringMode)return filteringMode<k.filteringMode;
        return srgbMode<k.srgbMode;
    }""",
    )
    text = text.replace(" = default;", " {}")
    text = text.replace("const auto hash", "const size_t hash")
    text = re.sub(r"(std::hash<[^>]+>)\{\}", r"\1()", text)
    for name in ("ShaderProgramKey", "GfxRenderingAPI"):
        text = modern_members(text, name)
    return text


def lower_post(text):
    def enum(match):
        name, body = match[1], match[2]
        return (
            "struct %s { enum Value {%s}; Value value; %s(Value v) : value(v) {} operator Value()"
            " const { return value; } };" % (name, body, name)
        )

    text = re.sub(r"enum class (\w+)\s*\{([^}]+)\};", enum, text)
    for name in re.findall(r"struct (\w+)\s*\{", text):
        text = modern_members(text, name)
    return text


def prepare():
    lock = json.loads((BASE / "source-lock.json").read_text(encoding="utf-8-sig"))
    for name, sha in lock["shared"].items():
        check_bytes((PLATFORM_BASE / name).read_bytes(), sha, name)
    platform_base = PLATFORM_BASE / "sources/xenos"
    upstream = {}
    for name, sha in lock["upstream"].items():
        data = (UPSTREAM / name).read_bytes()
        check_bytes(data, sha, name)
        upstream[name] = data.decode("utf-8-sig").replace("\r\n", "\n")
    api = "include/fast/backends/gfx_rendering_api.h"
    write(OUT / api, mapped("upstream/BattleShip/libultraship/" + api, lower_api(upstream[api])))
    window = "include/fast/backends/gfx_window_manager_api.h"
    win = modern_members(upstream[window].replace(" = default;", " {}"), "GfxWindowBackend")
    write(OUT / window, mapped("upstream/BattleShip/libultraship/" + window, win))
    for name in ("PostProcessTypes.h", "PostProcessPreset.h"):
        path = "include/fast/postprocess/" + name
        write(
            OUT / path,
            mapped("upstream/BattleShip/libultraship/" + path, lower_post(upstream[path])),
        )
    interp = upstream["include/fast/interpreter.h"]
    features = interp[
        interp.index("struct CCFeatures {") : interp.index("void gfx_cc_get_features")
    ]
    write(
        OUT / "include/fast/cc_features.h",
        mapped(
            "upstream/BattleShip/libultraship/include/fast/interpreter.h",
            "#pragma once\n#include <stdint.h>\n" + features,
            106,
        ),
    )
    # Exact project patch sets this ABI, no ImGui implementation substituted.
    patch = upstream["cmake/dependencies/patches/imgui-fixes-and-config.patch"]
    if "+#define ImTextureID void*" not in patch:
        raise ValueError("ImGui texture ABI drift")
    write(
        OUT / "include/imconfig.h",
        "#pragma once\n// Pinned imgui-fixes-and-config.patch:143\n#define ImTextureID void*\n",
    )
    write(
        OUT / "include/stdbool.h",
        "#pragma once\n#ifndef __cplusplus\n#define bool unsigned char\n#define true 1\n#define"
        " false 0\n#endif\n",
    )
    manifest = {
        "source_lock": lock,
        "outputs": {
            str(p.relative_to(OUT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in OUT.rglob("*")
            if p.is_file() and p.suffix in (".cpp", ".h")
        },
        "scope": (
            "Object compilation only; required platform and pinned-Prism symbols remain link"
            " dependencies."
        ),
    }
    write(OUT / "manifest.json", json.dumps(manifest, indent=2) + "\n")


def compile_xdk():
    xdk = Path("C:/Program Files (x86)/Microsoft Xbox 360 SDK")
    compiler = xdk / "bin/win32/cl.exe"
    flags = [
        str(compiler),
        "/nologo",
        "/TP",
        "/D_XBOX",
        "/D_WIN32",
        "/DNOMINMAX",
        "/EHsc",
        "/MT",
        "/W4",
        "/I" + str(xdk / "include/xbox"),
        "/I" + str(PLATFORM_BASE / "sources"),
        "/I" + str(PLATFORM_BASE / "sources/xenos"),
        "/I" + str(OUT / "include"),
        "/I" + str(BASE),
        "/I" + str(ROOT / "platform/xbox360"),
    ]
    from xbox360_platform import xenos_capabilities
    flags += xenos_capabilities.compiler_options(3, shader_pack=True)
    sources = [
        PLATFORM_BASE / "sources/xenos/core.cpp",
        BASE / "api.cpp",
        BASE / "shipyard_services.cpp",
        PLATFORM_BASE / "sources/xenos/shader_cache.cpp",
        PLATFORM_BASE / "sources/xenos/shader_pack_program.cpp",
        BASE / "shader_cache_adapter.cpp",
        PLATFORM_BASE / "sources/graphics/shader_lower.cpp",
        PLATFORM_BASE / "sources/presentation/xenos_surface.cpp",
        BASE / "window_xenos.cpp",
        ROOT / "tests/graphics/xdk_contract.cpp",
    ]
    ok = True
    for source in sources:
        obj = OUT / (source.stem + ".obj")
        result = subprocess.run(
            flags + ["/c", "/Fo" + str(obj), str(source)], capture_output=True, text=True
        )
        log = result.stdout + result.stderr
        write(OUT / (source.stem + ".log"), log)
        print(source.name + ": exit " + str(result.returncode))
        if result.returncode:
            print(log[-10000:])
            ok = False
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--compile", action="store_true")
    args = parser.parse_args()
    prepare()
    if args.compile:
        compile_xdk()
