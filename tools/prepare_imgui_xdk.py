"""Compile the pinned ImGui library and the donor native GUI renderer."""

from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import subprocess
from prepare_prism_xdk import mapped, PARSER, walk, field, tx
from platform_base import resolve as resolve_platform_base
import runpy

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / "upstream/dependencies/imgui"
OUT = ROOT / "scratch/imgui-xdk"
PLATFORM = ROOT / "platform/xbox360/imgui"
LOWER_RANGES = runpy.run_path(str(ROOT / "platform/xbox360/cpp-compat/config/lowering.py"))[
    "lower_ranges"
]


def default_members(text):
    permitted = {
        "ImGuiDemoWindowData",
        "ExampleTreeNode",
        "ExampleDualListBox",
        "ExampleAppPropertyEditor",
        "ExampleAppDocuments",
        "ExampleAssetsBrowser",
        "ImTriangulatorNodeSpan",
        "ImTriangulator",
        "ImGuiTextIndex",
        "ImGuiTypingSelectState",
        "ImGuiMetricsConfig",
        "MergeGroup",
    }
    data = text.encode()
    parsed = data.replace(b"IMGUI_API", b"         ")
    edits = []
    for node in walk(PARSER.parse(parsed).root_node):
        if node.type != "struct_specifier":
            continue
        name, body = tx(field(node, "name")), field(node, "body")
        if not body or name not in permitted:
            continue
        defaults = [
            c
            for c in body.named_children
            if c.type == "field_declaration" and field(c, "default_value")
        ]
        if not defaults:
            continue
        init = []
        for member in defaults:
            decl, value = field(member, "declarator"), field(member, "default_value")
            names = [n for n in walk(decl) if n.type == "field_identifier"]
            if len(names) != 1:
                raise RuntimeError("Ambiguous initialized member")
            member_name = tx(names[0])
            val = tx(value)
            if decl.type == "array_declarator":
                if val != '""':
                    raise RuntimeError("Unsupported member array initializer")
                val = ""  # Original empty string zero-initializes every char.
            init.append(member_name + "(" + val + ")")
            edits.append((decl.end_byte, value.end_byte, b""))
        constructors = []
        for child in body.named_children:
            if child.type != "function_definition":
                continue
            decl = field(child, "declarator")
            if decl and tx(field(decl, "declarator")) == name:
                constructors.append(child)
        if not constructors:
            edits.append(
                (
                    body.start_byte + 1,
                    body.start_byte + 1,
                    ("\n    " + name + "() : " + ", ".join(init) + " {}\n").encode(),
                )
            )
        else:
            for constructor in constructors:
                if any(c.type == "field_initializer_list" for c in constructor.named_children):
                    raise RuntimeError("Existing explicit initializers need review: " + name)
                block = field(constructor, "body")
                edits.append(
                    (block.start_byte, block.start_byte, (" : " + ", ".join(init) + " ").encode())
                )
    for begin, end, replacement in sorted(edits, reverse=True):
        data = data[:begin] + replacement + data[end:]
    return data.decode()


def callback_lambdas(text):
    # XDK lambdas cannot convert to function pointers. These no-capture
    # callbacks become local static member functions, retaining their bodies.
    data = text.encode()
    edits, insertions = [], {}
    for node in walk(PARSER.parse(data.replace(b"IMGUI_API", b"         ")).root_node):
        if node.type != "lambda_expression":
            continue
        capture = next(c for c in node.named_children if c.type == "lambda_capture_specifier")
        if tx(capture) != "[]":
            raise RuntimeError("Capturing ImGui callback needs separate lowering")
        declarator, block = field(node, "declarator"), field(node, "body")
        parameters = field(declarator, "parameters")
        body_text = data[block.start_byte : block.end_byte].decode()
        if "GetClipboardTextFn" in body_text or "return ((const char**)data)[n]" in body_text:
            result = "const char*"
        elif "SetClipboardTextFn" in body_text or "array[n] = selected;" in body_text:
            result = "void"
        elif (
            "return (ImGuiID)idx;" in body_text
            or "return items[idx];" in body_text
            or "return (*p_items)[idx];" in body_text
            or "return self->Items[idx].ID;" in body_text
        ):
            result = "ImGuiID"
        else:
            raise RuntimeError("Unaudited callback return type: " + body_text)
        owner = node.parent
        while owner and owner.type != "function_definition":
            owner = owner.parent
        if owner is None:
            raise RuntimeError("Callback outside a function")
        scope = field(owner, "body")
        name = "Smash360Callback" + str(node.start_byte)
        definition = (
            "\nstruct "
            + name
            + " { static "
            + result
            + " Invoke"
            + tx(parameters)
            + " "
            + body_text
            + " };\n"
        )
        insertions.setdefault(scope.start_byte + 1, []).append(definition)
        edits.append((node.start_byte, node.end_byte, (name + "::Invoke").encode()))
    edits.extend((pos, pos, "".join(values).encode()) for pos, values in insertions.items())
    for start, end, value in sorted(edits, reverse=True):
        data = data[:start] + value + data[end:]
    return data.decode()


def enum_definitions_before_use(text):
    # MSVC16 supports enum underlying types, but not opaque declarations.
    # Move the definition intact; do not replace enum types with ints.
    for forward in list(re.finditer(r"^enum (\w+)\s*:\s*(\w+)\s*;", text, re.M)):
        name, base = forward.groups()
        pattern = r"^enum " + name + r"\s*:\s*" + base + r"\s*\{.*?^\};"
        matches = list(re.finditer(pattern, text, re.M | re.S))
        if len(matches) != 1:
            raise RuntimeError("Ambiguous enum definition: " + name)
        definition = matches[0].group()
        text = text[: matches[0].start()] + "\n" * definition.count("\n") + text[matches[0].end() :]
        text = re.sub(
            r"^enum " + name + r"\s*:\s*" + base + r"\s*;",
            lambda _: definition,
            text,
            count=1,
            flags=re.M,
        )
    return text


def prepare():
    shared_base = resolve_platform_base(ROOT)
    source = OUT / "source"
    source.mkdir(parents=True, exist_ok=True)
    records = []
    locks = json.loads((PLATFORM / "source-lock.json").read_text())
    patch = (
        ROOT
        / "upstream/BattleShip/libultraship/cmake/dependencies/patches/imgui-fixes-and-config.patch"
    )
    if hashlib.sha256(patch.read_bytes()).hexdigest() != locks["LUS_CONFIG_PATCH"]:
        raise RuntimeError("Pinned LUS ImGui configuration patch changed")
    for file in sorted(ORIGINAL.iterdir()):
        if file.suffix not in (".h", ".cpp"):
            continue
        if hashlib.sha256(file.read_bytes()).hexdigest() != locks[file.name]:
            raise RuntimeError("Pinned ImGui source changed: " + file.name)
        original = file.read_text(encoding="utf-8-sig")
        text = original
        if file.name == "imconfig.h":
            # Exact LUS config patch. Its Metal/SDL backend patches are irrelevant
            # to this Xbox backend and remain in the pinned reference patch.
            text = text.replace(
                "//#define IMGUI_DEFINE_MATH_OPERATORS", "#define IMGUI_DEFINE_MATH_OPERATORS"
            )
            text += "\n#define ImTextureID void*\n"
            text += (
                "\n#ifdef _XBOX\n#define IMGUI_DISABLE_WIN32_FUNCTIONS\n#define"
                " IMGUI_DISABLE_DEFAULT_SHELL_FUNCTIONS\n#endif\n"
            )
        if file.name in ("imgui.h", "imgui_internal.h"):
            text = enum_definitions_before_use(text)
            text = re.sub(r"\bconstexpr\s+", "", text)
        if file.name.startswith("imgui"):
            text = default_members(text)
            text = callback_lambdas(text)
            text = LOWER_RANGES(text.encode(), "Smash360ImGuiBegin", "Smash360ImGuiEnd").decode()
        if file.name == "imgui_internal.h":
            anchor = "    ImGuiID             WindowID;\n};"
            if text.count(anchor) != 1:
                raise RuntimeError("Focus scope record changed")
            text = text.replace(
                anchor,
                anchor
                + "\ninline ImGuiFocusScopeData Smash360FocusScope(ImGuiID id, ImGuiID window) {"
                " ImGuiFocusScopeData result = { id, window }; return result; }",
            )
        if file.name == "imgui.cpp":
            text = text.replace(
                "g.NavFocusRoute.push_back({ focus_scope_id, g.NavWindow->ID });",
                "g.NavFocusRoute.push_back(Smash360FocusScope(focus_scope_id, g.NavWindow->ID));",
            )
            text = text.replace(
                "g.NavFocusRoute.push_back({ window->NavRootFocusScopeId, window->ID });",
                "g.NavFocusRoute.push_back(Smash360FocusScope(window->NavRootFocusScopeId,"
                " window->ID));",
            )
        if file.name == "imgui_demo.cpp":
            text = text.replace(
                "ExampleTreeNodeMemberInfos[]\n{", "ExampleTreeNodeMemberInfos[] =\n{"
            )
            text = text.replace(
                "static ImVec4 col4 = { 1.0f, 0.0f, 0.2f, 1.0f };",
                "static ImVec4 col4(1.0f, 0.0f, 0.2f, 1.0f);",
            )
            text = text.replace(
                "sizeof(ExampleTreeNode::Name)", "sizeof(((ExampleTreeNode*)0)->Name)"
            )
            text = text.replace(
                "ImVec2 button_sz = { ImGui::GetFrameHeight(), ImGui::GetFrameHeight() };",
                "ImVec2 button_sz(ImGui::GetFrameHeight(), ImGui::GetFrameHeight());",
            )
            match = re.search(r"const ImVec2 pos_norms\[\] = \{ (.*?) \};", text)
            if not match:
                raise RuntimeError("Demo shape source changed")
            converted = re.sub(r"\{ ([^{}]+) \}", r"ImVec2(\1)", match[1])
            text = text[: match.start(1)] + converted + text[match.end(1) :]
        if file.name == "imgui.h":
            text += '\n#include "range.h"\n'
        target = source / file.name
        if file.name.startswith("imstb_"):
            # STB implementation sections intentionally support repeated includes
            # under different implementation macros. Never add an outer guard.
            target.write_text(
                '#line 1 "' + file.relative_to(ROOT).as_posix() + '"\n' + text, encoding="utf-8"
            )
        else:
            mapped(file.relative_to(ROOT).as_posix(), text, target)
        records.append(
            {
                "source": str(file.relative_to(ROOT)),
                "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
                "generated_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            }
        )
    (OUT / "source-map.json").write_text(json.dumps(records, indent=2) + "\n")
    donor = shared_base / "sources/imgui/imgui_xenos.cpp"
    if not donor.is_file():
        raise RuntimeError("Native GUI source missing")


def compile_xdk():
    shared_base = resolve_platform_base(ROOT)
    xdk = Path(os.environ.get("XEDK", "C:/Program Files (x86)/Microsoft Xbox 360 SDK"))
    results = []
    for name in (
        "imgui",
        "imgui_draw",
        "imgui_tables",
        "imgui_widgets",
        "imgui_demo",
        "imgui_xenos",
        "platform_frame",
        "platform_adapter",
    ):
        source = (
            PLATFORM / "platform_adapter.cpp"
            if name == "platform_adapter"
            else (
                shared_base / ("sources/imgui/" + name + ".cpp")
                if name in ("imgui_xenos", "platform_frame")
                else OUT / ("source/" + name + ".cpp")
            )
        )
        command = [
            str(xdk / "bin/win32/cl.exe"),
            "/nologo",
            "/c",
            "/TP",
            "/EHsc",
            "/MT",
            "/W3",
            "/D_XBOX",
            "/DNOMINMAX",
            "/I" + str(xdk / "include/xbox"),
            "/I" + str(OUT / "source"),
            "/I" + str(PLATFORM),
            "/I" + str(OUT),
            "/I" + str(ROOT / "platform/xbox360/input"),
            "/I" + str(ROOT / "platform/xbox360/graphics"),
            "/I" + str(shared_base / "sources/imgui"),
            "/I" + str(shared_base / "sources"),
            "/Fo" + str(OUT / (name + ".obj")),
            str(source),
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        (OUT / (name + ".log")).write_text(result.stdout + result.stderr)
        results.append({"name": name, "passed": result.returncode == 0, "command": command})
        print(name, "PASS" if not result.returncode else "FAIL")
        if result.returncode:
            print(
                "\n".join(
                    line for line in (result.stdout + result.stderr).splitlines() if "error" in line
                )[:2500]
            )
    (OUT / "compile-report.json").write_text(json.dumps(results, indent=2) + "\n")
    if not all(r["passed"] for r in results):
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compile", action="store_true")
    args = parser.parse_args()
    prepare()
    if args.compile:
        compile_xdk()
