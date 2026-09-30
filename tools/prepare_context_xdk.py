"""Compose the actual startup Context and its unclaimed lifecycle/C bridge closure."""

from pathlib import Path
import argparse, hashlib, json, re, runpy, subprocess, sys
from platform_base import resolve as resolve_platform_base

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
UP = ROOT / "upstream/BattleShip"
OUT = ROOT / "scratch/context-xdk"
BASE = ROOT / "platform/xbox360/cpp-compat/context"
PRISM = runpy.run_path(str(ROOT / "tools/prepare_prism_xdk.py"))
LOWER = runpy.run_path(str(ROOT / "platform/xbox360/cpp-compat/controllers/lowering.py"))
STAGE = runpy.run_path(str(ROOT / "platform/xbox360/game-compat/source_tree.py"))["stage_sources"]


def once(t, a, b):
    if t.count(a) != 1:
        raise ValueError("Context anchor drift " + a[:90])
    return t.replace(a, b)


def transform(relative, t):
    direct = []
    if relative.endswith("/Context.cpp"):
        # Init must publish the window while renderer/GUI initialization runs,
        # but a failed Init must not leave a partially initialized window for
        # Context's destructor to query when saving dimensions/fullscreen state.
        t = once(
            t,
            "    GetWindow()->Init();",
            "    try {\n        GetWindow()->Init();\n    } catch (...) {\n       "
            " mWindow.reset();\n        throw;\n    }",
        )
        direct = [
            "ship/config/Config.h",
            "ship/resource/ResourceManager.h",
            "ship/debug/Console.h",
            "ship/window/Window.h",
            "ship/window/gui/Gui.h",
            "spdlog/spdlog.h",
        ]
        direct.append("input/physical.h")
        t = once(
            t,
            "    mControlDeck = nullptr;",
            "#ifdef _XBOX\n    if (mControlDeck) mControlDeck->StopAllRumble();\n   "
            " ShipyardInput_StopPhysicalRumble();\n#endif\n    mControlDeck = nullptr;",
        )
    elif relative.endswith("consolevariablebridge.cpp"):
        direct = ["ship/config/ConsoleVariable.h"]
    elif relative.endswith("eventsbridge.cpp"):
        direct = ["ship/events/EventSystem.h"]
    elif relative.endswith("resourcebridge.cpp"):
        direct = [
            "ship/resource/ResourceManager.h",
            "ship/resource/ResourceLoader.h",
            "ship/resource/archive/ArchiveManager.h",
            "fast/resource/type/Texture.h",
            "spdlog/spdlog.h",
        ]
    elif relative.endswith("/gfxbridge.cpp"):
        t = once(
            t,
            "= static_pointer_cast<Fast::Fast3dWindow>",
            "= std::static_pointer_cast<Fast::Fast3dWindow>",
        )
    elif relative.endswith("/FileDropMgr.h"):
        t = (
            once(
                t,
                "FileDropMgr() = default;",
                "FileDropMgr() : mPath(nullptr),mFileDropped(false) {}",
            )
            .replace("mPath = nullptr;", "mPath;")
            .replace("mFileDropped = false;", "mFileDropped;")
        )
    elif relative.endswith("/FileDropMgr.cpp"):
        t = once(t, "#include <Windows.h>", "#if !defined(_XBOX)\n#include <Windows.h>")
        t = once(t, "#include <dbghelp.h>", "#include <dbghelp.h>\n#endif")
        t = once(
            t,
            "#elif _MSC_VER",
            '#elif defined(_XBOX)\n    SPDLOG_WARN("Trying to register {}. Already'
            ' registered.",funcAddr);\n#elif _MSC_VER',
        )
        direct = ["ship/window/gui/Gui.h", "ship/window/gui/GameOverlay.h"]
    elif relative.endswith("/EventSystem.h"):
        t = once(t, "  public:\n", "  public:\n    EventSystem() : mInternalEventID(0) {}\n")
        t = once(t, "EventID mInternalEventID = 0;", "EventID mInternalEventID;")
    elif relative.endswith("/EventSystem.cpp"):
        t = once(
            t,
            'this->mEventRegistry[id] = EventRegistration{ .Name = name == nullptr ? "Unknown" :'
            " name };",
            'EventRegistration registration;\n    registration.Name = name == nullptr ? "Unknown" :'
            " name;\n    this->mEventRegistry[id] = registration;",
        )
        t = once(
            t,
            "registry.Listeners.push_back({ priority, callback, { file, line, 0 } });",
            "EventListener listener = { priority, callback, { file, line, 0 } };\n   "
            " registry.Listeners.push_back(listener);",
        )
        t = once(
            t,
            "for (auto& [priority, function, _] : registry.Listeners) {\n        function(event);",
            "for (auto& listener : registry.Listeners) {\n        listener.Function(event);",
        )
    elif relative.endswith("/CrashHandler.h"):
        t = t.replace("#if _WIN32", "#if defined(_WIN32) && !defined(_XBOX)").replace(
            "#elif _WIN32", "#elif defined(_WIN32) && !defined(_XBOX)"
        )
        t = (
            t.replace("mCallback = nullptr;", "mCallback;")
            .replace("mOutBuffer = nullptr;", "mOutBuffer;")
            .replace("mOutBuffersize = 0;", "mOutBuffersize;")
            .replace("static constexpr size_t", "static const size_t")
        )
    elif relative.endswith("/CrashHandler.cpp"):
        t = (
            t.replace("#ifdef _WIN32", "#if defined(_WIN32) && !defined(_XBOX)")
            .replace("#elif defined(_WIN32)", "#elif defined(_WIN32) && !defined(_XBOX)")
            .replace("#elif _WIN32", "#elif defined(_WIN32) && !defined(_XBOX)")
        )
        # The actual callback/buffer diagnostics remain; desktop DbgHelp and x86
        # register capture are unavailable on Xbox. No made-up PPC stack walk.
        t = once(
            t,
            "CrashHandler::CrashHandler() {",
            "CrashHandler::CrashHandler() :"
            " mCallback(nullptr),mOutBuffer(nullptr),mOutBuffersize(0) {",
        )
        t = once(
            t,
            "CrashHandler::CrashHandler(CrashHandlerCallback callback) {",
            "CrashHandler::CrashHandler(CrashHandlerCallback callback) :"
            " mCallback(nullptr),mOutBuffer(nullptr),mOutBuffersize(0) {",
        )
    elif relative.endswith("/luslog.cpp"):
        t = once(
            t,
            "auto loc = spdlog::source_loc{ file, line, SPDLOG_FUNCTION };",
            "spdlog::source_loc loc(file,line,SPDLOG_FUNCTION);",
        )
        # This overload is a preformatted message, including arbitrary braces.
        t = once(
            t,
            "spdlog::default_logger_raw()->log(loc, lvl, str);",
            "spdlog::default_logger_raw()->log(loc,lvl,spdlog::string_view_t(str));",
        )
    t = LOWER["syntax"](t, set())
    return (
        '#include "controllers/compiler.h"\n'
        + "".join('#include "' + h + '"\n' for h in direct)
        + t
    )


def prepare():
    locks = json.loads((BASE / "source-lock.json").read_text())
    records = []
    for rel, sha in locks.items():
        original = UP / rel
        if hashlib.sha256(original.read_bytes()).hexdigest() != sha:
            raise ValueError("Context source drift " + rel)
        startup = ROOT / "scratch/startup-xdk/generated" / rel
        source = startup if rel.endswith("/Context.cpp") else original
        if source == startup:
            startup_manifest = json.loads((ROOT / "scratch/startup-xdk/manifest.json").read_text())
            if hashlib.sha256(source.read_bytes()).hexdigest() != startup_manifest["outputs"][rel]:
                raise ValueError("Startup overlay drift")
        target = OUT / "overlay" / rel
        PRISM["mapped"](
            original.as_posix(), transform(rel, source.read_text(encoding="utf-8-sig")), target
        )
        records.append(
            {
                "source": rel,
                "sha256": sha,
                "input": str(source.relative_to(ROOT)),
                "input_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "generated_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            }
        )
    layers = [
        ("scratch/input-editor-xdk/compile-tree", ""),
        ("scratch/resources-xdk/generated/include", "libultraship/include"),
        ("scratch/config-xdk/generated/include", "libultraship/include"),
        ("scratch/gui-widgets-xdk/generated/include", "libultraship/include"),
        ("scratch/controllers-xdk/generated/include", "libultraship/include"),
        ("scratch/gui-xdk/overlay", ""),
        ("scratch/input-editor-xdk/overlay", ""),
        ("scratch/context-xdk/overlay", ""),
    ]
    headers = {}
    support = []
    for name, prefix in layers:
        for path in (ROOT / name).rglob("*.h"):
            headers[(Path(prefix) / path.relative_to(ROOT / name)).as_posix()] = path
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
    for rel in locks:
        if not rel.endswith(".cpp"):
            continue
        target = OUT / "composed" / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((OUT / "overlay" / rel).read_bytes())
    staged = STAGE(
        UP, OUT / "compile-tree", [r for r in locks if r.endswith(".cpp")], [OUT / "composed"]
    )
    (OUT / "manifest.json").write_text(
        json.dumps({"transforms": records, "support": support, "staged": staged}, indent=2) + "\n"
    )


def compile_xdk(only):
    base = json.loads((ROOT / "scratch/input-editor-xdk/compile-report.json").read_text())[
        "command"
    ]
    includes = []
    for arg in base:
        if arg.startswith("/I"):
            includes.append(
                arg.replace(
                    str(ROOT / "scratch/input-editor-xdk/compile-tree"), str(OUT / "compile-tree")
                )
            )
    includes.append("/I" + str(resolve_platform_base(ROOT) / "sources"))
    sdk = Path("C:/Program Files (x86)/Microsoft Xbox 360 SDK")
    results = []
    for rel in json.loads((BASE / "source-lock.json").read_text()):
        if not rel.endswith(".cpp") or (only and Path(rel).stem != only):
            continue
        source = OUT / "compile-tree" / rel
        name = source.stem
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
            + includes
            + ["/Fo" + str(OUT / (name + ".obj")), str(source)]
        )
        p = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
        log = p.stdout + p.stderr
        (OUT / (name + ".log")).write_text(log)
        results.append({"source": rel, "command": cmd, "exit": p.returncode})
        print(name, p.returncode)
        print("\n".join(line for line in log.splitlines() if "error " in line)[:3500])
    (OUT / "compile-report.json").write_text(json.dumps(results, indent=2) + "\n")
    return any(r["exit"] for r in results)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--compile", action="store_true")
    p.add_argument("--only")
    a = p.parse_args()
    prepare()
    if a.compile:
        raise SystemExit(compile_xdk(a.only))
