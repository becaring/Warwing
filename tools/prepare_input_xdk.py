"""Pinned sparse input overlay; original sources remain read-only."""

from pathlib import Path
import hashlib, json, re, argparse

ROOT = Path(__file__).resolve().parents[1]
UP = ROOT / "upstream/BattleShip"
BASE = ROOT / "platform/xbox360/input"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def replace(text, old, new, count=1):
    if text.count(old) != count:
        raise ValueError("Strict match failed: " + old[:100])
    return text.replace(old, new)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "scratch/input-xdk/source")
    args = parser.parse_args()
    out = args.output.resolve()
    if not out.is_relative_to(ROOT) or out.is_relative_to(UP):
        raise ValueError("Output must be owned workspace outside upstream")
    lock = json.loads((BASE / "source-lock.json").read_text())
    pending = []
    for rel, expected in lock.items():
        source = UP / rel
        data = source.read_bytes()
        if sha(data) != expected:
            raise ValueError("Source changed: " + rel)
        text = data.decode().replace("\r\n", "\n")
        text = re.sub(
            r"#include <(?:SDL2/)?SDL(?:_events)?\.h>", "#include <smash360_input_sdl.h>", text
        )
        if rel.endswith("physicaldevice/ConnectedPhysicalDeviceManager.h"):
            text = replace(
                text,
                "    void RefreshConnectedSDLGamepads();",
                "    void RefreshConnectedSDLGamepads();\n    void RefreshNativeGamepads(bool"
                " usePresentationSample = false);",
            )
            text = replace(
                text, "  private:", "  private:\n    uint32_t mNativeTopologyGeneration;"
            )
        elif rel.endswith("physicaldevice/ConnectedPhysicalDeviceManager.cpp"):
            text = replace(
                text,
                "ConnectedPhysicalDeviceManager::ConnectedPhysicalDeviceManager() {",
                "ConnectedPhysicalDeviceManager::ConnectedPhysicalDeviceManager() :"
                " mNativeTopologyGeneration(0) {",
            )
            method = """void ConnectedPhysicalDeviceManager::RefreshNativeGamepads(bool usePresentationSample) {
    if (usePresentationSample) ShipyardInput_RefreshGamepadsForGui();
    else ShipyardInput_PumpGamepads();
    const uint32_t generation = ShipyardInput_GamepadTopologyGeneration();
    if (generation != mNativeTopologyGeneration) {
        RefreshConnectedSDLGamepads();
        mNativeTopologyGeneration = generation;
    }
}
"""
            text = replace(text, "} // namespace Ship", method + "} // namespace Ship")
        elif rel.endswith("physicaldevice/SDLAddRemoveDeviceEventHandler.cpp"):
            start = text.index("    SDL_PumpEvents();")
            end = text.index("\n}\n} // namespace Ship", start)
            text = (
                text[:start]
                + "    Context::GetInstance()->GetControlDeck()->GetConnectedPhysicalDeviceManager()->RefreshNativeGamepads(true);"
                + text[end:]
            )
        elif rel.endswith("src/libultraship/controller/controldeck/ControlDeck.cpp"):
            text = replace(
                text,
                "    SDL_PumpEvents();",
                "    GetConnectedPhysicalDeviceManager()->RefreshNativeGamepads();",
            )
        transformed = ('#line 1 "' + source.as_posix() + '"\n' + text).encode()
        pending.append((rel, transformed, expected))
    manifest = {
        "source_root": str(UP),
        "sources": [],
        "native_sources": ["window_input.cpp"],
        "excluded_capabilities": [
            "raw Raphnet HID transport",
            "keyboard",
            "mouse",
            "gyro",
            "programmable RGB LED",
        ],
        "note": (
            "No runtime proof; native sources compile separately. Include platform/xbox360/input."
        ),
    }
    for rel, data, original_hash in pending:
        target = out / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        manifest["sources"].append(
            {"path": rel, "source_sha256": original_hash, "output_sha256": sha(data)}
        )
    manifest["backend_hashes"] = {
        p.name: sha(p.read_bytes()) for p in sorted(BASE.glob("*")) if p.is_file()
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "input-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Generated {len(pending)} pinned input overlay files in {out}")


if __name__ == "__main__":
    main()
