"""Typed lowering of a closed set of port GUI records and container literals.

Unknown initializer contexts stay visible as native compiler errors. No GUI
record, callback, field, variant alternative, or default value is substituted.
"""

from pathlib import Path
import re
import runpy
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "tools"))
COMMON = runpy.run_path(str(ROOT / "tools/prepare_prism_xdk.py"))
FAST = runpy.run_path(str(ROOT / "tools/prepare_fast3d_xdk.py"))
CTRL = runpy.run_path(str(ROOT / "platform/xbox360/cpp-compat/controllers/lowering.py"))
from xbox360_platform.cpp_syntax import lower_if_initializers

PARSER, walk, field, tx = [COMMON[n] for n in ("PARSER", "walk", "field", "tx")]
OPTIONS = [
    "WidgetOptions",
    "TextOptions",
    "ButtonOptions",
    "ColorPickerOptions",
    "WindowButtonOptions",
    "CheckboxOptions",
    "ComboboxOptions",
    "IntSliderOptions",
    "FloatSliderOptions",
    "BtnSelectorOptions",
    "RadioButtonsOptions",
    "InputOptions",
]
RECORDS = ["WidgetInfo", "WidgetPath", "disabledInfo", "SidebarEntry", "MainMenuEntry", "SearchEntry", "SearchWidget"]
ENUMS = {"Colors", "InputTypes", "LabelPositions", "ComponentAlignments", "ColorPickerModifiers"}


def split_types(text):
    result = []
    start = 0
    depth = 0
    for i, c in enumerate(text):
        if c == "<":
            depth += 1
        if c == ">":
            depth -= 1
        if c == "," and depth == 0:
            result.append(text[start:i].strip())
            start = i + 1
    result.append(text[start:].strip())
    return result


def members_of(node, data):
    members = []
    for member in field(node, "body").named_children:
        if member.type != "field_declaration":
            continue
        if any(c.type == "storage_class_specifier" for c in member.named_children):
            continue
        typ = field(member, "type")
        if not typ:
            continue
        prefix = data[member.start_byte : typ.end_byte].decode()
        decls = member.children_by_field_name("declarator")
        for decl in decls:
            if any(n.type == "function_declarator" for n in walk(decl)):
                continue
            names = [n for n in walk(decl) if n.type == "field_identifier"]
            if len(names) != 1 or decl.type == "array_declarator":
                raise ValueError("Unknown GUI member " + tx(member))
            name = names[0]
            suffix = data[decl.start_byte : name.start_byte].decode() + data[name.end_byte : decl.end_byte].decode()
            following = next((d.start_byte for d in decls if d.start_byte > decl.start_byte), member.end_byte)
            default = next(
                (
                    v
                    for v in member.children_by_field_name("default_value")
                    if decl.end_byte <= v.start_byte < following
                ),
                None,
            )
            members.append(
                {"name": tx(name), "type": (prefix + suffix).strip(), "default": tx(default) if default else None}
            )
    return members


SCHEMA = {}
for filename in ("UIWidgets.hpp", "MenuTypes.h"):
    raw = (ROOT / "upstream/BattleShip/port/gui" / filename).read_bytes()
    for node in walk(PARSER.parse(raw).root_node):
        if node.type != "struct_specifier" or not field(node, "body"):
            continue
        name = tx(field(node, "name"))
        if name not in OPTIONS + RECORDS:
            continue
        SCHEMA[name] = members_of(node, raw)


def canonical(typ):
    return typ.strip().removeprefix("const ").rstrip("& ").strip()


def emit_aggregate(typ, node, statements, counter):
    typ = canonical(typ)
    simple = typ.split("::")[-1]
    if node.type != "initializer_list":
        return tx(node)
    children = [n for n in node.named_children if n.type != "comment"]
    container = re.fullmatch(r"std::(vector|set|map|unordered_map)<(.*)>", typ, re.S)
    if not container and (simple not in SCHEMA or simple == "SearchWidget"):
        return value(typ, node, "&")
    variable = "_aggregate" + str(counter[0])
    counter[0] += 1
    statements.append(typ + " " + variable + (" = " + typ + "::Smash360Value()" if not container else "") + ";")
    if container:
        kind, args = container.groups()
        types = split_types(args)
        for child in children:
            if kind in ("map", "unordered_map"):
                pair = [n for n in child.named_children if n.type != "comment"]
                if child.type != "initializer_list" or len(pair) != 2:
                    raise ValueError("Invalid map literal")
                k = emit_aggregate(types[0], pair[0], statements, counter)
                v = emit_aggregate(types[1], pair[1], statements, counter)
                statements.append(variable + ".insert(std::make_pair(" + k + ", " + v + "));")
            else:
                expr = emit_aggregate(types[0], child, statements, counter)
                statements.append(variable + "." + ("push_back" if kind == "vector" else "insert") + "(" + expr + ");")
    else:
        schema = SCHEMA[simple]
        if any(n.type == "initializer_pair" for n in children):
            previous = -1
            pairs = []
            for n in children:
                name = tx(field(n, "designator")).lstrip(".")
                position = next((i for i, m in enumerate(schema) if m["name"] == name), -1)
                if position <= previous:
                    raise ValueError("GUI designator ordering/member changed")
                previous = position
                pairs.append((schema[position], field(n, "value")))
        else:
            if simple in OPTIONS and simple != "WidgetOptions" and children:
                base = emit_aggregate("UIWidgets::WidgetOptions", children[0], statements, counter)
                statements.append("static_cast<UIWidgets::WidgetOptions&>(" + variable + ") = " + base + ";")
                children = children[1:]
            if len(children) > len(schema):
                raise ValueError("GUI aggregate arity changed")
            pairs = list(zip(schema, children))
        for member, child in pairs:
            expr = emit_aggregate(member["type"], child, statements, counter)
            statements.append(variable + "." + member["name"] + " = " + expr + ";")
    return variable


def value(typ, node, capture="&"):
    """Build one typed initializer expression, preserving written order."""
    typ = canonical(typ)
    simple = typ.split("::")[-1]
    if node.type != "initializer_list":
        return tx(node)
    children = [n for n in node.named_children if n.type != "comment"]
    if children and (
        re.fullmatch(r"std::(vector|set|map|unordered_map)<(.*)>", typ, re.S)
        or simple in SCHEMA
        and simple != "SearchWidget"
    ):
        statements = []
        result = emit_aggregate(typ, node, statements, [0])
        return "([" + capture + "]() -> " + typ + " { " + " ".join(statements) + " return " + result + "; }())"
    if typ in ("ImVec2", "ImVec4"):
        return typ + "(" + ", ".join(tx(n) for n in children) + ")"
    if typ == "ImRect":
        return typ + "(" + ", ".join(value("ImVec2", n, capture) for n in children) + ")"
    if typ in ("Color_RGB8", "Color_RGBA8"):
        fields = ["r", "g", "b"] + (["a"] if typ == "Color_RGBA8" else [])
        if len(children) > len(fields):
            raise ValueError("Invalid color aggregate")
        return (
            "Smash360Port::"
            + ("RGBA" if typ == "Color_RGBA8" else "RGB")
            + "("
            + ", ".join(tx(n) for n in children)
            + ")"
        )
    container = re.fullmatch(r"std::(vector|set|map|unordered_map)<(.*)>", typ, re.S)
    if container:
        if not children:
            return typ + "()"
        kind, args = container.groups()
        types = split_types(args)
        statements = []
        for child in children:
            if kind in ("map", "unordered_map"):
                pair = [n for n in child.named_children if n.type != "comment"]
                if child.type != "initializer_list" or len(pair) != 2:
                    raise ValueError("Invalid map literal")
                statements.append(
                    "v.insert(std::make_pair("
                    + value(types[0], pair[0], capture)
                    + ", "
                    + value(types[1], pair[1], capture)
                    + "));"
                )
            else:
                statements.append(
                    "v."
                    + ("push_back" if kind == "vector" else "insert")
                    + "("
                    + value(types[0], child, capture)
                    + ");"
                )
        return "([" + capture + "]() -> " + typ + " { " + typ + " v; " + " ".join(statements) + " return v; }())"
    if simple in SCHEMA:
        schema = SCHEMA[simple]
        if simple == "SearchWidget":
            # The reference is required; it must be bound in construction.
            if not children or any(n.type == "initializer_pair" for n in children):
                raise ValueError("SearchWidget reference initializer")
            return typ + "(" + ", ".join(value(m["type"], n, capture) for m, n in zip(schema, children)) + ")"
        assignments = []
        if any(n.type == "initializer_pair" for n in children):
            previous = -1
            for n in children:
                name = tx(field(n, "designator")).lstrip(".")
                positions = [i for i, m in enumerate(schema) if m["name"] == name]
                if len(positions) != 1 or positions[0] <= previous:
                    raise ValueError("GUI designator ordering/member changed")
                previous = positions[0]
                m = schema[previous]
                assignments.append("v." + name + " = " + value(m["type"], field(n, "value"), capture) + ";")
        else:
            if simple in OPTIONS and simple != "WidgetOptions" and children:
                assignments.append(
                    "static_cast<UIWidgets::WidgetOptions&>(v) = "
                    + value("UIWidgets::WidgetOptions", children[0], capture)
                    + ";"
                )
                children = children[1:]
            for m, n in zip(schema, children):
                assignments.append("v." + m["name"] + " = " + value(m["type"], n, capture) + ";")
            if len(children) > len(schema):
                raise ValueError("GUI aggregate arity changed")
        if not assignments:
            return typ + "::Smash360Value()"
        return (
            "(["
            + capture
            + "]() -> "
            + typ
            + " { "
            + typ
            + " v = "
            + typ
            + "::Smash360Value(); "
            + " ".join(assignments)
            + " return v; }())"
        )
    if not children:
        return typ + "()"
    raise ValueError("Unaudited GUI initializer type: " + typ)


def record_defaults(text, names):
    # A plain default constructor retains original indeterminate scalar fields.
    # The explicit value factory separately implements T{} zero-initialization.
    for name in names:
        schema = SCHEMA[name]
        if name == "SearchWidget":
            text = text.replace('    std::string extraTerms = "";', "    std::string extraTerms;", 1) if False else text
            data = text.encode()
            node = next(
                n
                for n in walk(PARSER.parse(data).root_node)
                if n.type == "struct_specifier" and tx(field(n, "name")) == name and field(n, "body")
            )
            block = tx(node).replace('std::string extraTerms = "";', "std::string extraTerms;")
            ctor = """\

    SearchWidget(WidgetInfo& i, const std::string& m, const \
std::string& s, const std::string& l, const std::string& e = \"\") : \
info(i),menuName(m),sidebarName(s),location(l),extraTerms(e) {}
"""
            block = block.replace("struct SearchWidget {", "struct SearchWidget {" + ctor)
            text = text[: node.start_byte] + block + text[node.end_byte :]
            continue
        # Lower nonempty class-valued member defaults to typed expressions first.
        data = text.encode()
        edits = []
        node = next(
            n
            for n in walk(PARSER.parse(data).root_node)
            if n.type == "struct_specifier" and tx(field(n, "name")) == name and field(n, "body")
        )
        for member in field(node, "body").named_children:
            if member.type != "field_declaration":
                continue
            for default in member.children_by_field_name("default_value"):
                if default.type != "initializer_list":
                    continue
                decl = member.children_by_field_name("declarator")[0]
                member_name = next(n for n in walk(decl) if n.type == "field_identifier")
                m = next(m for m in schema if m["name"] == tx(member_name))
                replacement = value(m["type"], default, "")
                edits.append((default.start_byte, default.end_byte, replacement.encode()))
        text = CTRL["apply"](data, edits).decode()
        data = text.encode()
        node = next(
            n
            for n in walk(PARSER.parse(data).root_node)
            if n.type == "struct_specifier" and tx(field(n, "name")) == name and field(n, "body")
        )
        block, initializers, arrays = FAST["remove_class_defaults"](tx(node), name)
        text = (data[: node.start_byte] + block.encode() + data[node.end_byte :]).decode()
        if arrays:
            raise ValueError("Unexpected GUI array default")
        constructor = "    " + name + "()" + (" : " + ", ".join(initializers) if initializers else "") + " {}\n"
        missing = []
        for m in schema:
            if m["default"] is not None:
                continue
            if "&" in m["type"]:
                raise ValueError("Unbound GUI reference")
            missing.append(
                "v." + m["name"] + " = " + ("0" if m["type"].rstrip().endswith("*") else m["type"] + "()") + ";"
            )
        factory = "    static " + name + " Smash360Value() { " + name + " v; " + " ".join(missing) + " return v; }\n"
        text = re.sub(r"(struct " + name + r"(?:\s*:\s*\w+)?\s*\{)", r"\1\n" + constructor + factory, text, count=1)
    return text


def lower_literals(text):
    # Outer initializer contexts recursively lower their nested typed contents.
    data = text.encode()
    edits = []
    for node in walk(PARSER.parse(data).root_node):
        typ = None
        target = node
        if node.type == "call_expression":
            fn = tx(field(node, "function"))
            args = field(node, "arguments").named_children
            if fn.split("::")[-1] in OPTIONS + RECORDS and not args and fn.split("::")[-1] != "SearchWidget":
                if not any(a <= node.start_byte and node.end_byte <= b for a, b, _ in edits):
                    edits.append((node.start_byte, node.end_byte, (fn + "::Smash360Value()").encode()))
                continue
            if fn.split("::")[-1] in OPTIONS + RECORDS and len(args) == 1 and args[0].type == "initializer_list":
                typ = fn
                init = args[0]
            elif fn in ("Button", "UIWidgets::Button") and len(args) == 2 and args[1].type == "initializer_list":
                typ = "UIWidgets::ButtonOptions"
                init = args[1]
                target = init
            else:
                continue
        elif node.type == "compound_literal_expression":
            typ = field(node, "type")
            init = field(node, "value")
            if not typ or not init or init.type != "initializer_list":
                continue
            typ = tx(typ)
            if not typ.strip():
                continue
        elif node.type == "init_declarator":
            init = field(node, "value")
            if not init or init.type != "initializer_list":
                continue
            decl = node.parent
            if decl.type != "declaration":
                continue
            typ = tx(field(decl, "type"))
            target = init
            if field(node, "declarator").type == "array_declarator":
                continue
        elif node.type == "optional_parameter_declaration":
            init = field(node, "default_value")
            if init and init.type == "compound_literal_expression":
                init = field(init, "value")
            if not init or init.type != "initializer_list":
                continue
            typ = tx(field(node, "type"))
            target = init
        elif node.type == "assignment_expression" and tx(field(node, "left")) == "disabledMap":
            init = field(node, "right")
            if not init or init.type != "initializer_list":
                continue
            typ = "std::unordered_map<uint32_t, disabledInfo>"
            target = init
        else:
            continue
        if any(a <= target.start_byte and target.end_byte <= b for a, b, _ in edits):
            continue
        ancestor = node.parent
        local = False
        while ancestor:
            if ancestor.type in ("function_definition", "lambda_expression"):
                local = True
                break
            ancestor = ancestor.parent
        edits = [e for e in edits if not (target.start_byte <= e[0] and e[1] <= target.end_byte)]
        replacement = value(typ, init, "&" if local else "")
        if not local and node.type == "init_declarator" and replacement.startswith("([]() -> "):
            # XDK namespace-scope lambda name lookup differs from standard C++.
            # A namespace-local builder function keeps the identical lookup.
            name = "Smash360_Build_" + tx(field(node, "declarator"))
            prefix = "([]() -> " + canonical(typ) + " {"
            if not replacement.startswith(prefix) or not replacement.endswith("}())"):
                raise ValueError("Invalid generated global initializer")
            body = replacement[len(prefix) : -4]
            function = "static " + canonical(typ) + " " + name + "() {" + body + "}\n"
            edits.append((node.parent.start_byte, node.parent.start_byte, function.encode()))
            replacement = name + "()"
        edits.append((target.start_byte, target.end_byte, replacement.encode()))
    return CTRL["apply"](data, edits).decode()


def calls(text):
    data = text.encode()
    edits = []
    vec2 = {
        "ImGui::SetNextWindowSizeConstraints": {0, 1},
        "ImGui::BeginChild": {1},
        "ImGui::SetNextWindowSize": {0},
        "ImGui::SetNextWindowPos": {0, 2},
    }
    vec4 = {"ImGui::PushStyleColor": {1}, "ImGui::GetColorU32": {0}}
    for node in walk(PARSER.parse(data).root_node):
        if node.type != "call_expression":
            continue
        fn = tx(field(node, "function"))
        args = field(node, "arguments").named_children
        for i, arg in enumerate(args):
            if arg.type != "initializer_list":
                continue
            typ = None
            if i in vec2.get(fn, set()):
                typ = "ImVec2"
            if i in vec4.get(fn, set()):
                typ = "ImVec4"
            if fn == "sidebars.at(pathInfo.sidebarName).columnWidgets.push_back":
                typ = "std::vector<WidgetInfo>"
            if fn == "entry.columnWidgets.at(column).push_back":
                typ = "WidgetInfo"
            if typ:
                edits.append((arg.start_byte, arg.end_byte, value(typ, arg).encode()))
        if relative_call_is_map_emplace(fn) and len(args) == 2:
            replacement = fn[: -len("emplace")] + "insert(std::make_pair(" + ", ".join(tx(a) for a in args) + "))"
            edits.append((node.start_byte, node.end_byte, replacement.encode()))
    return CTRL["apply"](data, edits).decode()


def relative_call_is_map_emplace(fn):
    return fn in (
        "menuEntries.emplace",
        'menuEntries["Settings"].sidebars.emplace',
        "infoCache.emplace",
        "menuEntries.at(sectionName).sidebars.emplace",
    )


def menu_class(text):
    data = text.encode()
    node = next(
        n
        for n in walk(PARSER.parse(data).root_node)
        if n.type == "field_declaration" and b"searchSidebarEntry" in n.text
    )
    init = field(node, "default_value")
    expression = value("SidebarEntry", init, "")
    start = expression.index("{") + 1
    body = expression[start:-4]
    function = "    static SidebarEntry BuildSearchSidebar() {" + body + "}\n"
    text = (data[: node.start_byte] + b"const SidebarEntry searchSidebarEntry;" + data[node.end_byte :]).decode()
    text = text.replace("bool allowPopout = true;", "bool allowPopout;")
    # Constructor overload with exactly (string,string) resolves to Menu's own
    # constructor with defaulted last arguments, as in the original.
    signatures = [
        ("", ""),
        ("const std::string& c,bool v,const std::string& n,ImVec2 s,uint32_t f", "c,v,n,s,f"),
        ("const std::string& c,bool v,const std::string& n,ImVec2 s", "c,v,n,s"),
        ("const std::string& c,bool v,const std::string& n", "c,v,n"),
        ("const std::string& c,const std::string& n,ImVec2 s,uint32_t f", "c,n,s,f"),
        ("const std::string& c,const std::string& n,ImVec2 s", "c,n,s"),
    ]
    constructors = "\n".join(
        "    Menu("
        + params
        + ") : GuiWindow("
        + args
        + "),searchSidebarEntry(BuildSearchSidebar()),allowPopout(true) {}"
        for params, args in signatures
    )
    return text.replace("    using GuiWindow::GuiWindow;", constructors + "\n" + function)


def port_menu_capabilities(text):
    text = text.replace("#include <SDL2/SDL.h>", "#if !defined(_XBOX)\n#include <SDL2/SDL.h>\n#endif")
    anchor = "#if !defined(__ANDROID__) && !defined(BATTLESHIP_UWP)\n// Shader-pack downloader UI"
    if text.count(anchor) != 1:
        raise ValueError("Shader downloader definition guard changed")
    text = text.replace(
        anchor, "#if !defined(__ANDROID__) && !defined(BATTLESHIP_UWP) && !defined(_XBOX)\n// Shader-pack downloader UI"
    )
    anchor = "#if !defined(__ANDROID__) && !defined(BATTLESHIP_UWP)\n    RenderShaderPackModal();"
    if text.count(anchor) != 1:
        raise ValueError("Shader downloader modal call changed")
    text = text.replace(
        anchor, "#if !defined(__ANDROID__) && !defined(BATTLESHIP_UWP) && !defined(_XBOX)\n    RenderShaderPackModal();"
    )
    # Guard complete controls, never replace the callback with a no-op. The
    # script-mod panel is already excluded by the target DISABLE_SCRIPTING.
    data = text.encode()
    edits = []
    for node in walk(PARSER.parse(data).root_node):
        if node.type != "expression_statement":
            continue
        statement = tx(node)
        if not statement.lstrip().startswith("AddWidget("):
            continue
        if statement.lstrip().startswith('AddWidget(path, "mods_panel"'):
            continue
        if (
            "SDL_OpenURL(" in statement
            or "SDL_SetHint(" in statement
            or ".CustomFunction(RenderShaderPackDownloader)" in statement
        ):
            edits.append(
                (node.start_byte, node.end_byte, ("\n#if !defined(_XBOX)\n" + statement + "\n#endif\n").encode())
            )
    if len(edits) != 6:
        raise ValueError("Expected five desktop SDL controls and one shader downloader control")
    return CTRL["apply"](data, edits).decode()


def transform(relative, text):
    if relative.endswith("/PortMenu.cpp"):
        text = port_menu_capabilities(text)
    text = text.replace("#include <libultraship/libultraship.h>", '#include "port/gui_includes.h"')
    text = text.replace("#include <variant>", "#include <xbox_compat/variant.h>")
    text = (
        text.replace("std::variant<", "xbox_compat::variant<")
        .replace("std::get<", "xbox_compat::get<")
        .replace("std::get_if<", "xbox_compat::get_if<")
    )
    text = text.replace("#include <filesystem>", '#include "filesystem/filesystem.h"').replace(
        "std::filesystem", "xbox_compat::filesystem"
    )
    text = text.replace("constexpr ", "const ")
    if relative.endswith("UIWidgets.cpp"):
        text = text.replace("std::round(", "Smash360Controllers::Round(")
        for component in "xyz":
            original = "fmin(fmax(colorVec." + component + " * 255, 0), 255)"
            if text.count(original) != 1:
                raise ValueError("UI color conversion changed")
            text = text.replace(original, "Shipyard::Math::ColorByte(colorVec." + component + ")")
    if relative.endswith("/Menu.h"):
        text = menu_class(text)
    if relative.endswith("/Menu.cpp"):
        text = text.replace("sidebar->contains(sectionIndex)", "(sidebar->find(sectionIndex) != sidebar->end())")
        text = text.replace(
            "defaultThemeIndex(defaultThemeIndex_) {",
            "defaultThemeIndex(defaultThemeIndex_), searchSidebarEntry(BuildSearchSidebar()), allowPopout(true) {",
        )
        text = text.replace("return {};", "return std::string();").replace(" noexcept", " throw()")
        text = text.replace("std::reinterpret_pointer_cast<", "Smash360Gui::ReinterpretPointerCast<")
        text = text.replace(
            'std::erase_if(menuEntries["Settings"].sidebarOrder, [](std::string& name) { return name == "Search"; });',
            """\
menuEntries[\"Settings\"].sidebarOrder.\
erase(std::remove_if(menuEntries[\"Settings\"].sidebarOrder.begin(), \
menuEntries[\"Settings\"].sidebarOrder.end(), [](const std::string& \
name) { return name == \"Search\"; }), menuEntries[\"Settings\"].\
sidebarOrder.end());""",
        )
        # Both dimensions originate in finite integer window/CVar dimensions.
        text = text.replace(
            "std::fminf(windowWidth * 0.9f, (windowHeight * 1.77f))",
            "(std::min)(windowWidth * 0.9f, (windowHeight * 1.77f))",
        )
        text = '#include "gui/compiler.h"\n#include <ship/window/gui/ConsoleWindow.h>\n' + text
    if relative.endswith("/PortMenu.h"):
        text = text.replace("~PortMenu() override = default;", "~PortMenu() override {}")
        text = text.replace("bool mShowReextractMessage = false;", "bool mShowReextractMessage;").replace(
            "bool mMenuElementsInitialized = false;", "bool mMenuElementsInitialized;"
        )
    if relative.endswith("/PortMenu.cpp"):
        text = text.replace(
            "UIWidgets::Colors::LightBlue) {",
            "UIWidgets::Colors::LightBlue), mShowReextractMessage(false), mMenuElementsInitialized(false) {",
        )
    text = text.replace("typename T = size_t", "typename T").replace("typename T = int32_t", "typename T")
    text = text.replace("using SectionFunc = void (*)();", "typedef void (*SectionFunc)();")
    text = re.sub(r"using (\w+) = ([^;]+);", r"typedef \2 \1;", text)
    if relative.endswith("UIWidgets.hpp"):
        text = record_defaults(text, OPTIONS)
    if relative.endswith("UIWidgets.hpp"):
        # Preserve the two non-deduced original default-template entry points.
        extra = """\

inline bool CVarCombobox(const char* label,const char* cvarName,const \
std::vector<const char*>& values,const ComboboxOptions& options = \
ComboboxOptions::Smash360Value()) { return \
CVarCombobox<int32_t>(label,cvarName,values,options); }
template<size_t N> bool CVarCombobox(const char* label,const char* \
cvarName,const char* (&values)[N],const ComboboxOptions& options = \
ComboboxOptions::Smash360Value()) { return CVarCombobox<int32_t,\
N>(label,cvarName,values,options); }
"""
        text = text.replace(
            "void PushStyleSlider(Colors color = Colors::LightBlue);",
            extra + "\nvoid PushStyleSlider(Colors color = Colors::LightBlue);",
        )
    if relative.endswith("MenuTypes.h"):
        text = text.replace(
            '{ Ship::AudioBackend::NUL, "Null" },',
            '{ Ship::AudioBackend::NUL, "Null" },\n    { Ship::AudioBackend::XAUDIO2, "XAudio2" },',
        )
        text = text.replace(
            '{ Ship::WindowBackend::FAST3D_SDL_METAL, "Metal" },',
            '{ Ship::WindowBackend::FAST3D_SDL_METAL, "Metal" },\n    { Ship::WindowBackend::FAST3D_XENOS, "Xenos" },',
        )
        text = record_defaults(text, RECORDS)
    text = lower_literals(text)
    text = calls(text)
    text = lower_if_initializers(text, PARSER, walk)
    text = CTRL["syntax"](text, ENUMS)
    text = text.replace("std::variant<", "xbox_compat::variant<")
    text = text.replace("std::bad_variant_access", "xbox_compat::bad_variant_access")
    text = text.replace(
        "static_cast<int32_t>(configWindowBackend)", "static_cast<int32_t>(configWindowBackend.GetValue())"
    )
    text = text.replace("(int32_t)(configWindowBackend)", "static_cast<int32_t>(configWindowBackend.GetValue())")
    return '#include "controllers/compiler.h"\n#include "math/color.h"\n#include <xbox_compat/variant.h>\n' + text
