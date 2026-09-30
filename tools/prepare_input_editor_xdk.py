"""Pinned real InputEditorWindow source and platform capability projection."""

from pathlib import Path
import argparse, hashlib, json, re, runpy, subprocess, sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
import runpy as _shipyard_runpy

SHIPYARD_BASE = _shipyard_runpy.run_path(str(ROOT / "tools/platform_base.py"))["resolve"](ROOT)
UP = ROOT / "upstream/BattleShip"
LUS = UP / "libultraship"
BASE = ROOT / "platform/xbox360/cpp-compat/input-editor"
OUT = ROOT / "scratch/input-editor-xdk"
PRISM = runpy.run_path(str(ROOT / "tools/prepare_prism_xdk.py"))
LOWER = runpy.run_path(str(ROOT / "platform/xbox360/cpp-compat/controllers/lowering.py"))
STAGE = runpy.run_path(str(ROOT / "platform/xbox360/game-compat/source_tree.py"))["stage_sources"]


def once(t, a, b):
    if t.count(a) != 1:
        raise ValueError("Input editor anchor drift: " + a[:90])
    return t.replace(a, b)


def transform(relative, t):
    if relative.endswith(".h"):
        constructors = "    InputEditorWindow() : GuiWindow() {}\n"
        for args, call in [
            ("const std::string& c,bool v,const std::string& n,ImVec2 s,uint32_t f", "c,v,n,s,f"),
            ("const std::string& c,bool v,const std::string& n,ImVec2 s", "c,v,n,s"),
            ("const std::string& c,bool v,const std::string& n", "c,v,n"),
            ("const std::string& c,const std::string& n,ImVec2 s,uint32_t f", "c,n,s,f"),
            ("const std::string& c,const std::string& n,ImVec2 s", "c,n,s"),
            ("const std::string& c,const std::string& n", "c,n"),
        ]:
            constructors += "    InputEditorWindow(" + args + ") : GuiWindow(" + call + ") {}\n"
        t = once(t, "    using GuiWindow::GuiWindow;", constructors)
    else:
        inc = '#include "ship/controller/raphnet/RaphnetPhysicalDeviceManager.h"'
        t = once(t, inc, "#if !defined(_XBOX)\n" + inc + "\n#endif")
        start = t.index("        // Native Raphnet ports")
        end = t.index("        DrawClearAllButton(portIndex);", start)
        t = t[:start] + "#if !defined(_XBOX)\n" + t[start:end] + "#endif\n" + t[end:]
        for variable in ("mButtonsBitmasks", "mDpadBitmasks"):
            pattern = r"    " + variable + r" = \{ ([^}]+) \};"
            matches = list(re.finditer(pattern, t))
            if len(matches) != 1:
                raise ValueError("Expected bitmask set initializer")
            m = matches[0]
            items = m[1].split(", ")
            replacement = (
                "    "
                + variable
                + ".clear();\n"
                + "".join("    " + variable + ".insert(" + v + ");\n" for v in items)
            )
            t = t[: m.start()] + replacement + t[m.end() :]
        start = t.index("    for (auto stick :\n")
        end = t.index("        for (auto direction : { LEFT, RIGHT, UP, DOWN }) {", start)
        t = (
            t[:start]
            + (
                '    const std::pair<uint8_t,std::shared_ptr<ControllerStick> > sticks[] = {\n'
                '        std::pair<uint8_t,std::shared_ptr<ControllerStick> >(LEFT,Context::GetIn'
                'stance()->GetControlDeck()->GetControllerByPort(port)->GetLeftStick()),\n'
                '        std::pair<uint8_t,std::shared_ptr<ControllerStick> >(RIGHT,Context::GetI'
                'nstance()->GetControlDeck()->GetControllerByPort(port)->GetRightStick()) };\n'
                '    const Direction directions[] = { LEFT, RIGHT, UP, DOWN };\n'
                '    for (auto stick : sticks) {\n'
            )
            + t[end:]
        )
        t = once(
            t,
            "for (auto direction : { LEFT, RIGHT, UP, DOWN })",
            "for (auto direction : directions)",
        )
        t = once(
            t,
            "[](const auto& a, const auto& b)",
            "[](const std::pair<int32_t,std::string>& a, const std::pair<int32_t,std::string>& b)",
        )
        t = once(
            t,
            "ImVec4 color = { mapping->GetSavedColor().r / 255.0f, mapping->GetSavedColor().g /"
            " 255.0f,\n                                 mapping->GetSavedColor().b / 255.0f,"
            " 1.0f };",
            "ImVec4 color(mapping->GetSavedColor().r / 255.0f, mapping->GetSavedColor().g /"
            " 255.0f,\n                                 mapping->GetSavedColor().b / 255.0f,"
            " 1.0f);",
        )
        t = once(
            t,
            "mapping->SetSavedColor(\n                        Color_RGB8({"
            " static_cast<uint8_t>(color.x * 255.0), static_cast<uint8_t>(color.y * 255.0),\n      "
            "                               static_cast<uint8_t>(color.z * 255.0) }));",
            "Color_RGB8 savedColor = { static_cast<uint8_t>(color.x * 255.0),"
            " static_cast<uint8_t>(color.y * 255.0),\n                                    "
            " static_cast<uint8_t>(color.z * 255.0) };\n                   "
            " mapping->SetSavedColor(savedColor);",
        )
        # With no native mouse, use the existing ImGui automatic popup placement.
        # Explicit desktop mouse position would be invalid during gamepad-only UI.
        start = t.index("    const float HORIZONTAL_OFFSET = 10.0f;")
        end = t.index("\n}", start)
        t = t[:start] + "#if !defined(_XBOX)\n" + t[start:end] + "\n#endif" + t[end:]
        for section, message in [
            ("Gyro", "Xbox 360 gamepads do not provide gyroscope input."),
            ("LEDs", "Xbox 360 gamepads do not provide programmable LED colors."),
        ]:
            anchor = '        if (ImGui::CollapsingHeader("' + section + '")) {'
            t = once(
                t,
                anchor,
                anchor
                + '\n#ifdef _XBOX\n            ImGui::TextUnformatted("'
                + message
                + '");\n#endif',
            )
    t = LOWER["syntax"](t, {"PhysicalDeviceType"})
    return '#include "controllers/compiler.h"\n#include <spdlog/spdlog.h>\n' + t


def prepare():
    locks = json.loads((BASE / "source-lock.json").read_text())
    records = []
    for rel, sha in locks.items():
        original = LUS / rel
        if hashlib.sha256(original.read_bytes()).hexdigest() != sha:
            raise ValueError("Input editor source drift " + rel)
        text = transform(rel, original.read_text(encoding="utf-8-sig"))
        target = OUT / "overlay/libultraship" / rel
        PRISM["mapped"](original.as_posix(), text, target)
        records.append(
            {
                "source": "libultraship/" + rel,
                "sha256": sha,
                "generated_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            }
        )
    # Compose the authoritative header owners into one compiler mirror so quoted
    # sibling includes cannot bypass the generated controller/gui declarations.
    layers = [
        ("scratch/gui-xdk/compile-tree", ""),
        ("scratch/gui-widgets-xdk/generated/include", "libultraship/include"),
        ("scratch/controllers-xdk/generated/include", "libultraship/include"),
        ("scratch/gui-xdk/overlay", ""),
        ("scratch/input-editor-xdk/overlay", ""),
    ]
    headers = {}
    support = []
    for name, prefix in layers:
        directory = ROOT / name
        for path in directory.rglob("*.h"):
            rel = (Path(prefix) / path.relative_to(directory)).as_posix()
            headers[rel] = path
    for rel, path in headers.items():
        target = OUT / "composed" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
        support.append(
            {
                "path": str(path.relative_to(ROOT)),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    source = "libultraship/src/ship/window/gui/InputEditorWindow.cpp"
    target = OUT / "composed" / source
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes((OUT / "overlay" / source).read_bytes())
    staged = STAGE(UP, OUT / "compile-tree", [source], [OUT / "composed"])
    (OUT / "manifest.json").write_text(
        json.dumps({"transforms": records, "support": support, "staged": staged}, indent=2) + "\n"
    )


def compile_xdk():
    sdk = Path("C:/Program Files (x86)/Microsoft Xbox 360 SDK")
    tree = OUT / "compile-tree"
    includes = [
        tree / "libultraship/include",
        tree / "libultraship/src",
        tree / "include",
        ROOT / "platform/xbox360/cpp-compat",
        SHIPYARD_BASE / 'sources',
        SHIPYARD_BASE / 'sources/json/include',
        SHIPYARD_BASE / 'sources/value_types',
        ROOT / "scratch/thread-pool-xdk",
        ROOT / "platform/xbox360/cpp-compat/thread-pool",
        ROOT / "platform/xbox360/cpp-compat/async",
        SHIPYARD_BASE,
        SHIPYARD_BASE / 'sources',
        ROOT / "scratch/logging-xdk/core-include",
        ROOT / "scratch/logging-xdk/include",
        ROOT / "upstream/dependencies/fmt-xdk",
        ROOT / "scratch/imgui-xdk/source",
        ROOT / "platform/xbox360/imgui",
        ROOT / "platform/xbox360/input",
        ROOT / "upstream/dependencies/stb",
        sdk / "include/xbox",
    ]
    cmd = (
        [
            str(sdk / "bin/win32/cl.exe"),
            "/nologo",
            "/c",
            "/TP",
            "/EHsc",
            "/MT",
            "/W3",
            "/D_XBOX",
            "/DNOMINMAX",
            "/DDISABLE_SCRIPTING",
            "/FI" + str(ROOT / "scratch/config-xdk/cvars.h"),
        ]
        + ["/I" + str(p) for p in includes]
        + [
            "/Fo" + str(OUT / "InputEditorWindow.obj"),
            str(tree / "libultraship/src/ship/window/gui/InputEditorWindow.cpp"),
        ]
    )
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    log = result.stdout + result.stderr
    (OUT / "compile.log").write_text(log)
    (OUT / "compile-report.json").write_text(
        json.dumps({"command": cmd, "exit": result.returncode}, indent=2) + "\n"
    )
    print("\n".join(line for line in log.splitlines() if "error " in line)[:9000])
    return result.returncode


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--compile", action="store_true")
    a = p.parse_args()
    prepare()
    if a.compile:
        raise SystemExit(compile_xdk())
