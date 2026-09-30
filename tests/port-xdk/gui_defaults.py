"""Compare actual original/projected GUI record initialization on Win32 ILP32."""

from pathlib import Path
import hashlib, json, re, runpy, subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "scratch/port-xdk/gui-tests"
LOWER = runpy.run_path(str(ROOT / "platform/xbox360/cpp-compat/port/gui_lowering.py"))


def extract(path):
    text = path.read_text(encoding="utf-8-sig")
    text = re.sub(r"^#line[^\n]*\n", "", text, flags=re.M)
    raw = text.encode()
    nodes = []
    for node in LOWER["walk"](LOWER["PARSER"].parse(raw).root_node):
        if node.type == "enum_specifier" and LOWER["tx"](LOWER["field"](node, "name")) in LOWER["ENUMS"]:
            nodes.append((node.start_byte, LOWER["tx"](node) + ";"))
        if node.type == "namespace_definition" and LOWER["tx"](LOWER["field"](node, "name")) == "Sizes":
            nodes.append((node.start_byte, LOWER["tx"](node)))
        if node.type == "struct_specifier" and LOWER["tx"](LOWER["field"](node, "name")) in LOWER["OPTIONS"]:
            nodes.append((node.start_byte, LOWER["tx"](node) + ";"))
    return "namespace UIWidgets {\n" + "\n".join(t for _, t in sorted(nodes)) + "\n}\n"


def program(path, projected):
    helper = (
        (ROOT / "platform/xbox360/cpp-compat/port/gui_includes.h").read_text().split("namespace Smash360Port {", 1)[1]
    )
    prefix = (
        """\
#include <cstdio>
#include <map>
#include <string>
#include <utility>
#include <imgui.h>
#include <libultraship/libultra/types.h>
#include <ship/utils/color.h>
namespace Smash360Port {"""
        + helper
        + "\n"
    )
    main = ['int main() { static_assert(sizeof(void*)==4,"ILP32");']
    for mode in ("value", "default"):
        for name in LOWER["OPTIONS"]:
            init = (" = UIWidgets::" + name + "::Smash360Value()" if projected else "{}") if mode == "value" else ""
            main.append("{ UIWidgets::" + name + " v" + init + ";")
            members = LOWER["SCHEMA"][name] + (LOWER["SCHEMA"]["WidgetOptions"] if name != "WidgetOptions" else [])
            for member in members:
                if mode == "default" and member["default"] is None:
                    continue
                typ = member["type"]
                field = "v." + member["name"]
                label = mode + "/" + name + "/" + member["name"] + "="
                if typ.rstrip().endswith("*"):
                    expr = 'printf("' + label + '%s\\n", ' + field + " ? " + field + ' : "(null)");'
                elif typ == "ImVec2":
                    expr = 'printf("' + label + '%.9g,%.9g\\n", double(' + field + ".x), double(" + field + ".y));"
                elif typ == "Color_RGBA8":
                    expr = (
                        'printf("'
                        + label
                        + '%u,%u,%u,%u\\n", '
                        + ",".join("unsigned(" + field + "." + c + ")" for c in "rgba")
                        + ");"
                    )
                elif typ.startswith("std::map"):
                    expr = 'printf("' + label + '%u\\n", unsigned(' + field + ".size()));"
                elif typ == "std::string":
                    expr = 'printf("' + label + '%s\\n", ' + field + ".c_str());"
                else:
                    expr = 'printf("' + label + '%.17g\\n", double(' + field + "));"
                main.append(expr)
            main.append("}")
    main += ["return 0;", "}"]
    return prefix + extract(path) + "\n" + "\n".join(main) + "\n"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    paths = {
        "original": ROOT / "upstream/BattleShip/port/gui/UIWidgets.hpp",
        "projected": ROOT / "scratch/port-xdk/composed-overlay/port/gui/UIWidgets.hpp",
    }
    outputs = {}
    for name, path in paths.items():
        source = OUT / (name + ".cpp")
        source.write_text(program(path, name == "projected"))
        batch = OUT / (name + ".cmd")
        includes = [
            ROOT / "scratch/imgui-xdk/source",
            ROOT / "platform/xbox360/imgui",
            ROOT / "upstream/BattleShip/libultraship/include",
        ]
        command = (
            "cl /nologo /std:c++20 /EHsc /MT /D_CRT_SECURE_NO_WARNINGS "
            + " ".join('/I"' + str(p) + '"' for p in includes)
            + " /Fe:"
            + name
            + '.exe "'
            + str(source)
            + '"'
        )
        batch.write_text(
            '@echo off\ncall "C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Auxiliary/Build/vcvars32.bat" >nul\n'
            + command
            + "\n"
        )
        result = subprocess.run(["cmd.exe", "/d", "/c", str(batch)], cwd=OUT, capture_output=True)
        (OUT / (name + "-build.log")).write_bytes(result.stdout + result.stderr)
        assert result.returncode == 0, (result.stdout + result.stderr).decode(errors="replace")
        result = subprocess.run([str(OUT / (name + ".exe"))], cwd=OUT, capture_output=True)
        assert result.returncode == 0
        outputs[name] = result.stdout
        (OUT / (name + ".values")).write_bytes(result.stdout)
    assert outputs["original"] == outputs["projected"], "GUI default/value initialization differs"
    report = {
        "actual_record_types": len(LOWER["OPTIONS"]),
        "compared_fields": outputs["original"].count(b"="),
        "host_win32_ilp32": True,
        "target_runtime": False,
        "input_sha256": {k: hashlib.sha256(p.read_bytes()).hexdigest() for k, p in paths.items()},
    }
    (OUT / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
