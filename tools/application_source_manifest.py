"""Evaluate pinned CMake source discovery without configuring desktop dependencies.

Every Xbox exclusion is a reviewed platform capability or a replaced backend.
Compilation failures never remove entries. This is source selection, not proof
that all selected files compile or that platform registrations are complete.
"""

from pathlib import Path
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "upstream/BattleShip"
OUT = ROOT / "scratch/application-xdk"
sys.path.insert(0, str(ROOT / "tools"))
from game_source_manifest import CMAKE_SHA256, manifest as game_manifest


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    original = SOURCE / "CMakeLists.txt"
    if digest(original) != CMAKE_SHA256:
        raise RuntimeError("Pinned application source selection changed")
    OUT.mkdir(parents=True, exist_ok=True)
    cmake = original.read_text(encoding="utf-8")
    block = cmake[cmake.index("file(GLOB_RECURSE SSB64_SRC_PORT") : cmake.index("set(SSB64_DECOMP_SOURCES")]
    # CONFIGURE_DEPENDS changes CMake reconfiguration, not the source set.
    block = block.replace(" CONFIGURE_DEPENDS ", " ")
    collection = OUT / "upstream-selection.txt"
    definitions = [
        "cmake_minimum_required(VERSION 3.24)",
        'set(CMAKE_SYSTEM_NAME "Xbox360")',
        "set(DISABLE_SCRIPTING ON)",
        "set(SSB64_VERSION us)",
        f'set(CMAKE_CURRENT_SOURCE_DIR "{SOURCE.as_posix()}")',
        f'file(WRITE "{collection.as_posix()}" "")',
        # No target compilation occurs in script mode; collect its real inputs.
        "function(source_group)\nendfunction()",
        "function(target_sources target visibility)",
        "  foreach(item IN LISTS ARGN)",
        '    get_filename_component(path "${item}" ABSOLUTE BASE_DIR "${CMAKE_CURRENT_SOURCE_DIR}")',
        f'    file(APPEND "{collection.as_posix()}" "${{path}}\\n")',
        "  endforeach()",
        "endfunction()",
    ]
    cmake_inputs = {str(original.relative_to(ROOT)): digest(original)}
    script_path = OUT / "collect-sources.cmake"
    script_path.write_text(
        "\n".join(definitions + [block, "target_sources(ssb64 PRIVATE ${SSB64_SRC_PORT} ${SSB64_DEBUG_TOOLS})"]) + "\n",
        encoding="utf-8",
    )
    # Relative GLOB expressions in original port CMake resolve against cwd.
    subprocess.run(["cmake", "-P", str(script_path)], cwd=SOURCE, check=True)
    # Included CMake GLOB patterns are relative to CMAKE_CURRENT_SOURCE_DIR only
    # in project mode; script mode uses cwd. Evaluate each LUS list separately
    # in its own source directory so no path is accidentally dropped.
    selected = {Path(p) for p in collection.read_text().splitlines() if Path(p).suffix in (".cpp", ".c")}
    for name in ("ship", "fast", "libultraship"):
        directory = SOURCE / "libultraship/src" / name
        cmake_inputs[str((directory / "CMakeLists.txt").relative_to(ROOT))] = digest(directory / "CMakeLists.txt")
        local_lines = definitions + [
            f'set(CMAKE_CURRENT_SOURCE_DIR "{directory.as_posix()}")',
            f'include("{(directory / "CMakeLists.txt").as_posix()}")',
        ]
        script_path.write_text("\n".join(local_lines) + "\n", encoding="utf-8")
        subprocess.run(["cmake", "-P", str(script_path)], cwd=directory, check=True)
        selected.update(Path(p) for p in collection.read_text().splitlines() if Path(p).suffix in (".cpp", ".c"))

    exclusions = {
        "port/coroutine_test.cpp": "Separate upstream test executable; never application code",
        "port/first_run.cpp": "Host ROM extraction belongs to tools/build-assets.ps1; Xbox consumes final O2R assets",
        "port/native_dialog.cpp": "Desktop file picker is called only by excluded host first-run ROM extraction",
        "port/renderdoc_trigger.cpp": "Desktop RenderDoc DLL injection unavailable on Xbox; original call sites guarded by native startup projection",
        "port/port_window_icon.cpp": "Desktop window icon; native Xbox presentation has no desktop window icon",
        "port/enhancements/Updater.cpp": "Desktop self-updater uses process/shell/network package replacement; Xbox deployment is external",
        "port/enhancements/DiscordRichPresence.cpp": "Desktop Discord IPC capability absent on Xbox",
        "port/enhancements/ShaderDownloader.cpp": "Desktop shader downloader; packaged shader resources retain runtime loading",
        "libultraship/src/ship/audio/SDLAudioPlayer.cpp": "Replaced platform output: real XAudio2AudioPlayer; AudioPlayer and mixer retained",
        "libultraship/src/ship/audio/WasapiAudioPlayer.cpp": "Desktop WASAPI unavailable; real XAudio2AudioPlayer",
        "libultraship/src/ship/audio/CoreAudioAudioPlayer.cpp": "Apple platform output unavailable; real XAudio2AudioPlayer",
    }
    entries = []
    for path in sorted(selected):
        relative = path.relative_to(SOURCE).as_posix()
        reason = exclusions.get(relative)
        if relative.startswith("libultraship/src/ship/controller/raphnet/") or relative.endswith(
            "/RaphnetRumbleMapping.cpp"
        ):
            reason = """\
Raphnet USB HID transport unavailable on Xbox; serialized mapping \
identity retained with explicit unsupported-device reporting; no mock \
transport"""
        if relative.startswith("libultraship/src/fast/backends/"):
            reason = "Desktop rendering/window backend replaced by current-contract Xbox Xenos/window implementations; original Fast3D interpreter retained"
        actual = path
        if relative == "port/resource/RelocFileTable.us.cpp":
            actual = ROOT / "scratch/generated/port/resource/RelocFileTable.us.cpp"
        if not actual.is_file():
            raise RuntimeError("Missing real source: " + str(actual))
        entries.append(
            {
                "path": relative,
                "sha256": digest(actual),
                "input": str(actual.relative_to(ROOT)).replace("\\", "/"),
                "selected": reason is None,
                "exclusion": reason,
            }
        )
    result = {
        "schema": 1,
        "scope": "Authoritative CMake application/LUS inputs plus separately generated full game C manifest",
        "status": "selection only; platform registration and compile/link completion must be validated separately",
        "cmake_inputs": cmake_inputs,
        "disable_scripting": "Existing upstream option: native TinyCC/funchook desktop executable-code runtime unavailable on Xbox",
        "sources": entries,
        "game_c_sources": len(game_manifest()["sources"]),
    }
    (OUT / "source-manifest.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        "%d application/LUS inputs, %d selected; %d real game C inputs tracked separately"
        % (len(entries), sum(e["selected"] for e in entries), result["game_c_sources"])
    )


if __name__ == "__main__":
    main()
