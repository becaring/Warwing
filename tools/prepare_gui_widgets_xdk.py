"""Hash-locked LUS widget projection; no replacement GUI classes."""

from pathlib import Path
import argparse, hashlib, json, re, subprocess
from prepare_prism_xdk import mapped, once, enum_wrappers, lower_ranges, PARSER, walk, field, tx
from prepare_fast3d_xdk import remove_class_defaults, data_struct_constructors
from xbox360_platform.cpp_syntax import lower_if_initializers
from xbox360_platform import overlap_lus

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "platform/xbox360/cpp-compat/gui-widgets"
OUT = ROOT / "scratch/gui-widgets-xdk"
UP = ROOT / "upstream/BattleShip/libultraship"


def inherited_windows(name, initializers):
    signatures = [
        ("", ""),
        ("const std::string& c, bool v, const std::string& n, ImVec2 s, uint32_t f", "c,v,n,s,f"),
        ("const std::string& c, bool v, const std::string& n, ImVec2 s", "c,v,n,s"),
        ("const std::string& c, bool v, const std::string& n", "c,v,n"),
        ("const std::string& c, const std::string& n, ImVec2 s, uint32_t f", "c,n,s,f"),
        ("const std::string& c, const std::string& n, ImVec2 s", "c,n,s"),
        ("const std::string& c, const std::string& n", "c,n"),
    ]
    extra = ", " + ", ".join(initializers) if initializers else ""
    return "\n".join(
        "    " + name + "(" + params + ") : GuiWindow(" + args + ")" + extra + " {}"
        for params, args in signatures
    )


def vector_defaults(text):
    # Const-vector defaults must finish construction before the ctor body.
    pattern = r"const std::vector<([^>]+)> (\w+) = \{(.*?)\};"
    helpers = []

    def replace(match):
        typ, name, values = match.groups()
        helpers.append(
            "    static std::vector<"
            + typ
            + "> Build_"
            + name
            + "() {\n        const "
            + typ
            + " values[] = {"
            + values
            + "};\n        return std::vector<"
            + typ
            + ">(values, values+sizeof(values)/sizeof(values[0]));\n    }\n"
        )
        return "const std::vector<" + typ + "> " + name + " = Build_" + name + "();"

    text = re.sub(pattern, replace, text, flags=re.S)
    if len(helpers) != 3:
        raise ValueError("Changed ConsoleWindow const vector defaults")
    return text, helpers


def lower_header(text, name):
    if name == "GuiWindow.h":
        # Defined value-initialization initializes the scalar flag to zero.
        # Plain default-initialization leaves it indeterminate.
        text = once(text, "GuiWindow() = default;", "GuiWindow() : mWindowFlags(0) {}")
    if name == "ConsoleWindow.h":
        text, helpers = vector_defaults(text)
        text, initializers, arrays = remove_class_defaults(text, "ConsoleWindow")
        if arrays:
            raise ValueError("Unexpected ConsoleWindow array defaults")
        text = once(
            text,
            "    using GuiWindow::GuiWindow;",
            inherited_windows("ConsoleWindow", initializers),
        )
        text = once(text, "    struct ConsoleLine {", "".join(helpers) + "    struct ConsoleLine {")
        start = text.index("    struct ConsoleLine {")
        end = text.index("\n    };", start) + 7
        text = text[:start] + data_struct_constructors(text[start:end]) + text[end:]
    if name in ("StatsWindow.h", "GfxDebuggerWindow.h", "EventDebuggerWindow.h"):
        cls = name[:-2]
        text = once(text, "    using GuiWindow::GuiWindow;", inherited_windows(cls, []))
        text = text.replace("mLastBreakPoint = {};", "mLastBreakPoint;")
    if name == "GameOverlay.h":
        text, initializers, arrays = remove_class_defaults(text, "GameOverlay")
        if arrays or initializers != ['mCurrentFont("Default")', "mNeedsCleanup(false)"]:
            raise ValueError("Changed GameOverlay defaults")
    # Passive overlap GUI: the stats overlay replays from the capture.
    if name == "GuiWindow.h":
        text = overlap_lus.gui_window_header(text)
    if name == "StatsWindow.h":
        text = overlap_lus.overlap_drawable(text, "StatsWindow")
    if name == "GameOverlay.h":
        text = overlap_lus.game_overlay_header(text)
    if name == "Console.h":
        text = data_struct_constructors(text)
    if name in ("Font.h", "GuiTexture.h"):
        cls = name[:-2]
        suffix = ", Data(nullptr)" if name == "Font.h" else ""
        text = once(
            text,
            "    using Resource::Resource;",
            "    explicit "
            + cls
            + "(std::shared_ptr<ResourceInitData> initData) : Resource(initData)"
            + suffix
            + " {}",
        )
        text = text.replace("char* Data = nullptr;", "char* Data;")
    text = text.replace(" override", "").replace(" final :", " :").replace("constexpr", "const")
    text = enum_wrappers(text)
    text = re.sub(
        r"(struct (\w+) \{ enum Value \{[^}]*\}; Value value;) ",
        lambda m: m[1] + " " + m[2] + "() : value(static_cast<Value>(0)) {} ",
        text,
    )
    text = text.replace("#include <optional>", "#include <xbox_compat/optional.h>").replace(
        "std::optional<", "xbox_compat::optional<"
    )
    return text


def flatten_delegates(text, cls):
    data = text.encode()
    constructors = []
    for node in walk(PARSER.parse(data).root_node):
        if node.type != "function_definition":
            continue
        decl = field(node, "declarator")
        if not tx(decl).startswith(cls + "::" + cls + "("):
            continue
        body = field(node, "body")
        initializers = next(
            (n for n in node.named_children if n.type == "field_initializer_list"), None
        )
        constructors.append((node, decl, body, initializers))
    primary = [
        entry for entry in constructors if not tx(entry[3]).lstrip(": ").startswith(cls + "(")
    ]
    if len(primary) != 1:
        raise ValueError("Changed primary constructor: " + cls)
    _, decl, body, initializers = primary[0]
    params = field(decl, "parameters")
    names = [re.search(r"(\w+)\s*$", tx(p))[1] for p in params.named_children]
    edits = []
    for node, decl, body_, init in constructors:
        if node == primary[0][0]:
            continue
        if tx(body_).strip() != "{\n}":
            raise ValueError("Delegating constructor gained body: " + cls)
        args = next(n for n in walk(init) if n.type == "argument_list")
        values = [tx(n) for n in args.named_children]
        if len(values) != len(names):
            raise ValueError("Non-direct constructor delegation: " + cls)
        substitutions = dict(zip(names, values))
        payload = tx(initializers) + " " + tx(body)
        payload = re.sub(
            r"\b(" + "|".join(map(re.escape, names)) + r")\b",
            lambda m: "(" + substitutions[m[0]] + ")",
            payload,
        )
        edits.append((init.start_byte, body_.end_byte, payload.encode()))
    for start, end, value in reversed(edits):
        data = data[:start] + value + data[end:]
    return data.decode()


def lower_widget_aggregates(text):
    data = text.encode()
    edits = []

    def arguments(value):
        records = [
            "CommandArgument(" + ", ".join(tx(n) for n in child.named_children) + ")"
            for child in value.named_children
        ]
        if not records:
            return "std::vector<CommandArgument>()"
        return (
            "[&]() -> std::vector<CommandArgument> { const CommandArgument values[] = {"
            + ", ".join(records)
            + "}; return std::vector<CommandArgument>(values,"
            " values+sizeof(values)/sizeof(values[0])); }()"
        )

    for node in walk(PARSER.parse(data).root_node):
        if node.type != "call_expression":
            continue
        function = tx(field(node, "function"))
        args = field(node, "arguments")
        values = [n for n in args.named_children if n.type == "initializer_list"]
        for value in values:
            members = value.named_children
            if function.endswith("->AddCommand"):
                if len(members) not in (2, 3):
                    raise ValueError("Changed command record")
                prefix = (
                    "CommandHandler handler = "
                    + tx(members[0])
                    + "; std::string description = "
                    + tx(members[1])
                    + "; "
                )
                fields = ["handler", "description"]
                if len(members) == 3:
                    records = [
                        "CommandArgument(" + ", ".join(tx(n) for n in child.named_children) + ")"
                        for child in members[2].named_children
                    ]
                    prefix += "const CommandArgument arguments[] = {" + ", ".join(records) + "}; "
                    fields.append(
                        "std::vector<CommandArgument>(arguments,"
                        " arguments+sizeof(arguments)/sizeof(arguments[0]))"
                    )
                expression = (
                    "[&]() -> CommandEntry { "
                    + prefix
                    + "CommandEntry entry = {"
                    + ", ".join(fields)
                    + "}; return entry; }()"
                )
            elif function == "mLog[channel].push_back":
                expression = "ConsoleLine(" + ", ".join(tx(n) for n in members) + ")"
            elif function == "Overlay":
                expression = (
                    "[&]() -> Overlay { Overlay entry = {"
                    + ", ".join(tx(n) for n in members)
                    + "}; return entry; }()"
                )
            else:
                raise ValueError("Unaudited widget aggregate argument: " + function)
            # Overlay({...}) itself is replaced, rather than wrapping its result.
            start, end = (
                (node.start_byte, node.end_byte)
                if function == "Overlay"
                else (value.start_byte, value.end_byte)
            )
            edits.append((start, end, expression.encode()))
    for start, end, value in sorted(edits, reverse=True):
        data = data[:start] + value + data[end:]
    return data.decode()


def lower_source(text, name):
    if name == "EventDebuggerWindow.cpp":
        text = once(
            text,
            "#include <version>",
            "// No standard-library feature-test macros are used in this source.",
        )
    text = re.sub(r"ImVec([24])\{([^{}]*)\}", r"ImVec\1(\2)", text)
    if name in ("GuiElement.cpp", "GuiWindow.cpp", "GuiMenuBar.cpp"):
        text = flatten_delegates(text, name[:-4])
    if name == "GameOverlay.cpp":
        text = once(
            text,
            "GameOverlay::GameOverlay() {",
            'GameOverlay::GameOverlay() : mCurrentFont("Default"), mNeedsCleanup(false) {',
        )
    if name == "GameOverlay.cpp":
        text = text.replace(
            "ImFontConfig fontConf = {};", "ImFontConfig fontConf = ImFontConfig();"
        )
        text = once(text, "switch (var->Type)", "switch (var->Type.GetValue())")
        text = overlap_lus.game_overlay_source(text)
    if name == "Font.cpp":
        text = once(
            text,
            "Font::Font() : Resource(std::shared_ptr<ResourceInitData>()) {",
            "Font::Font() : Resource(std::shared_ptr<ResourceInitData>()), Data(nullptr) {",
        )
    if name == "StatsWindow.cpp":
        text = once(
            text,
            "#if defined(_WIN32)",
            '#if defined(_XBOX)\n    ImGui::Text("Platform: Xbox 360");\n#elif defined(_WIN32)',
        )
    if name == "Console.cpp":
        text = once(
            text,
            "mCommands.contains(commandName)",
            "(mCommands.find(commandName) != mCommands.end())",
        )
    if name == "ConsoleWindow.cpp":
        text = once(
            text,
            "va_copy(argsCopy, args);",
            "argsCopy = args; // Xbox/Windows va_list is a pointer; preserve independent cursor.",
        )
        for member in ["mBindings", "mBindingToggle"]:
            text = once(
                text,
                "window->" + member + ".contains((ImGuiKey)k)",
                "(window->" + member + ".find((ImGuiKey)k) != window->" + member + ".end())",
            )
    if name == "GfxDebuggerWindow.cpp":
        text = once(
            text,
            "#include <optional>",
            '#include <optional>\n#include "ship/resource/ResourceManager.h"',
        )
        text = once(
            text,
            "dynamic_pointer_cast<Fast::Fast3dWindow>",
            "std::dynamic_pointer_cast<Fast::Fast3dWindow>",
        )
        text = text.replace("SDL_SetClipboardText(", "ImGui::SetClipboardText(")
        text = once(text, "const F3DGfx* sub = nullptr", "const F3DGfx* sub")
        data = text.encode()
        edits = []
        for node in walk(PARSER.parse(data).root_node):
            if node.type == "call_expression" and tx(field(node, "function")) == "nodeWithText":
                args = field(node, "arguments")
                if len(args.named_children) == 2:
                    edits.append((args.end_byte - 1, args.end_byte - 1, b", nullptr"))
                elif len(args.named_children) != 3:
                    raise ValueError("Changed nodeWithText arity")
        for start, end, value in reversed(edits):
            data = data[:start] + value + data[end:]
        text = data.decode()
    # SDK integer-to-string overloads expose int64/uint64 only. All reached
    # original arguments are nonnegative bool/size_t values.
    data = text.encode()
    edits = []
    for node in walk(PARSER.parse(data).root_node):
        if node.type == "call_expression" and tx(field(node, "function")) == "std::to_string":
            args = field(node, "arguments")
            arg = args.named_children[0]
            if name not in ("ConsoleWindow.cpp", "GfxDebuggerWindow.cpp"):
                raise ValueError("Unaudited to_string call")
            edits.append(
                (
                    arg.start_byte,
                    arg.end_byte,
                    ("static_cast<unsigned long long>(" + tx(arg) + ")").encode(),
                )
            )
    for start, end, value in reversed(edits):
        data = data[:start] + value + data[end:]
    text = data.decode()
    text = re.sub(r"(?<!\w)vsnprintf\(", "Smash360_Vsnprintf(", text)
    index = 0

    def structured(match):
        nonlocal index
        index += 1
        cv, a, b, expression = match.groups()
        entry = "widget_range_entry_" + str(index)
        return (
            "for ("
            + cv
            + " "
            + entry
            + " : "
            + expression
            + ") { auto& "
            + a
            + " = "
            + entry
            + ".first; auto& "
            + b
            + " = "
            + entry
            + ".second;"
        )

    text = re.sub(
        r"for \(((?:const )?auto\s*&?)\s*\[(\w+),\s*(\w+)\]\s*:\s*([^\n]+?)\) \{", structured, text
    )
    text = (
        text.replace("#include <optional>", "#include <xbox_compat/optional.h>")
        .replace("std::optional<", "xbox_compat::optional<")
        .replace("std::nullopt", "xbox_compat::nullopt")
    )
    text = re.sub(r"\bstd::get<", "xbox_compat::get<", text)
    text = text.replace("constexpr", "const")
    text = lower_widget_aggregates(text)
    text = lower_if_initializers(text, PARSER, walk)
    text = lower_ranges(text.encode()).decode()
    return (
        '#include "prism/compat.h"\n#include "ship/window/gui/Gui.h"\n#include "cvars.h"\n#include'
        ' "crt/snprintf.h"\n'
        + text
    )


def prepare():
    records = json.loads((BASE / "source-lock.json").read_text())
    for relative, digest in records.items():
        data = (UP / relative).read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError("Source drift: " + relative)
        text = data.decode("utf-8-sig").replace("\r\n", "\n")
        if relative.endswith(".h"):
            text = lower_header(text, Path(relative).name)
        else:
            text = lower_source(text, Path(relative).name)
        target = OUT / "generated" / relative
        mapped("upstream/BattleShip/libultraship/" + relative, text, target)
    (OUT / "manifest.json").write_text(
        json.dumps(
            {
                "input_hashes": records,
                "scope": (
                    "actual full widget source and class-header projection; application"
                    " integration/runtime validation separate"
                ),
            },
            indent=2,
        )
    )


def compile_xdk():
    # The complete Fast3D compile records the shared dependencies.
    flags = json.loads((ROOT / "scratch/fast3d-xdk/compile-audit.json").read_text())[
        "translation_units"
    ][0]["command"]
    flags = flags[: flags.index("/c")]
    flags[1:1] = [
        "/I" + str(OUT / "generated/include"),
        "/I" + str(ROOT / "scratch/gui-xdk/overlay/libultraship/include"),
        "/I" + str(ROOT / "scratch/fast3d-xdk/compile-tree/libultraship/include/fast"),
        "/I" + str(ROOT / "upstream/dependencies/stb"),
    ]
    records = []
    for source in [
        ROOT / "tests/gui-widgets-xdk/headers.cpp",
        *sorted((OUT / "generated/src").rglob("*.cpp")),
    ]:
        command = flags + ["/c", "/Fo" + str(OUT / (source.stem + "-xdk.obj")), str(source)]
        run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        log = run.stdout + run.stderr
        (OUT / (source.stem + "-xdk.log")).write_text(log)
        errors = [line for line in log.splitlines() if "error " in line]
        print(source.stem, run.returncode)
        print("\n".join(errors[:8]))
        records.append(
            {
                "source": str(source.relative_to(ROOT)),
                "command": command,
                "exit": run.returncode,
                "errors": errors,
            }
        )
    (OUT / "compile-audit.json").write_text(json.dumps(records, indent=2))
    return int(any(r["exit"] for r in records))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--compile", action="store_true")
    args = parser.parse_args()
    prepare()
    if args.compile:
        raise SystemExit(compile_xdk())
