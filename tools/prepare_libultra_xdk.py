"""Pinned LUS libultra/audio bridge projection; no replacement OS services."""

from pathlib import Path
import hashlib, json, runpy

ROOT = Path(__file__).resolve().parents[1]
UP = ROOT / "upstream/BattleShip/libultraship"
BASE = ROOT / "platform/xbox360/cpp-compat/libultra"
OUT = ROOT / "scratch/libultra-xdk"
MAP = runpy.run_path(str(ROOT / "tools/prepare_prism_xdk.py"))["mapped"]
LOWER = runpy.run_path(str(ROOT / "platform/xbox360/cpp-compat/controllers/lowering.py"))


def once(text, a, b):
    if text.count(a) != 1:
        raise ValueError("libultra anchor drift: " + a[:100])
    return text.replace(a, b)


def transform(relative, text):
    if relative.endswith("/NullAudioPlayer.h"):
        text = once(text, '#include "AudioPlayer.h"', '#include "ship/audio/AudioPlayer.h"')
    if '#include "libultraship/libultraship.h"' in text:
        # Real declarations needed by these small C ABI modules, avoiding the
        # umbrella classes.h desktop GUI/audio dependency aggregation.
        text = once(
            text,
            '#include "libultraship/libultraship.h"',
            '#include "libultraship/libultra.h"\n#include <cstring>\n#include <cstdio>',
        )
    if relative.endswith("/os.cpp"):
        text = once(
            text,
            "#include <SDL2/SDL.h>\n#include <ratio>",
            '#include "ship/Context.h"\n#include'
            ' "libultraship/controller/controldeck/ControlDeck.h"\n#include'
            ' "input/physical.h"\n#include "libultra/clock.h"\n#include <spdlog/spdlog.h>',
        )
        start = text.index("// Establish a chrono duration for the N64 46.875MHz clock rate")
        end = text.index('extern "C" {', start)
        text = text[:start] + text[end:]
        for expression in (
            "std::chrono::duration_cast<n64CycleRateDuration>(std::chrono::steady_clock::now().time_since_epoch()).count()",
            (
                "std::chrono::duration_cast<n64CycleRateDuration>(std::chrono::steady_clock::now().time_since_epoch())\n"
                "               .count()"
            ),
            (
                "std::chrono::duration_cast<n64CycleRateDuration>(std::chrono::steady_clock::now().time_since_epoch())\n"
                "        .count()"
            ),
        ):
            text = once(text, expression, "Shipyard::Libultra::NowCycles()")
        start = text.index("    // Locating + loading gamecontrollerdb.txt")
        end = text.index(
            "    Ship::Context::GetInstance()->GetControlDeck()->Init(controllerBits);", start
        )
        text = (
            text[:start]
            + """    // Xbox physical devices use the actual four-slot XInput transport.
    // SDL controller databases, desktop HID hints and Raphnet are unavailable.
    ShipyardInput_PumpGamepads();
    SPDLOG_INFO("Initializing Xbox native controllers (four physical slots)");

"""
            + text[end:]
        )
        text = once(
            text,
            "osSendMesg(mesg, OSMesg{}, OS_MESG_NOBLOCK);",
            "osSendMesg(mesg, OSMesg(), OS_MESG_NOBLOCK);",
        )
        text = once(
            text,
            "    GameContPad* out = reinterpret_cast<GameContPad*>(pad);",
            '    static_assert(sizeof(GameContPad) == 6, "BattleShip game controller ABI is six'
            ' bytes");\n    GameContPad* out = reinterpret_cast<GameContPad*>(pad);',
        )
    if relative.endswith("/os_eeprom.cpp"):
        text = '#include "ship/Context.h"\n' + text
    if relative.endswith("/os_vi.cpp"):
        text = '#include "libultra/unavailable_vi_timer.h"\n' + text
        text = once(
            text,
            "Uint32 __lusViCallback(Uint32 interval, void* param)",
            "uint32_t __lusViCallback(uint32_t interval, void* param)",
        )
        text = once(
            text,
            "SDL_AddTimer(16, &__lusViCallback, NULL);",
            "Smash360_UnavailableLusFallbackViTimer(16, &__lusViCallback, NULL);",
        )
    if relative.endswith("/AudioDmaRegistry.cpp"):
        text = once(
            text, "static constexpr int kMaxAudioBlobs = 8;", "static const int kMaxAudioBlobs = 8;"
        )
        text = once(
            text,
            "    sAudioBlobs[sAudioBlobCount++] = { b, b + size };",
            "    const AudioBlobRange range = { b, b + size };\n    sAudioBlobs[sAudioBlobCount++]"
            " = range;",
        )
    return LOWER["syntax"](text, set())


def prepare():
    locks = json.loads((BASE / "source-lock.json").read_text())
    pending = {}
    selection = json.loads((ROOT / "scratch/application-xdk/source-manifest.json").read_text())
    selected = {
        entry["path"].removeprefix("libultraship/")
        for entry in selection["sources"]
        if entry["selected"]
    }
    if not {name for name in locks if name.endswith(".cpp")} <= selected:
        raise ValueError("Pinned libultra/audio source no longer selected by application manifest")
    for relative, expected in locks.items():
        raw = (UP / relative).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("libultra source SHA drift: " + relative)
        pending[relative] = transform(relative, raw.decode("utf-8-sig").replace("\r\n", "\n"))
    output = {}
    for relative, text in pending.items():
        path = OUT / "generated" / relative
        MAP("upstream/BattleShip/libultraship/" + relative, text, path)
        output[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    (OUT / "manifest.json").write_text(
        json.dumps(
            {
                "originals": locks,
                "outputs": output,
                "unavailable_symbol": "Smash360_UnavailableLusFallbackViTimer",
                "require_archive_member_unselected": ["os_vi.cpp", "os_mesg.cpp"],
                "inherited_noops_preserved": True,
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    prepare()
