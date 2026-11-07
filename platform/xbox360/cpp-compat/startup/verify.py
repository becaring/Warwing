"""Native compilation and source-contract verification; no boot simulation."""

from pathlib import Path
import hashlib, json, runpy, subprocess

ROOT = Path(__file__).resolve().parents[4]
import runpy as _shipyard_runpy

SHIPYARD_BASE = _shipyard_runpy.run_path(str(ROOT / "tools/platform_base.py"))["resolve"](ROOT)
OUT = ROOT / "scratch/startup-xdk"
SDK = Path("C:/Program Files (x86)/Microsoft Xbox 360 SDK")


def source_contracts():
    m = runpy.run_path(str(ROOT / "tools/prepare_startup_xdk.py"))
    outputs = m["prepare"]()
    assert outputs == m["prepare"](), "generation not deterministic"
    read = lambda p: (ROOT / "upstream/BattleShip" / p).read_text(encoding="utf-8-sig")
    port = m["transform"]("port/port.cpp", read("port/port.cpp"))
    main = port[port.index("int main(int argc, char* argv[])") :]
    calls = [
        "Smash360Startup::Initialize()",
        "PortInit(argc, argv)",
        "PortGameInit();",
        "PortPushFrame();",
        "PortGameShutdown();",
    ]
    offsets = [main.index(s) for s in calls]
    assert offsets == sorted(offsets)
    normal = main[main.index("\tPortGameShutdown();") : main.index("} catch (const std::exception& e)")]
    assert (
        normal.index("PortGameShutdown();")
        < normal.index("PortShutdown();")
        < normal.index("Smash360Startup::Shutdown();")
    )
    assert "Smash360Startup::RequireArchive(f3d)" in port
    assert "Smash360Startup::RequireArchive(PortLocateFile(SSB64_O2R_NAME))" in port
    assert "#ifdef _XBOX\n    xboxGameStarted = true;\n#endif\n\tPortGameInit();" in port
    context = m["transform"]("libultraship/src/ship/Context.cpp", read("libultraship/src/ship/Context.cpp"))
    assert "if (GetWindow()) GetWindow()->SaveWindowToConfig();" in context
    assert "if (GetConfig()) GetConfig()->Save();" in context
    assert context.count('return "game:\\\\";') == 2
    assert 'warwingsave' not in context
    try:
        m["transform"](
            "port/port.cpp", read("port/port.cpp").replace("int main(int argc, char* argv[]) {", "int renamed() {")
        )
    except ValueError:
        pass
    else:
        raise AssertionError("changed main accepted")
    print("Deterministic source mapping, exact anchors, archive failure and real lifecycle order PASS")


def native_compile():
    includes = [
        ROOT / "scratch/config-xdk/generated/include",
        ROOT / "scratch/resources-xdk/generated/include",
        ROOT / "scratch/logging-xdk/core-include",
        ROOT / "scratch/logging-xdk/include",
        ROOT / "scratch/audio-xdk/generated/include",
        SHIPYARD_BASE,
        SHIPYARD_BASE / 'sources',
        SHIPYARD_BASE / 'sources/json/include',
        ROOT / "platform/xbox360/cpp-compat",
        ROOT / "platform/xbox360",
        ROOT / "upstream/dependencies/fmt-xdk",
        ROOT / "upstream/BattleShip/libultraship/include",
        SDK / "include/xbox",
    ]
    status = {}
    for name, source in [
        ("startup_runtime", ROOT / "platform/xbox360/cpp-compat/startup/runtime.cpp"),
        ("app_paths", OUT / "generated/port/app_paths.cpp"),
        ("port_log", ROOT / "upstream/BattleShip/port/port_log.c"),
    ]:
        folder = OUT / "native" / name
        folder.mkdir(parents=True, exist_ok=True)
        obj = folder / (name + ".obj")
        command = (
            [
                SDK / "bin/win32/cl.exe",
                "/nologo",
                "/c",
                "/TP",
                "/EHsc",
                "/MT",
                "/W4",
                "/D_XBOX",
                "/DNOMINMAX",
                "/DDISABLE_SCRIPTING",
            ]
            + ["/I" + str(p) for p in includes]
            + ["/Fo" + str(obj), source]
        )
        result = subprocess.run(list(map(str, command)), cwd=ROOT, capture_output=True, text=True)
        (folder / "command.json").write_text(json.dumps(list(map(str, command)), indent=2) + "\n")
        (folder / "result.log").write_text(result.stdout + result.stderr)
        status[name] = {"exit": result.returncode, "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
        if result.returncode:
            print(result.stdout + result.stderr)
        else:
            data = obj.read_bytes()
            assert int.from_bytes(data[:2], "little") == 0x1F2
            status[name]["object_sha256"] = hashlib.sha256(data).hexdigest()
        print(name + ": " + ("PowerPC object PASS" if result.returncode == 0 else "FAIL"))
    (OUT / "native-verification.json").write_text(json.dumps(status, indent=2) + "\n")
    assert all(item["exit"] == 0 for item in status.values())


if __name__ == "__main__":
    source_contracts()
    native_compile()
