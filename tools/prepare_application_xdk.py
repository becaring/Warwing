"""Compose owned source projections and audited game objects into Xbox projects.

This does not downlevel code or infer exclusions from compiler failures. Missing
providers and unreviewed conflicts stop assembly with a machine-readable report.
"""

from pathlib import Path
import argparse, hashlib, json, re, runpy, shutil, sys
import xml.etree.ElementTree as ET
from application_compile_definitions import application_definitions

ROOT = Path(__file__).resolve().parents[1]
from platform_base import resolve as resolve_platform_base

PLATFORM_BASE = resolve_platform_base(ROOT)
from xbox360_platform.build_policy import CXX_MSBUILD

UP = ROOT / "upstream/BattleShip"
OUT = ROOT / "scratch/application-xdk/native"
TREE = OUT / "source/BattleShip"
PLATFORM = ROOT / "platform/xbox360"
sys.path.insert(0, str(PLATFORM / "game-compat"))
from source_tree import stage_sources, starts_with_pragma_once

XML = "http://schemas.microsoft.com/developer/msbuild/2003"
ET.register_namespace("", XML)
SOURCE_EXT = {".c", ".cpp", ".h", ".hpp", ".hxx", ".inc", ".inl"}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stable(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = content.encode("utf-8") if isinstance(content, str) else content
    if not path.exists() or path.read_bytes() != raw:
        path.write_bytes(raw)


def json_file(path, data):
    stable(path, json.dumps(data, indent=2) + "\n")


def relative(path):
    return Path(path).relative_to(ROOT).as_posix()


def relocate_platform_includes(content):
    # Isolated providers record absolute owned helper includes. The assembled
    # build must use one physical instance of each helper, especially headers
    # using pragma once, rather than mixing its snapshot and the live source.
    prefix = (ROOT / "platform").as_posix().encode() + b"/"
    target = (OUT / "source/platform").as_posix().encode() + b"/"
    return re.sub(
        rb'(^\s*#\s*include\s*")' + re.escape(prefix), lambda m: m[1] + target, content, flags=re.M
    )


def node(parent, name, text=None, **attributes):
    child = ET.SubElement(parent, "{" + XML + "}" + name, attributes)
    if text is not None:
        child.text = str(text)
    return child


# Each name is a source owner, not an include-order preference. Known overlap
# rules below state which owner has already composed the required changes.
PROVIDERS = [
    ("game", "scratch/game-xdk/c-language-overlay", ""),
    ("gbi", "scratch/game-xdk/gbi-source-overlay", ""),
    ("endian", "scratch/endian-xdk/source", ""),
    ("startup", "scratch/startup-xdk/generated", ""),
    ("graphics", "scratch/graphics-xdk/include", "libultraship/include/"),
    ("fast3d", "scratch/fast3d-xdk/overlay", ""),
    ("config", "scratch/config-xdk/generated", "libultraship/"),
    ("resources", "scratch/resources-xdk/generated", "libultraship/"),
    ("binary", "scratch/binary-reader-xdk/generated", "libultraship/"),
    ("audio", "scratch/audio-xdk/generated/include", "libultraship/include/"),
    ("input", "scratch/input-xdk/source", ""),
    ("controllers", "scratch/controllers-xdk/generated", "libultraship/"),
    ("widgets", "scratch/gui-widgets-xdk/generated", "libultraship/"),
    ("gui", "scratch/gui-xdk/overlay", ""),
    ("context", "scratch/context-xdk/overlay", ""),
    ("input-editor", "scratch/input-editor-xdk/overlay", ""),
    ("libultra", "scratch/libultra-xdk/generated", "libultraship/"),
    ("postprocess", "scratch/postprocess-xdk/generated", "libultraship/"),
    ("fast-resources", "scratch/fast-resources-xdk/generated", "libultraship/"),
    ("port", "scratch/port-xdk/composed-overlay", ""),
    ("hires", "scratch/hires-xdk/overlay", ""),
]


def choose(name, candidates):
    owners = {c["owner"] for c in candidates}
    if len({c["sha256"] for c in candidates}) == 1:
        return candidates[-1]
    wanted = None
    allowed = set()
    if name.startswith("port/hires/"):
        wanted = "hires"
        allowed = {"hires", "port"}
    elif name.startswith("port/"):
        wanted = "port"
        allowed = {"port", "startup", "endian"}
    elif name == "libultraship/src/ship/Context.cpp":
        wanted = "context"
        allowed = {"context", "startup"}
    elif name in (
        "libultraship/include/ship/Context.h",
        "libultraship/include/ship/window/Window.h",
        "libultraship/src/ship/audio/Audio.cpp",
    ):
        wanted = "config"
        allowed = {"config", "gui"}
    elif name in (
        "libultraship/include/fast/Fast3dWindow.h",
        "libultraship/include/fast/FastMouseStateManager.h",
    ):
        wanted = "gui"
        allowed = {"gui", "fast3d"}
    elif name == "libultraship/src/ship/window/Window.cpp":
        wanted = "gui"
        allowed = {"gui", "config"}
    elif name.startswith(
        (
            "libultraship/src/ship/controller/",
            "libultraship/include/ship/controller/",
            "libultraship/src/libultraship/controller/",
        )
    ):
        wanted = "controllers"
        allowed = {"controllers", "input"}
    elif name.startswith(
        ("libultraship/include/fast/backends/", "libultraship/include/fast/postprocess/")
    ):
        wanted = "fast3d"
        allowed = {"fast3d", "graphics"}
    if wanted not in owners or not owners.issubset(allowed):
        raise ValueError(
            "Unknown ownership conflict: " + name + " [" + ", ".join(sorted(owners)) + "]"
        )
    return next(c for c in candidates if c["owner"] == wanted)


def overlays(missing):
    files = {}
    for owner, location, prefix in PROVIDERS:
        directory = ROOT / location
        if not directory.is_dir():
            missing.append({"provider": owner, "path": location})
            continue
        for source in sorted(directory.rglob("*")):
            if not source.is_file() or source.suffix.lower() not in SOURCE_EXT:
                continue
            name = prefix + source.relative_to(directory).as_posix()
            if owner == "port" and not name.startswith("port/"):
                # Extra non-LUS headers are allowed, never stale composed LUS.
                if name.startswith("libultraship/") or source.suffix not in (
                    ".h",
                    ".hpp",
                    ".inl",
                    ".inc",
                ):
                    continue
                # Canonical game/endian providers already supply their headers.
                if name.startswith("decomp/"):
                    continue
            if owner == "graphics" and not name.startswith("libultraship/include/fast/"):
                continue
            files.setdefault(name, []).append(
                {"owner": owner, "input": relative(source), "sha256": digest(source)}
            )
    for stem in ("AudioPlayer", "SoundMatrixDecoder"):
        source = ROOT / ("scratch/audio-xdk/generated/" + stem + ".cpp")
        if not source.is_file():
            missing.append({"provider": "audio", "path": relative(source)})
            continue
        name = "libultraship/src/ship/audio/" + stem + ".cpp"
        files[name] = [{"owner": "audio", "input": relative(source), "sha256": digest(source)}]
    result = {}
    decisions = []
    for name, candidates in sorted(files.items()):
        selected = choose(name, candidates)
        result[name] = selected
        if len(candidates) > 1:
            decisions.append(
                {"path": name, "selected_owner": selected["owner"], "candidates": candidates}
            )
    return result, decisions


# Explicit production sources. No discovery glob can turn a fixture/donor into
# application code. The source inventory is reviewable before any link occurs.
PLATFORM_SOURCES = [
    "platform/xbox360/environment.cpp",
    "platform/xbox360/math_constants.cpp",
    "platform/xbox360/input/window_input.cpp",
    "platform/xbox360/audio/shipyard_audio_services.cpp",
    "platform/xbox360/imgui/platform_adapter.cpp",
    "platform/xbox360/imgui/gui_startup.cpp",
    "platform/xbox360/graphics/window_xenos.cpp",
    "platform/xbox360/graphics/shader_provider.cpp",
    "platform/xbox360/graphics/api.cpp",
    "platform/xbox360/graphics/shipyard_services.cpp",
    "platform/xbox360/graphics/shader_resources.cpp",
    "platform/xbox360/graphics/shader_cache_adapter.cpp",
    "platform/xbox360/graphics/screenshot.cpp",
    "platform/xbox360/cpp-compat/startup/runtime.cpp",
    "platform/xbox360/runtime/diagnostics_adapter.cpp",
    "platform/xbox360/runtime/clock_adapter.cpp",
    "platform/xbox360/runtime/diagnostic_file_adapter.cpp",
    "platform/xbox360/runtime/shader_worker_adapter.cpp",
    "platform/xbox360/runtime/perf_trace.cpp",
    "platform/xbox360/runtime/storage_adapter.cpp",
    "scratch/prism-xdk/prism/ast.cpp",
    "scratch/prism-xdk/prism/lexer.cpp",
    "scratch/prism-xdk/prism/processor.cpp",
    "scratch/prism-xdk/prism/utils/gv.cpp",
    "scratch/prism-xdk/prism/utils/invoke.c",
    "scratch/prism-xdk/shader_builder.cpp",
    "scratch/imgui-xdk/source/imgui.cpp",
    "scratch/imgui-xdk/source/imgui_draw.cpp",
    "scratch/imgui-xdk/source/imgui_tables.cpp",
    "scratch/imgui-xdk/source/imgui_widgets.cpp",
    "scratch/imgui-xdk/source/imgui_demo.cpp",
    "scratch/stb-xdk/stb_impl.cpp",
    "upstream/dependencies/tinyxml2/tinyxml2.cpp",
]

EXTERNAL_HEADERS = [
    "platform/xbox360",
    "scratch/graphics-xdk/include",
    "scratch/logging-xdk/core-include",
    "scratch/logging-xdk/include",
    "scratch/imgui-xdk/source",
    "scratch/thread-pool-xdk",
    "scratch/json-xdk/backend-generated",
    "scratch/libzip-xdk/generated",
    "scratch/prism-xdk/prism",
    "scratch/generated/include",
    "scratch/generated/css_icons",
    "scratch/generated/port/resource",
    "upstream/dependencies/fmt-xdk/fmt",
    "upstream/dependencies/stb",
    "upstream/dependencies/tinyxml2",
]
EXTRA_HEADERS = ["scratch/prism-xdk/shader_constants.h", "scratch/config-xdk/cvars.h"]
INCLUDED_SOURCES = ["scratch/json-xdk/backend-generated/json/generated/ordered_json.cpp"]


def external_sources(missing):
    files = {}
    for name in (
        "platform/xbox360/cpp-compat/fast3d/unit_color.h",
        "platform/xbox360/cpp-compat/fast3d/rdp_value_init.h",
        "platform/xbox360/cpp-compat/fast3d/fp_rounding.h",
        "platform/xbox360/cpp-compat/fast3d/command_stack.h",
        "platform/xbox360/cpp-compat/fast3d/dispatch_owner.h",
        "platform/xbox360/cpp-compat/fast3d/shade_cache.h",
        "platform/xbox360/cpp-compat/fast3d/triangle_pipeline.h",
        "platform/xbox360/cpp-compat/port/timing.h",
        "platform/xbox360/cpp-compat/port/bounds_gap.h",
        "platform/xbox360/imgui/platform_frame.cpp",
        "platform/xbox360/cpp-compat/prism/compat.h",
        "platform/xbox360/cpp-compat/binary/compat.h",
        "platform/xbox360/cpp-compat/value-types/common.h",
        "platform/xbox360/cpp-compat/value-types/optional.h",
        "scratch/value-types/include/xbox_compat/common.h",
        "scratch/value-types/include/xbox_compat/optional.h",
        "scratch/value-types/include/xbox_compat/variant.h",
    ):
        stale = OUT / "source" / name
        if stale.is_file():
            stale.unlink()
    for location in EXTERNAL_HEADERS:
        directory = ROOT / location
        if not directory.is_dir():
            missing.append({"provider": "headers", "path": location})
            continue
        for source in sorted(directory.rglob("*")):
            if not source.is_file() or source.suffix.lower() not in SOURCE_EXT - {".c", ".cpp"}:
                continue
            name = relative(source)
            if source.relative_to(directory).parts[:2] == ("cpp-compat", "json"):
                continue
            if any(
                part in ("donor", "tests", "python", "reference", "__pycache__")
                for part in source.relative_to(directory).parts
            ):
                continue
            files[name] = source
    # fmt's header-only implementation includes format.cc literally.
    for name in (
        PLATFORM_SOURCES
        + EXTRA_HEADERS
        + INCLUDED_SOURCES
        + ["upstream/dependencies/fmt-xdk/fmt/format.cc"]
    ):
        source = ROOT / name
        if not source.is_file():
            missing.append({"provider": "production source/header", "path": name})
        else:
            files[name] = source
    records = []
    for name, source in sorted(files.items()):
        content = relocate_platform_includes(source.read_bytes())
        text = re.sub(rb"^#line[^\n]*\n", b"", content, flags=re.M)
        if source.suffix in (".h", ".hpp") and starts_with_pragma_once(text):
            content = b"#pragma once\n" + content
        target = OUT / "source" / name
        stable(target, content)
        records.append(
            {
                "input": name,
                "input_sha256": digest(source),
                "output": relative(target),
                "output_sha256": digest(target),
            }
        )
    return records


def game_objects(missing):
    manifest = json.loads((ROOT / "scratch/game-xdk/source-manifest.json").read_text())
    audit = json.loads((ROOT / "scratch/game-xdk/compile-audit.json").read_text())
    if not audit.get("passed") or audit["selected"] != len(manifest["sources"]):
        raise ValueError("Complete audited game C object set required")
    expected = {entry["path"]: entry for entry in manifest["sources"]}
    records = {entry["path"]: entry for entry in audit["results"]}
    if set(expected) != set(records):
        raise ValueError("Game source manifest and compiled object set differ")
    result = []
    for name, entry in sorted(expected.items()):
        record = records[name]
        if (
            digest(UP / name) != entry["sha256"]
            or record["sha256"] != entry["sha256"]
            or record["compile_exit"] != 0
        ):
            raise ValueError("Game source/audit drift: " + name)
        if name == "port/port_log.c":
            continue
        source = ROOT / record["object"]
        if not source.is_file():
            missing.append({"provider": "audited game object", "path": relative(source)})
            continue
        if digest(source) != record["object_sha256"]:
            raise ValueError("Audited game object changed: " + name)
        target = OUT / "game-objects" / source.name
        stable(target, source.read_bytes())
        result.append(
            {
                "source": name,
                "input": relative(source),
                "input_sha256": digest(source),
                "object": relative(target),
                "compile_command": record["compile_command"],
            }
        )
    return set(expected), result


def include_paths():
    root = "$(SmashSourceRoot)"
    names = [
        "BattleShip",
        "BattleShip/port",
        "BattleShip/decomp/src",
        "BattleShip/debug_tools",
        "BattleShip/libultraship/include",
        "BattleShip/libultraship/src",
        "scratch/generated/include",
        "scratch/generated/css_icons",
        "scratch/generated/port/resource",
        "scratch/config-xdk",
        "scratch/graphics-xdk/include",
        "scratch/logging-xdk/core-include",
        "scratch/logging-xdk/include",
        "scratch/imgui-xdk/source",
        "platform/xbox360/imgui",
        "platform/xbox360/graphics",
        "platform/xbox360/input",
        "platform/xbox360/runtime",
        "platform/xbox360/audio",
        "platform/xbox360/cpp-compat",
        "platform/xbox360/cpp-compat/prism",
        "platform/xbox360",
        "scratch/prism-xdk",
        "scratch/imgui-xdk",
        "scratch/json-xdk/backend-generated",
        "upstream/dependencies/stb",
        "upstream/dependencies/tinyxml2",
        "upstream/dependencies/fmt-xdk",
        "scratch/thread-pool-xdk",
        "platform/xbox360/cpp-compat/thread-pool",
        "platform/xbox360/cpp-compat/async",
        "scratch/libzip-xdk/generated",
    ]
    return [root + name.replace("/", "\\") for name in names] + [
        "$(ShipyardRoot)",
        "$(ShipyardRoot)\\sources",
        "$(ShipyardRoot)\\sources\\value_types",
        "$(ShipyardRoot)\\sources\\json\\include",
        "$(ShipyardRoot)\\sources\\graphics",
        "$(ShipyardRoot)\\sources\\imgui",
    ]


def project(name, items, game=()):
    root = ET.Element("{" + XML + "}Project", {"DefaultTargets": "Build", "ToolsVersion": "4.0"})
    group = node(root, "ItemGroup", Label="ProjectConfigurations")
    cfg = node(group, "ProjectConfiguration", Include="Release|Xbox 360")
    node(cfg, "Configuration", "Release")
    node(cfg, "Platform", "Xbox 360")
    group = node(root, "PropertyGroup", Label="Globals")
    node(
        group,
        "ProjectGuid",
        "{4E7FDB28-6743-4C85-9236-00000000000" + ("1" if name == "Smash360" else "2") + "}",
    )
    node(group, "Keyword", "Xbox360Proj")
    node(group, "RootNamespace", name)
    node(root, "Import", Project="$(VCTargetsPath)\\Microsoft.Cpp.Default.props")
    group = node(root, "PropertyGroup", Label="Configuration")
    node(group, "ConfigurationType", "Application" if name == "Smash360" else "StaticLibrary")
    node(group, "PlatformToolset", "2010-01")
    node(group, "CharacterSet", "MultiByte")
    node(root, "Import", Project="$(VCTargetsPath)\\Microsoft.Cpp.props")
    group = node(root, "PropertyGroup")
    node(group, "SmashNativeRoot", "$(ProjectDir)..\\..\\scratch\\application-xdk\\native\\")
    node(group, "SmashSourceRoot", "$(SmashNativeRoot)source\\")
    node(group, "ShipyardRoot", str(PLATFORM_BASE) + "\\", Condition="'$(ShipyardRoot)'==''")
    node(group, "SmashFullProfiling", "0", Condition="'$(SmashFullProfiling)'==''")
    node(group, "OutDir", "$(SmashNativeRoot)build\\")
    node(group, "OutputPath", "$(OutDir)")
    node(group, "IntDir", "$(SmashNativeRoot)obj\\" + name + "\\")
    node(group, "TargetName", name)
    node(group, "LinkIncremental", "false")
    node(group, "TargetExt", ".exe" if name == "Smash360" else ".lib")
    node(group, "TargetPath", "$(OutDir)$(TargetName)$(TargetExt)")
    node(group, "TargetDir", "$(OutDir)")
    # Xbox targets derive TargetPath from this property, including static libs.
    # Set it after Cpp.props so its earlier default cannot retain Release\.
    node(group, "OutputFile", "$(OutDir)$(TargetName)$(TargetExt)")
    if name == "Smash360":
        node(group, "ImageXexOutput", "$(OutDir)Smash360.xex")
    defs = node(root, "ItemDefinitionGroup")
    cl = node(defs, "ClCompile")
    for key, value in [
        ("PrecompiledHeader", "NotUsing"),
        ("CompileAs", "CompileAsCpp"),
        ("Optimization", "MaxSpeed"),
        ("RuntimeLibrary", "MultiThreaded"),
        ("ExceptionHandling", "Sync"),
        ("RuntimeTypeInfo", "true"),
        ("DebugInformationFormat", "ProgramDatabase"),
        *CXX_MSBUILD,
        ("WarningLevel", "Level3"),
    ]:
        node(cl, key, value)
    definitions = [
        "_XBOX",
        "XBOX",
        "SMASH_XBOX360",
        "NDEBUG",
        "NOMINMAX",
        "_CRT_SECURE_NO_WARNINGS",
        "_USE_MATH_DEFINES",
        "DISABLE_SCRIPTING",
        "SPDLOG_ACTIVE_LEVEL=0",
        "SMASH360_ENABLE_FULL_PROFILING=$(SmashFullProfiling)",
    ]
    definitions += application_definitions() if name == "Smash360" else ["F3DEX_GBI_2=1"]
    node(cl, "PreprocessorDefinitions", ";".join(definitions) + ";%(PreprocessorDefinitions)")
    node(
        cl,
        "AdditionalIncludeDirectories",
        ";".join(include_paths()) + ";%(AdditionalIncludeDirectories)",
    )
    node(
        cl,
        "ForcedIncludeFiles",
        "$(SmashSourceRoot)scratch\\config-xdk\\cvars.h;%(ForcedIncludeFiles)",
    )
    if name == "Smash360":
        link = node(defs, "Link")
        node(link, "OutputFile", "$(OutDir)Smash360.exe")
        libraries = [
            "$(OutDir)Libultraship360.lib",
            "$(SmashNativeRoot)libraries\\zip.lib",
            "$(SmashNativeRoot)libraries\\zlib.lib",
            "xboxkrnl.lib",
            "xapilib.lib",
            "d3d9.lib",
            "d3dx9.lib",
            "xgraphics.lib",
            "xaudio2.lib",
            "xmcore.lib",
            "xnet.lib",
        ]
        node(link, "AdditionalDependencies", ";".join(libraries) + ";%(AdditionalDependencies)")
        for key, value in [
            ("GenerateDebugInformation", "true"),
            ("GenerateMapFile", "true"),
            ("StackReserveSize", "4194304"),
            ("StackCommitSize", "4194304"),
            ("OptimizeReferences", "true"),
        ]:
            node(link, key, value)
        image = node(defs, "ImageXex")
        node(image, "TitleId", "0x534D3601")
        node(image, "OutputFile", "$(OutDir)Smash360.xex")
    else:
        node(node(defs, "Lib"), "OutputFile", "$(OutDir)Libultraship360.lib")
    group = node(root, "ItemGroup")
    for index, item in enumerate(items):
        include = (
            "$(ShipyardRoot)\\" + item["shipyard_source"].replace("/", "\\")
            if "shipyard_source" in item
            else "$(SmashSourceRoot)" + item["staged"].replace("/", "\\")
        )
        unit = node(group, "ClCompile", Include=include)
        node(unit, "ObjectFileName", "$(IntDir)%04d_%s.obj" % (index, Path(item["path"]).stem))
        if item["path"].endswith(".c"):
            node(unit, "CompileAs", "CompileAsC")
        # Bounded real SDK project smoke compilation, without touching or
        # excluding any production source in the normal build.
        node(
            unit,
            "ExcludedFromBuild",
            "true",
            Condition="'$(SmashCompileOnly)'!='' and '$(SmashCompileOnly)'!='" + item["path"] + "'",
        )
    if name == "Smash360":
        group = node(root, "ItemGroup")
        for record in game:
            node(
                group,
                "Object",
                Include="$(SmashNativeRoot)game-objects\\" + Path(record["object"]).name,
            )
        group = node(root, "ItemGroup")
        reference = node(group, "ProjectReference", Include="Libultraship360.vcxproj")
        node(reference, "Project", "{4E7FDB28-6743-4C85-9236-000000000002}")
        node(reference, "LinkLibraryDependencies", "false")
        node(reference, "UseLibraryDependencyInputs", "false")
    node(root, "Import", Project="$(VCTargetsPath)\\Microsoft.Cpp.targets")
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"


def prepare():
    OUT.mkdir(parents=True, exist_ok=True)
    runpy.run_path(str(ROOT / "tools/application_source_manifest.py"))["main"]()
    app = json.loads((OUT.parent / "source-manifest.json").read_text())
    missing = []
    owners, decisions = overlays(missing)
    game_names, objects = game_objects(missing)
    external = external_sources(missing)
    libraries = []
    for name in ("zip", "zlib"):
        source = ROOT / ("scratch/libzip-xdk/xdk/" + name + ".lib")
        if not source.is_file():
            missing.append({"provider": "native compression library", "path": relative(source)})
        else:
            target = OUT / "libraries" / source.name
            stable(target, source.read_bytes())
            libraries.append(
                {
                    "input": relative(source),
                    "input_sha256": digest(source),
                    "output": relative(target),
                    "output_sha256": digest(target),
                }
            )
    selected = [item for item in app["sources"] if item["selected"]]
    # Every selected input remains represented, either by its audited game
    # object or by a project compile item. No compilation-driven exclusions.
    units = [
        item
        for item in selected
        if item["path"] not in game_names or item["path"] == "port/port_log.c"
    ]
    overlay = OUT / "composed-overlay"
    for name, record in owners.items():
        stable(overlay / name, (ROOT / record["input"]).read_bytes())
    # Stale provider files are never reused after the owner's inventory changes.
    index = overlay / ".files.json"
    if index.is_file():
        for name in set(json.loads(index.read_text())) - set(owners):
            stale = (overlay / name).resolve()
            if not stale.is_relative_to(overlay.resolve()):
                raise ValueError("Invalid prior overlay path")
            if stale.is_file():
                stale.unlink()
    json_file(index, sorted(owners))
    report = {
        "scope": (
            "Physical production source composition; compilation/link/execution not established"
        ),
        "missing": missing,
        "owners": owners,
        "decisions": decisions,
        "game_objects": objects,
        "external_sources": external,
        "libraries": libraries,
        "game_manifest_count": len(game_names),
        "direct_game_object_count": len(objects),
        "duplicate_replacement": (
            "port/port_log.c is compiled once by application; audited C object excluded"
        ),
        "lazy_library_requirement": (
            "LUS os_vi/os_mesg must remain unselected; game n64_stubs owns VI/messages"
        ),
        "known_excluded_fixture": (
            "scratch/prism-xdk/test_shader_features.cpp duplicates real interpreter decoder"
        ),
        "optional_features_undefined": ["INCLUDE_MPQ_SUPPORT", "LUS_POSTPROCESS_TRANSPILER"],
        "donor_project_structure": {
            "source": "D:/Projects/SoH360/platform/xbox360/SoH360.vcxproj",
            "sha256": "b08adffb5f464e7560cdadcfe14ca205f0f4a06897d9813702e2f62e8576754b",
            "build_driver_sha256": (
                "0dae485d01f0bcd96b85dcd6a347e650beed1d611ad17f9c90fec88765e6975f"
            ),
            "note": "Structure/SDK libraries/4 MiB stack only; no donor game source items imported",
        },
    }
    if missing:
        json_file(OUT / "assembly-report.json", report)
        raise ValueError("Missing providers: " + ", ".join(record["path"] for record in missing))
    staged = stage_sources(UP, TREE, [item["path"] for item in units], overlays=[overlay])
    for entry in staged:
        target = TREE / entry["relative_path"]
        stable(target, relocate_platform_includes(target.read_bytes()))
        entry["generated_sha256"] = digest(target)
    lookup = {entry["relative_path"]: entry for entry in staged}
    app_items = []
    lus_items = []
    for item in units:
        name = item["path"]
        entry = {
            "path": name,
            "staged": "BattleShip/" + name,
            "provider": owners.get(name, {}).get("owner", "pinned upstream"),
            "input": lookup[name]["input"],
            "sha256": lookup[name]["generated_sha256"],
        }
        (lus_items if name.startswith("libultraship/") else app_items).append(entry)
    for name in PLATFORM_SOURCES:
        app_items.append(
            {
                "path": name,
                "staged": name,
                "provider": "explicit production platform source",
                "input": name,
                "sha256": digest(OUT / "source" / name),
            }
        )
    filesystem = "sources/filesystem/filesystem.cpp"
    app_items.append(
        {
            "path": "shipyard/" + filesystem,
            "shipyard_source": filesystem,
            "provider": "Shipyard direct source",
            "input": "platform_base:" + filesystem,
            "sha256": digest(PLATFORM_BASE / filesystem),
        }
    )
    json_backend = "sources/json/json.cpp"
    app_items.append(
        {
            "path": "shipyard/" + json_backend,
            "shipyard_source": json_backend,
            "provider": "Shipyard direct source",
            "input": "platform_base:" + json_backend,
            "sha256": digest(PLATFORM_BASE / json_backend),
        }
    )
    native = "sources/async/native.cpp"
    app_items.append(
        {
            "path": "shipyard/" + native,
            "shipyard_source": native,
            "provider": "Shipyard direct source",
            "input": "platform_base:" + native,
            "sha256": digest(PLATFORM_BASE / native),
        }
    )
    clock = "sources/clock/chrono.cpp"
    app_items.append(
        {
            "path": "shipyard/" + clock,
            "shipyard_source": clock,
            "provider": "Shipyard direct source",
            "input": "platform_base:" + clock,
            "sha256": digest(PLATFORM_BASE / clock),
        }
    )
    n64_clock = "sources/libultra/clock.cpp"
    app_items.append(
        {
            "path": "shipyard/" + n64_clock,
            "shipyard_source": n64_clock,
            "provider": "Shipyard direct source",
            "input": "platform_base:" + n64_clock,
            "sha256": digest(PLATFORM_BASE / n64_clock),
        }
    )
    storage = "sources/storage/device.cpp"
    app_items.append(
        {
            "path": "shipyard/" + storage,
            "shipyard_source": storage,
            "provider": "Shipyard direct source",
            "input": "platform_base:" + storage,
            "sha256": digest(PLATFORM_BASE / storage),
        }
    )
    atomic_file = "sources/storage/atomic_file.cpp"
    app_items.append(
        {
            "path": "shipyard/" + atomic_file,
            "shipyard_source": atomic_file,
            "provider": "Shipyard direct source",
            "input": "platform_base:" + atomic_file,
            "sha256": digest(PLATFORM_BASE / atomic_file),
        }
    )
    pool = "sources/audio/PcmBufferPool.cpp"
    app_items.append(
        {
            "path": "shipyard/" + pool,
            "shipyard_source": pool,
            "provider": "Shipyard direct source",
            "input": "platform_base:" + pool,
            "sha256": digest(PLATFORM_BASE / pool),
        }
    )
    sink = "sources/audio/XAudio2AudioPlayer.cpp"
    app_items.append(
        {
            "path": "shipyard/" + sink,
            "shipyard_source": sink,
            "provider": "Shipyard direct source",
            "input": "platform_base:" + sink,
            "sha256": digest(PLATFORM_BASE / sink),
        }
    )
    crt = "sources/crt/format.cpp"
    app_items.append(
        {
            "path": "shipyard/" + crt,
            "shipyard_source": crt,
            "provider": "Shipyard direct source",
            "input": "platform_base:" + crt,
            "sha256": digest(PLATFORM_BASE / crt),
        }
    )
    shader = "sources/graphics/shader_lower.cpp"
    app_items.append(
        {
            "path": "shipyard/" + shader,
            "shipyard_source": shader,
            "provider": "Shipyard direct source",
            "input": "platform_base:" + shader,
            "sha256": digest(PLATFORM_BASE / shader),
        }
    )
    shader_provider = "sources/graphics/shader_provider.cpp"
    app_items.append(
        {
            "path": "shipyard/" + shader_provider,
            "shipyard_source": shader_provider,
            "provider": "Shipyard direct source",
            "input": "platform_base:" + shader_provider,
            "sha256": digest(PLATFORM_BASE / shader_provider),
        }
    )
    vertex_transform = "sources/fast3d/vertex_transform.cpp"
    app_items.append(
        {
            "path": "shipyard/" + vertex_transform,
            "shipyard_source": vertex_transform,
            "provider": "Shipyard direct source",
            "input": "platform_base:" + vertex_transform,
            "sha256": digest(PLATFORM_BASE / vertex_transform),
        }
    )
    clip_quantize = "sources/fast3d/clip_quantize.cpp"
    app_items.append(
        {
            "path": "shipyard/" + clip_quantize,
            "shipyard_source": clip_quantize,
            "provider": "Shipyard direct source",
            "input": "platform_base:" + clip_quantize,
            "sha256": digest(PLATFORM_BASE / clip_quantize),
        }
    )
    xenos = "sources/xenos/core.cpp"
    app_items.append(
        {
            "path": "shipyard/" + xenos,
            "shipyard_source": xenos,
            "provider": "Shipyard direct source",
            "input": "platform_base:" + xenos,
            "sha256": digest(PLATFORM_BASE / xenos),
        }
    )
    presentation = "sources/presentation/xenos_surface.cpp"
    app_items.append(
        {
            "path": "shipyard/" + presentation,
            "shipyard_source": presentation,
            "provider": "Shipyard direct source",
            "input": "platform_base:" + presentation,
            "sha256": digest(PLATFORM_BASE / presentation),
        }
    )
    shader_cache = "sources/xenos/shader_cache.cpp"
    app_items.append(
        {
            "path": "shipyard/" + shader_cache,
            "shipyard_source": shader_cache,
            "provider": "Shipyard direct source",
            "input": "platform_base:" + shader_cache,
            "sha256": digest(PLATFORM_BASE / shader_cache),
        }
    )
    shader_worker = "sources/io/shader_worker.cpp"
    app_items.append(
        {
            "path": "shipyard/" + shader_worker,
            "shipyard_source": shader_worker,
            "provider": "Shipyard direct source",
            "input": "platform_base:" + shader_worker,
            "sha256": digest(PLATFORM_BASE / shader_worker),
        }
    )
    diagnostics_queue = "sources/diagnostics/queue.cpp"
    app_items.append(
        {
            "path": "shipyard/" + diagnostics_queue,
            "shipyard_source": diagnostics_queue,
            "provider": "Shipyard direct source",
            "input": "platform_base:" + diagnostics_queue,
            "sha256": digest(PLATFORM_BASE / diagnostics_queue),
        }
    )
    imgui = "sources/imgui/imgui_xenos.cpp"
    app_items.append(
        {
            "path": "shipyard/" + imgui,
            "shipyard_source": imgui,
            "provider": "Shipyard direct source",
            "input": "platform_base:" + imgui,
            "sha256": digest(PLATFORM_BASE / imgui),
        }
    )
    platform_frame = "sources/imgui/platform_frame.cpp"
    app_items.append(
        {
            "path": "shipyard/" + platform_frame,
            "shipyard_source": platform_frame,
            "provider": "Shipyard direct source",
            "input": "platform_base:" + platform_frame,
            "sha256": digest(PLATFORM_BASE / platform_frame),
        }
    )
    for input_source in ("sources/input/physical.cpp", "sources/input/xinput.cpp"):
        app_items.append(
            {
                "path": "shipyard/" + input_source,
                "shipyard_source": input_source,
                "provider": "Shipyard direct source",
                "input": "platform_base:" + input_source,
                "sha256": digest(PLATFORM_BASE / input_source),
            }
        )
    report.update(
        staged_sources=staged, application_items=app_items, libultraship_items=lus_items, missing=[]
    )
    json_file(OUT / "assembly-report.json", report)
    json_file(
        OUT / "project-items.json",
        {"Smash360": app_items, "Libultraship360": lus_items, "direct_game_objects": objects},
    )
    for name, items in [("Smash360", app_items), ("Libultraship360", lus_items)]:
        stable(PLATFORM / (name + ".vcxproj"), project(name, items, objects))
    print(
        "Staged %d application/platform TUs, %d LUS lazy-library TUs, %d direct game objects"
        % (len(app_items), len(lus_items), len(objects))
    )
    return report


def verify():
    report = json.loads((OUT / "assembly-report.json").read_text())
    if report["missing"]:
        raise ValueError("Assembly has missing providers")
    for record in report["staged_sources"]:
        if digest(TREE / record["relative_path"]) != record["generated_sha256"]:
            raise ValueError("Staged source changed: " + record["relative_path"])
    for record in report["external_sources"] + report["libraries"]:
        if digest(ROOT / record["output"]) != record["output_sha256"]:
            raise ValueError("Staged provider changed: " + record["output"])
    for item in report["application_items"]:
        if (
            "shipyard_source" in item
            and digest(PLATFORM_BASE / item["shipyard_source"]) != item["sha256"]
        ):
            raise ValueError("Shipyard direct source changed: " + item["shipyard_source"])
    for record in report["game_objects"]:
        if digest(ROOT / record["object"]) != record["input_sha256"]:
            raise ValueError("Staged game object changed: " + record["source"])
    print("Verified immutable physical compiler inputs and audited direct game objects")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    try:
        verify() if args.verify else prepare()
    except (OSError, ValueError) as error:
        json_file(OUT / "assembly-error.json", {"assembly_succeeded": False, "error": str(error)})
        print(str(error), file=sys.stderr)
        sys.exit(1)
