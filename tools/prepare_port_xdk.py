"""Compile real selected BattleShip port sources through owned composed overlays."""

from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import runpy
import subprocess
import sys
import profile_projections
import bounds_cache_projection
import command_work_projection
import reloc_lookup_projection
import rcp_cost_projection
import overlap_projection
from prepare_prism_xdk import PARSER, walk
from xbox360_platform.cpp_syntax import lower_if_initializers

ROOT = Path(__file__).resolve().parents[1]
from platform_base import resolve as resolve_platform_base

PLATFORM_BASE = resolve_platform_base(ROOT)
UP = ROOT / "upstream/BattleShip"
OUT = ROOT / "scratch/port-xdk"
OWN = ROOT / "platform/xbox360/cpp-compat/port"
CPP_LOWER = runpy.run_path(str(ROOT / "platform/xbox360/cpp-compat/config/lowering.py"))[
    "lower_ranges"
]
MAPPED = runpy.run_path(str(ROOT / "tools/prepare_prism_xdk.py"))["mapped"]
GUI = runpy.run_path(str(OWN / "gui_lowering.py"))["transform"]
sys.path.insert(0, str(ROOT / "platform/xbox360/game-compat"))
from source_tree import stage_sources


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def transform(relative, text):
    text = profile_projections.port(relative, text)
    if relative == "port/bridge/lbreloc_byteswap.cpp":
        diagnostic = 'std::fopen("debug_traces/tex_fixup.log", "w")'
        if text.count(diagnostic) != 1:
            raise ValueError("Texture diagnostic path anchor changed")
        text = text.replace(diagnostic, 'std::fopen("cache:\\\\tex_fixup.log", "w")')
        shell = '#if defined(_WIN32)\n\tstd::system("if not exist tex_dump mkdir tex_dump");'
        if text.count(shell) != 1:
            raise ValueError("Texture dump directory operation changed")
        text = text.replace(
            shell,
            "#if defined(_XBOX)\n    std::error_code directoryError;\n   "
            ' xbox_compat::filesystem::create_directories("tex_dump", directoryError);\n#elif'
            ' defined(_WIN32)\n\tstd::system("if not exist tex_dump mkdir tex_dump");',
        )
        text = '#include "filesystem/filesystem.h"\n' + text
    if relative.startswith("port/gui/"):
        text = GUI(relative, text)
    if relative == "port/resource/ResourceType.h":
        anchor = "enum class ResourceType : uint32_t {"
        if text.count(anchor) != 1:
            raise ValueError("Unsigned resource enum shape changed")
        text = text.replace(anchor, "enum ResourceType : uint32_t {")
    if relative == "port/port.cpp":
        text = text.replace(
            "#include <libultraship/libultraship.h>",
            '#include "port/gui_includes.h"\n#include <ship/resource/ResourceManager.h>\n#include'
            " <ship/resource/archive/ArchiveManager.h>\n#include"
            " <ship/debug/CrashHandler.h>\n#include <ship/window/gui/GameOverlay.h>\n#include"
            ' <ship/window/gui/ConsoleWindow.h>\n#include "crt/snprintf.h"',
        )
        text = text.replace(
            "#include <SDL2/SDL.h>", "#if !defined(_XBOX)\n#include <SDL2/SDL.h>\n#endif"
        )
        text = text.replace("#include <filesystem>", '#include "filesystem/filesystem.h"').replace(
            "std::filesystem", "xbox_compat::filesystem"
        )
        text = lower_if_initializers(text, PARSER, walk)
    if re.search(r"\b(?:std::)?getenv\s*\(", text):
        text = '#include "environment.h"\n' + re.sub(
            r"\b(?:std::)?getenv\s*\(", "XboxEnv_Get(", text
        )
    if relative == "port/port_watchdog.cpp":
        text = text.replace("#include <atomic>", '#include "atomic/atomic.h"')
        text = text.replace("#include <chrono>", '#include "chrono/chrono.h"')
        text = text.replace(
            "#include <thread>", '#include "clock/sleep.h"\n#include "thread-pool/native_support.h"'
        )
        text = text.replace("std::atomic<", "Shipyard::Atomic::atomic<").replace(
            "std::memory_order_", "Shipyard::Atomic::memory_order_"
        )
        text = text.replace("std::chrono", "xbox_compat::chrono").replace(
            "std::this_thread::sleep_for", "Shipyard::Clock::SleepFor"
        )
        text = text.replace(
            "std::thread           sWatchdogThread;", "xbox_compat::joining_thread sWatchdogThread;"
        )
        text = text.replace("std::thread(WatchdogLoop)", "xbox_compat::make_thread(WatchdogLoop)")
        text = re.sub(r"(Shipyard::Atomic::atomic<\w+>\s+\w+)\{([^{}]+)\};", r"\1(\2);", text)
        text = text.replace("constexpr ", "const ")
    if relative == "port/port_dl_ranges.cpp":
        text = bounds_cache_projection.span(bounds_cache_projection.transform(text))
        text = text.replace(
            "#include <atomic>", '#include "atomic/atomic.h"\n#include "crt/snprintf.h"'
        )
        text = text.replace("#include <mutex>", '#include "async/native.h"')
        text = text.replace(
            "std::atomic<uint64_t> sRangesGen{0};",
            "Shipyard::Atomic::atomic<uint64_t> sRangesGen(0);",
        )
        text = (
            text.replace("std::mutex", "xbox_compat::mutex")
            .replace("std::lock_guard", "xbox_compat::lock_guard")
            .replace("std::memory_order_", "Shipyard::Atomic::memory_order_")
        )
        text = (
            text.replace("uint64_t gen = ~0ull;", "uint64_t gen;")
            .replace("uintptr_t base = 0;", "uintptr_t base;")
            .replace("size_t size = 0;", "size_t size;")
        )
        # Zeroed entries never match: their size is 0.
        text = text.replace(
            "thread_local HitCache sHitCache[kHitCacheEntries];",
            "__declspec(thread) HitCache sHitCache[kHitCacheEntries];",
        )
        text = text.replace(
            "thread_local unsigned sHitCacheNext = 0;",
            "__declspec(thread) unsigned sHitCacheNext = 0;",
        )
        text = text.replace(
            "thread_local UnknownCache sUnknownCache = {0, {0, 0}, false};",
            "__declspec(thread) UnknownCache sUnknownCache = {0, {0, 0}, false};",
        )
        text = text.replace(
            "sRanges.push_back({b, size, label});",
            "Entry insertedEntry = {b, size, label}; sRanges.push_back(insertedEntry);",
        )
        text = text.replace(
            "sHitCache[sHitCacheNext++ % kHitCacheEntries] = HitCache{gen, e.base, e.size};",
            "HitCache updatedCache = {gen, e.base, e.size};"
            " sHitCache[sHitCacheNext++ % kHitCacheEntries] = updatedCache;",
        )
        text = text.replace("constexpr ", "const ")
    if relative.startswith("port/enhancements/") or relative in (
        "port/widescreen/widescreen.cpp",
        "port/resource/RelocPointerTable.cpp",
        "port/port_aobj_fixup.cpp",
    ):
        # Closed declarations are scalar arithmetic constants or immutable CVar
        # string pointers/arrays. Preserve top-level pointer constness too.
        text = re.sub(r"constexpr const char\* (\w+)", r"const char* const \1", text)
        text = text.replace("constexpr ", "const ")
    if relative == "port/bridge/lbreloc_byteswap.cpp":
        text = '#include "crt/snprintf.h"\n' + text
        text = text.replace(
            "[](auto &a, auto &b)",
            "[](const std::pair<int, uint64_t> &a, const std::pair<int, uint64_t> &b)",
        )
        text = text.replace("~size_t{3}", "~size_t(3)")
        text = text.replace(
            "sProtectedStructRanges.push_back({ b, b + size });",
            "ProtectedRange insertedRange = {b, b + size};"
            " sProtectedStructRanges.push_back(insertedRange);",
        )
        text = re.sub(
            r"regions\.push_back\(\{([^{}]+)\}\);",
            r"{ FixupRegion insertedRegion = {\1}; regions.push_back(insertedRegion); }",
            text,
        )
        a = text.index("struct StageAuditCounters {")
        b = text.index("\n};", a)
        block = text[a:b]
        members = re.findall(r"uint32_t\s+(\w+)\s*= 0;", block)
        if len(members) != 8:
            raise ValueError("StageAuditCounters shape changed")
        block = re.sub(r"(uint32_t\s+\w+)\s*= 0;", r"\1;", block)
        block += "\n    StageAuditCounters() : " + ", ".join(x + "(0)" for x in members) + " {}"
        text = text[:a] + block + text[b:]
        text = text.replace("StageAuditCounters{}", "StageAuditCounters()")
    if relative == "port/port_aobj_fixup.cpp":
        text = text.replace(
            "sHalfswappedRanges.push_back({b, e});",
            "Range insertedRange = {b, e}; sHalfswappedRanges.push_back(insertedRange);",
        )
    if relative == "port/fighter_registry.cpp":
        text = text.replace(
            "using FDPtr = std::unique_ptr<FighterDescriptor>;",
            "typedef std::unique_ptr<FighterDescriptor> FDPtr;",
        )
        text = text.replace(
            "std::make_unique<FighterDescriptor>()",
            "std::unique_ptr<FighterDescriptor>(new FighterDescriptor())",
        )
        text = text.replace("constexpr ", "const ")
    if relative == "port/enhancements/DisableStageHazards.cpp":
        text = text.replace("sBattleKey = {};", "sBattleKey = BattleKey();")
        text = re.sub(
            r"^static_assert\((.+)\);$",
            r'static_assert(\1, "Actual game mirror layout");',
            text,
            flags=re.M,
        )
        text = text.replace(
            "BattleKey CurrentBattleKey() {\n    return {",
            "BattleKey CurrentBattleKey() {\n    BattleKey result = {",
        )
        text = text.replace(
            "        gSCManagerBattleState,\n    };\n}",
            "        gSCManagerBattleState,\n    };\n    return result;\n}",
        )
    if relative in (
        "port/css_icons/port_css_arrow.cpp",
        "port/css_icons/port_css_stage_assets.cpp",
    ):
        text = text.replace("#include <mutex>", '#include "async/native.h"')
        text = text.replace("std::mutex", "xbox_compat::mutex").replace(
            "std::lock_guard", "xbox_compat::lock_guard"
        )
        text = text.replace("constexpr ", "const ")
        text = text.replace("#include <libultraship/libultraship.h>", "#include <ship/Context.h>")
        # These three writers construct native Sprite/Bitmap fields. Pixel
        # conversion/baked RGBA16 bytes remain explicitly serialized BE.
        for name, width in [("put_s16", 2), ("put_u16", 2), ("put_u32", 4)]:
            pattern = r"(static inline void " + name + r"\([^\n]+\) \{)[^}]+\}"
            text, count = re.subn(
                pattern, r"\1\n    std::memcpy(b + off, &v, " + str(width) + r");\n}", text
            )
            if count != 1:
                raise ValueError("Synthetic sprite native writer shape changed: " + name)
        if relative.endswith("port_css_stage_assets.cpp"):
            start = text.index("struct CacheEntry {")
            end = text.index("\n};", start)
            block = text[start:end]
            for name, value in [
                ("sprite", "nullptr"),
                ("bitmaps", "nullptr"),
                ("rgba16_buf", "nullptr"),
                ("nbitmaps", "0"),
                ("derive_failed", "false"),
            ]:
                block, count = re.subn(r"(\b" + name + r")\s*= " + value + r";", r"\1;", block)
                if count != 1:
                    raise ValueError("CSS CacheEntry shape changed")
            block += (
                "\n    CacheEntry() : sprite(nullptr), bitmaps(nullptr), rgba16_buf(nullptr),"
                " nbitmaps(0), derive_failed(false) {}"
            )
            text = text[:start] + block + text[end:]
    if relative == "port/enhancements/AnalogRemap.cpp":
        text = '#include "fast3d/views.h"\n' + text.replace("std::clamp(", "Smash360Fast3D::Clamp(")
    if relative == "port/interpolation/frame_interpolation.cpp":
        text = text.replace("#include <libultraship/libultraship.h>", "#include <ship/Context.h>")
        text = text.replace("constexpr ", "const ")
        text = text.replace(
            "sRecords.push_back({ mtx, owner, ordinal, tag });",
            "RecordEntry record = {mtx, owner, ordinal, tag}; sRecords.push_back(record);",
        )
        # These three maps are default-constructed and never change their
        # max_load_factor (1.0); rehash(n) is the specified reserve(n) bucket count.
        for name in ("occurrence", "sReplacements", "sPrevIndex"):
            text = text.replace(name + ".reserve(", name + ".rehash(")
        text = text.replace(
            "sReplacements.emplace(pair.mtx, value);",
            "sReplacements.insert(std::make_pair(pair.mtx, value));",
        )
        text = text.replace(
            "sPrevIndex.emplace(sPrev[i].key, i);",
            "sPrevIndex.insert(std::make_pair(sPrev[i].key, i));",
        )
    if relative == "port/port_save.cpp":
        text = text.replace("#include <libultraship/libultraship.h>", "#include <ship/Context.h>")
        text = text.replace(
            "#include <SDL2/SDL.h>", "#if !defined(_XBOX)\n#include <SDL2/SDL.h>\n#endif"
        )
        text = text.replace("#include <mutex>", '#include "async/native.h"')
        text = text.replace(
            "std::once_flag gPathOnce;",
            "xbox_compat::mutex gPathMutex;\nbool gPathResolved = false;",
        )
        # Saves are per profile, in the container the storage popup mounts; config stays in game:.
        relative_save = '        gSavePath = Ship::Context::GetPathRelativeToAppDirectory("ssb64_save.bin");'
        if text.count(relative_save) != 1:
            raise ValueError("save path drift")
        text = text.replace(
            relative_save,
            '#ifdef _XBOX\n        gSavePath = "smashsave:\\\\ssb64_save.bin";\n#else\n'
            + relative_save + "\n#endif",
        )
        start = text.index("    if (char *p = SDL_GetPrefPath")
        end = text.index('    gSavePath = "ssb64_save.bin";', start)
        text = text[:start] + "#if !defined(_XBOX)\n" + text[start:end] + "#endif\n" + text[end:]
        text = text.replace(
            "std::call_once(gPathOnce, resolveSavePath);",
            "xbox_compat::lock_guard<xbox_compat::mutex> guard(gPathMutex);\n    if"
            " (!gPathResolved) { resolveSavePath(); gPathResolved = true; }",
        )
    if relative in (
        "port/shaders/fast3d_shader_manifest.h",
        "port/shaders/fast3d_shader_manifest.cpp",
    ):
        text = text.replace("#include <span>", '#include "fast3d/views.h"').replace(
            "std::span<", "Smash360Fast3D::span<"
        )
        text = text.replace("constexpr std::array", "const std::array")
        text = text.replace(
            "return kUsShaderManifest;",
            "return Smash360Fast3D::span<const Fast::ShaderPermutation>(kUsShaderManifest.data(),"
            " kUsShaderManifest.size());",
        )
        if relative.endswith(".cpp"):
            text, count = re.subn(
                r"\{ (0x[0-9A-F]+ULL), (0x[0-9A-F]+ULL) \}",
                r"Fast::ShaderPermutation(\1, \2)",
                text,
            )
            if count != 74:
                raise ValueError("Shader manifest exact 74-pair shape changed")
    if relative == "port/coroutine_win32.cpp":
        old = "static thread_local PortCoroutine *sCurrentCoroutine = NULL;"
        if text.count(old) != 1:
            raise ValueError("Coroutine TLS anchor changed")
        text = text.replace(
            old, "static __declspec(thread) PortCoroutine *sCurrentCoroutine = NULL;"
        )
        text = text.replace("#include <windows.h>", "#include <xtl.h>")
    if relative == "port/enhancements/volume.cpp":
        # Every audio CVar read routes through these getters; n_alAudioFrame
        # freezes them once per synthesis call (endian overlay of sys/audio.c).
        from xbox360_platform import audio_cpu

        controls = tuple(
            (name, "float", 'CVarGetFloat("gSettings.Audio.%sVolume", 1.0f)' % name)
            for name in ("Master", "Music", "SFX", "Voice")
        )
        for name, _, expression in controls:
            text = audio_cpu.read(text, expression, name)
        text = audio_cpu.once(text, 'extern "C" {\n', 'extern "C" {\n' + audio_cpu.definitions(controls))
    if relative == "port/audio/mixer.c":
        # Subtract mixes and interleave use exact VMX lanes on aligned buffers.
        for old, new in (
            ("#define BUF_U8(a)", '#include "audio/mixer_vmx.h"\n#define BUF_U8(a)'),
            ("\tuint8_t  buf[DMEM_SIZE];", "\t__declspec(align(16)) uint8_t  buf[DMEM_SIZE];"),
            ("\tif (gain == -0x8000) {\n\t\t/* Special case: subtract only */\n",
             "\tif (gain == -0x8000) {\n\t\t/* Special case: subtract only */\n"
             "\t\tif (ShipyardAudio_SaturatedMix(out, in, nbytes, 1)) return;\n"),
            ("\td = BUF_S16(rspa.out);\n\n\tfor (i = 0; i < count; i++) {",
             "\td = BUF_S16(rspa.out);\n\tif (ShipyardAudio_Interleave(d, l, r, count * 2)) return;\n\n"
             "\tfor (i = 0; i < count; i++) {"),
        ):
            if text.count(old) != 1:
                raise ValueError("Mixer VMX anchor drift: " + old[:40])
            text = text.replace(old, new)
    if relative == "port/audio/audio_playback.cpp":
        if text.count("constexpr ") != 8:
            raise ValueError("Audio constants changed")
        text = text.replace("constexpr ", "const ")
        text = text.replace("#include <cmath>", '#include <cmath>\n#include "fast3d/platform.h"')
        text = text.replace("std::lrint(v)", "Smash360Fast3D::RoundSignedWord(v)")
        # WAV capture is a diagnostic. Keep byte-identical opted-in output,
        # but do no synchronous cache I/O during ordinary playback.
        anchor = "static void wavMaybeOpen(void)\n{\n"
        if text.count(anchor) != 1:
            raise ValueError("Audio capture entry drift")
        text = text.replace(
            anchor,
            anchor
            + '    const char* capture = XboxEnv_Get("SSB64_AUDIO_WAV_DUMP");\n'
            "    if (capture == nullptr || capture[0] != '1') return;\n",
        )
        # Existing bounded PCM diagnostic: Xbox has no /tmp mount. Its native
        # header/sample writes are BE, which is RIFX, not little-endian RIFF.
        # This changes only the diagnostic file, never the submitted audio.
        if text.count("/tmp/ssb64_dump.wav") != 3:
            raise ValueError("Audio diagnostic path anchor changed")
        text = text.replace("/tmp/ssb64_dump.wav", "cache:\\\\ssb64_dump.rifx")
        anchor = '    std::fwrite("RIFF", 1, 4, fp);  w32(riffSize);'
        if text.count(anchor) != 1:
            raise ValueError("Audio diagnostic header anchor changed")
        text = text.replace(
            anchor,
            '#ifdef _XBOX\n    std::fwrite("RIFX", 1, 4, fp);  w32(riffSize);\n#else\n'
            + anchor
            + "\n#endif",
        )
    if relative == "port/bridge/audio_bridge.cpp":
        if text.count("AudioBlob{}") != 8:
            raise ValueError("Audio reset shape changed")
        text = text.replace("AudioBlob{}", "AudioBlob()")
    if relative == "port/bridge/particle_bank_bridge.cpp":
        text = text.replace(
            "static constexpr size_t kBankTableCount", "static const size_t kBankTableCount"
        )
        text = text.replace("static constexpr int32_t kImFmtCi", "static const int32_t kImFmtCi")
        text = text.replace(
            "std::make_unique<WorkingEntry>()", "std::unique_ptr<WorkingEntry>(new WorkingEntry())"
        )
        text = text.replace(
            "auto [ins_it, inserted] = cache.emplace(std::string(archive_path), std::move(data));",
            "auto insertion = cache.insert(std::make_pair(std::string(archive_path),"
            " std::move(data)));\n    auto ins_it = insertion.first;",
        )
    if relative == "port/resource/RelocPointerTable.cpp":
        text = reloc_lookup_projection.pointer_table(text)
    if relative == "port/bridge/lbreloc_bridge.cpp":
        text = reloc_lookup_projection.transform(text)
        text = text.replace(
            "[begin, end](const PortRelocFileRange &range) {",
            "[begin, end](const PortRelocFileRange &range) -> bool {",
        )
        text = text.replace("std::_Exit(0);", "::_exit(0);")
        text = re.sub(
            r"sPortRelocFileRanges\.push_back\(\{(.*?)\}\);",
            r"PortRelocFileRange newRange = {\1}; sPortRelocFileRanges.push_back(newRange);",
            text,
            flags=re.S,
        )
        text = '#include "crt/snprintf.h"\n' + text
    if relative == "port/resource/RelocFile.h":
        text = text.replace("class RelocFile final :", "class RelocFile :")
        text = text.replace(
            "using Resource::Resource;",
            "explicit RelocFile(std::shared_ptr<Ship::ResourceInitData> initData) :"
            " Ship::Resource<void>(initData) {}",
        )
    if relative == "port/resource/RelocFileFactory.h":
        text = text.replace(
            "ResourceFactoryBinaryRelocFileV0 final :", "ResourceFactoryBinaryRelocFileV0 :"
        )
    if relative == "port/resource/RelocFileFactory.cpp":
        text = text.replace(
            "std::get<std::shared_ptr<Ship::BinaryReader>>",
            "xbox_compat::get<std::shared_ptr<Ship::BinaryReader>>",
        )
    if relative == "port/enhancements/enhancements.h":
        start = text.index("// Libretro shader pack downloader.")
        finish = text.index("bool IsShaderPackDownloadComplete();", start) + len(
            "bool IsShaderPackDownloadComplete();"
        )
        text = (
            text[:start]
            + "\n#if !defined(_XBOX)\n"
            + text[start:finish]
            + "\n#endif\n"
            + text[finish:]
        )
    if relative == "port/gameloop.cpp":
        text = command_work_projection.port(text)
        text = rcp_cost_projection.port(text)
        text = text.replace(
            "#include <libultraship/libultraship.h>",
            "#include <libultraship/libultra.h>\n#include <ship/Context.h>\n#include"
            " <ship/window/Window.h>",
        )
        text = text.replace(
            "#include <chrono>", '#include "chrono/chrono.h"\n#include "crt/snprintf.h"'
        )
        text = text.replace("#include <thread>", '#include "clock/sleep.h"')
        text = text.replace("#include <filesystem>", '#include "filesystem/filesystem.h"')
        text = text.replace("std::filesystem::", "xbox_compat::filesystem::")
        text = text.replace("std::chrono::", "xbox_compat::chrono::").replace(
            "std::this_thread::sleep_for", "Shipyard::Clock::SleepFor"
        )
        text = text.replace("OSMesg m{};", "OSMesg m = {};")
        text = overlap_projection.gameloop(text)
    if relative in (
        "port/bridge/particle_bank_bridge.cpp",
        "port/bridge/lbreloc_bridge.cpp",
        "port/bridge/lbreloc_byteswap.cpp",
        "port/port_aobj_fixup.cpp",
        "port/port_dl_ranges.cpp",
        "port/interpolation/frame_interpolation.cpp",
    ):
        text = '#include "config/compiler.h"\n' + CPP_LOWER(text.encode()).decode()
    if relative == "port/port_log.c":
        # Match SoH360's diagnostic fallback when game: is read-only (disc or
        # Xenia's executable mount). Preserve BattleShip's complete log bytes.
        text = text.replace(
            'sLogFile = fopen(path, "w");',
            'sLogFile = fopen(path, "w");\n#ifdef _XBOX\n    if (sLogFile == NULL) sLogFile ='
            ' fopen("cache:\\\\ssb64.log", "w");\n#endif',
        )
        text = text.replace(
            "#if defined(BATTLESHIP_UWP)", "#if defined(BATTLESHIP_UWP) || defined(_XBOX)"
        )
        if text.count("vfprintf(sLogFile, fmt, ap);") != 1:
            raise ValueError("Port logging body changed")
        declaration = "\tif (sLogFile == NULL) return;\n\tva_list ap;"
        if text.count(declaration) != 1:
            raise ValueError("Port logger declaration order changed")
        text = text.replace(
            declaration, "\tva_list ap;\n\tint required;\n\tif (sLogFile == NULL) return;"
        )
        text = text.replace(
            "#include <stdarg.h>",
            '#include <stdarg.h>\n#include <stdlib.h>\n#include "crt/snprintf.h"',
        )
        text = text.replace(
            "vfprintf(sLogFile, fmt, ap);",
            """required = Smash360_Vsnprintf(NULL, 0, fmt, ap);
    if (required >= 0) {
        char *complete = (char *)malloc((size_t)required + 1);
        if (complete != NULL) {
            if (Smash360_Vsnprintf(complete, (size_t)required + 1, fmt, ap) == required)
                fwrite(complete, 1, (size_t)required, sLogFile);
            free(complete);
        }
    }""",
        )
    return overlap_projection.port(relative, text)


def prepare():
    manifest = json.loads((ROOT / "scratch/application-xdk/source-manifest.json").read_text())
    selected = [
        item
        for item in manifest["sources"]
        if item["selected"]
        and item["path"].startswith("port/")
        and item["path"].endswith((".cpp", ".c"))
    ]
    header_locks = json.loads((OWN / "headers.lock.json").read_text())
    transformed = selected + [
        {"path": path, "input": "upstream/BattleShip/" + path, "sha256": digest}
        for path, digest in header_locks.items()
    ]
    overlay = OUT / "composed-overlay"
    overlay.mkdir(parents=True, exist_ok=True)
    files = {}
    # Keep source owners' canonical paths. Conflicts stop rather than choosing
    # an include-order winner; each owner can compose its own transforms.
    mappings = [
        ("scratch/endian-xdk/source", ""),
        ("scratch/startup-xdk/generated", ""),
        ("scratch/game-xdk/c-language-overlay", ""),
        ("scratch/fast3d-xdk/overlay", ""),
        ("scratch/config-xdk/generated", "libultraship/"),
        ("scratch/resources-xdk/generated", "libultraship/"),
        ("scratch/binary-reader-xdk/generated", "libultraship/"),
        ("scratch/audio-xdk/generated/include", "libultraship/include/"),
    ]
    mappings += [("scratch/gui-xdk/overlay", "")]
    mappings += [
        ("scratch/controllers-xdk/generated", "libultraship/"),
        ("scratch/context-xdk/overlay", ""),
    ]
    mappings += [("scratch/hires-xdk/overlay", "")]
    if (ROOT / "scratch/gui-widgets-xdk/generated/include").is_dir():
        mappings += [("scratch/gui-widgets-xdk/generated/include", "libultraship/include/")]
    for location, prefix in mappings:
        folder = ROOT / location
        if not folder.is_dir():
            raise ValueError("Required owner overlay missing: " + str(folder))
        for path in sorted(folder.rglob("*")):
            if path.suffix not in (".h", ".hpp", ".c", ".cpp", ".inc", ".inl"):
                continue
            relative = prefix + path.relative_to(folder).as_posix()
            content = path.read_bytes()
            chain = files.get(relative, {}).get("chain", [])
            if relative in files and files[relative]["content"] != content:
                if location not in (
                    "scratch/gui-xdk/overlay",
                    "scratch/gui-widgets-xdk/generated/include",
                    "scratch/context-xdk/overlay",
                ):
                    raise ValueError(
                        "Owner overlays conflict for "
                        + relative
                        + ": "
                        + files[relative]["input"]
                        + " and "
                        + str(path)
                    )
                # Root explicitly supplies these as canonical current GUI
                # headers, superseding the earlier Fast3D declaration overlay.
            files[relative] = {
                "input": str(path),
                "content": content,
                "chain": chain + [{"input": str(path.relative_to(ROOT)), "sha256": sha(path)}],
            }
    # Actual generated asset table, not the placeholder source under upstream.
    for item in transformed:
        original = ROOT / item["input"]
        if sha(original) != item["sha256"]:
            raise ValueError("Application input changed: " + item["path"])
        relative = item["path"]
        entry = files.get(relative, {"input": str(original), "content": original.read_bytes()})
        text = entry["content"].decode("utf-8-sig").replace("\r\n", "\n")
        text = re.sub(r"^#line[^\n]*\n", "", text, flags=re.M)
        lowered = transform(relative, text)
        if lowered != text or original != UP / relative:
            target = overlay / relative
            MAPPED(item["input"], lowered, target)
            files[relative] = {
                "input": entry["input"],
                "content": target.read_bytes(),
                "chain": (
                    entry.get("chain", [])
                    + [{"transform": "prepare_port_xdk.transform", "driver_sha256": sha(__file__)}]
                ),
            }
    records = []
    current = set(files)
    index = overlay / ".owned-files.json"
    if index.is_file():
        for obsolete in set(json.loads(index.read_text())) - current:
            target = (overlay / obsolete).resolve()
            if not target.is_relative_to(overlay.resolve()):
                raise ValueError("Invalid owned overlay path")
            if target.is_file():
                target.unlink()
    for relative, entry in sorted(files.items()):
        target = overlay / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(entry["content"])
        records.append(
            {
                "relative": relative,
                "input": entry["input"],
                "input_sha256": sha(entry["input"]),
                "output_sha256": sha(target),
                "chain": entry.get("chain", []),
            }
        )
    index.write_text(json.dumps(sorted(current), indent=2) + "\n")
    tree = OUT / "compile-tree"
    staged = stage_sources(UP, tree, [item["path"] for item in selected], [overlay])
    (OUT / "staging.json").write_text(
        json.dumps({"composed": records, "staged": staged}, indent=2) + "\n"
    )
    return selected, tree


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", action="append")
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    selected, tree = prepare()
    if args.prepare_only:
        return 0
    if args.source:
        selected = [item for item in selected if item["path"] in args.source]
        if {item["path"] for item in selected} != set(args.source):
            raise ValueError("Source is not selected port application input")
    sdk = Path(os.environ.get("XEDK", "C:/Program Files (x86)/Microsoft Xbox 360 SDK"))
    includes = [
        tree,
        tree / "port",
        tree / "decomp/src",
        tree / "debug_tools",
        tree / "libultraship/include",
        tree / "libultraship/src",
    ]
    includes += [
        ROOT / p
        for p in (
            "scratch/generated/include",
            "scratch/generated/css_icons",
            "scratch/generated/port/resource",
            "scratch/graphics-xdk/include",
            "scratch/logging-xdk/core-include",
            "scratch/logging-xdk/include",
            "scratch/imgui-xdk/source",
            "scratch/json-xdk/backend-generated",
            "platform/xbox360/imgui",
            "platform/xbox360/cpp-compat",
            "platform/xbox360",
            "platform/xbox360/input",
            "upstream/dependencies/stb",
            "upstream/dependencies/fmt-xdk",
            "scratch/thread-pool-xdk",
            "platform/xbox360/cpp-compat/thread-pool",
            "platform/xbox360/cpp-compat/async",
            "upstream/dependencies/libzip/lib",
            "scratch/resources-xdk/libzip-public",
            "upstream/BattleShip/libultraship/extern/StormLib/src",
        )
    ]
    includes += [
        PLATFORM_BASE,
        PLATFORM_BASE / "sources",
        PLATFORM_BASE / "sources/value_types",
        PLATFORM_BASE / "sources/json/include",
        sdk / "include/xbox",
    ]
    report = {
        "scope": "Actual selected port C++/C object audit; no final executable link",
        "driver_sha256": sha(__file__),
        "owned_helpers": {
            p.relative_to(ROOT).as_posix(): sha(p)
            for p in sorted(OWN.rglob("*"))
            if p.suffix in (".py", ".h", ".json")
        },
        "staging_sha256": sha(OUT / "staging.json"),
        "results": [],
    }
    for item in selected:
        name = item["path"].replace("/", "__")
        obj, log = OUT / (name + ".obj"), OUT / (name + ".log")
        command = [
            str(sdk / "bin/win32/cl.exe"),
            "/nologo",
            "/c",
            "/TP",
            "/EHsc",
            "/GR",
            "/MT",
            "/O2",
            "/W3",
            "/D_XBOX",
            "/DNOMINMAX",
            "/DPORT",
            "/DDISABLE_SCRIPTING",
            "/D_CRT_SECURE_NO_WARNINGS",
            "/DREGION_US=1",
            "/DVERSION_US=1",
            '/DSSB64_O2R_NAME="BattleShip.o2r"',
            '/DSSB64_APP_NAME="BattleShip"',
            "/DNON_MATCHING=1",
            "/DNON_EQUIVALENT=1",
            "/DAVOID_UB=1",
            "/DF3DEX_GBI_2=1",
            "/D_LANGUAGE_C",
            "/DN_MICRO=1",
            "/D_USE_MATH_DEFINES",
            "/DCIMGUI_DEFINE_ENUMS_AND_STRUCTS",
            "/DPORT_HIRES_ENABLED=1",
        ]
        command += ["/I" + str(path) for path in includes] + [
            "/Fo" + str(obj),
            str(tree / item["path"]),
        ]
        result = subprocess.run(command, cwd=ROOT, capture_output=True)
        log.write_bytes(result.stdout + result.stderr)
        errors = [
            line
            for line in (result.stdout + result.stderr).decode(errors="replace").splitlines()
            if "error " in line
        ]
        entry = dict(
            item,
            command=command,
            exit=result.returncode,
            errors=errors,
            staged_sha256=sha(tree / item["path"]),
        )
        if result.returncode == 0:
            assert obj.read_bytes()[:2] == b"\xf2\x01"
            entry.update(object=str(obj), object_sha256=sha(obj))
        report["results"].append(entry)
        (OUT / "compile-audit.json").write_text(json.dumps(report, indent=2) + "\n")
        print(
            ("PASS " if result.returncode == 0 else "FAIL ")
            + item["path"]
            + ("\n" + "\n".join(errors[:3]) if errors else ""),
            flush=True,
        )
    return 0 if all(result["exit"] == 0 for result in report["results"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
