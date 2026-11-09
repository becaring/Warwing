"""Restore the developers' battle debug menu as a sparse game-source overlay.

The pinned decomp fork deleted src/db's C files at 0583cc8 but keeps them in its history; the
restore revision is the commit before that, already carrying the PC port changes. ovl8, the UI
library the menu draws through, is partly undecompiled, so platform/xbox360/debug/dbwindow.c
supplies the window calls the menu makes. The scene manager learns the Back-menu boot option,
and the port's empty scene stubs give way to the restored scenes. A missed player fist slam recovers
instead of falling forever. Fails closed before writing.
"""

from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / "upstream/BattleShip"
SUPPORT = ROOT / "platform/xbox360/debug"
OUTPUT = ROOT / "scratch/debug-xdk/source"
SHIM = "decomp/src/db/dbwindow.c"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def replace(relative, text, old, new):
    if text.count(old) != 1:
        raise ValueError(f"{relative}: expected one match: {old[:80]!r}")
    return text.replace(old, new)


def transform(relative, text):
    if relative == "decomp/src/db/dbmenu.c":
        # The N64 build passed &str as a va_list; PPC passes variadic arguments in registers.
        text = replace(
            relative,
            text,
            "\tfunc_ovl8_80386BE0(sDBMenuStringBuffer, &str);",
            "\t{ va_list args; va_start(args, str);"
            " vsnprintf(sDBMenuStringBuffer, sizeof(sDBMenuStringBuffer) - 1, str, args); va_end(args); }",
        )
    elif relative == "decomp/src/sc/scmanager.c":
        declare = "\textern int port_enhancement_boot_to_vs_css(void); extern sb32 portDebugBattleIsBootScene(void);\n"
        text = replace(
            relative,
            text,
            "\textern int port_enhancement_boot_to_vs_css(void);\n\tif (port_enhancement_boot_to_vs_css())",
            declare + "\tif (portDebugBattleIsBootScene()) { gSCManagerSceneData.scene_curr ="
            " gSCManagerSceneData.scene_prev = nSCKindDebugBattle; } else if (port_enhancement_boot_to_vs_css())",
        )
        text = replace(
            relative,
            text,
            "\textern int port_enhancement_boot_to_vs_css(void);\n\n"
            "\tsPortResetTarget = port_enhancement_boot_to_vs_css() ? nSCKindPlayersVS : nSCKindOpeningRoom;",
            declare + "\n\tsPortResetTarget = portDebugBattleIsBootScene() ? nSCKindDebugBattle :"
            " port_enhancement_boot_to_vs_css() ? nSCKindPlayersVS : nSCKindOpeningRoom;",
        )
    elif relative == "decomp/src/ft/ftchar/ftboss/ftbossgootsubusudown.c":
        # A player-steered fist slam can drop where no floor lies below; Master Hand has no blast-zone KO,
        # so a drop past the stage's lowest vertex returns him to his hover above the target's floor.
        text = replace(
            relative,
            text,
            "        ftBossGootsubusuEndSetStatus(fighter_gobj);\n    }\n}",
            "        ftBossGootsubusuEndSetStatus(fighter_gobj);\n    }\n"
            "    else if (DObjGetStruct(fighter_gobj)->translate.vec.f.y < gMPCollisionBounds.current.bottom)\n    {\n"
            "        FTStruct *fp = ftGetStruct(fighter_gobj);\n\n"
            "        ftBossWaitSetStatus(fighter_gobj);\n"
            "        DObjGetStruct(fighter_gobj)->translate.vec.f = fp->status_vars.boss.wait.pos;\n"
            "        fp->coll_data.pos_prev = fp->status_vars.boss.wait.pos;\n    }\n}",
        )
    elif relative == "port/stubs/debug_stubs.c":
        for scene in ("dbBattleStartScene", "dbFallsStartScene", "dbMapsStartScene"):
            text = replace(relative, text, f"void {scene}(void)\n{{\n}}", f"/* {scene}: restored debug overlay */\n\n")
    return text


def prepare(output):
    lock = json.loads((SUPPORT / "source-lock.json").read_text(encoding="utf-8"))
    revision = lock["restore_revision"]
    ready = []
    for relative, expected in lock["restored"].items():
        historical = relative.removeprefix("decomp/")
        raw = subprocess.run(
            ["git", "-c", "safe.directory=*", "-C", str(UPSTREAM / "decomp"), "show", f"{revision}:{historical}"],
            capture_output=True,
            check=True,
        ).stdout
        if sha(raw) != expected:
            raise ValueError(f"restored source hash mismatch: {relative}")
        origin = f"upstream/BattleShip/decomp@{revision[:12]}/{historical}"
        ready.append((relative, raw, origin, expected))
    for relative, expected in lock["patched"].items():
        raw = (UPSTREAM / relative).read_bytes()
        if sha(raw) != expected:
            raise ValueError(f"source hash mismatch: {relative}")
        ready.append((relative, raw, (UPSTREAM / relative).as_posix(), expected))
    shim = (SUPPORT / "dbwindow.c").read_bytes()
    ready.append((SHIM, shim, (SUPPORT / "dbwindow.c").as_posix(), sha(shim)))
    files = []
    outputs = []
    for relative, raw, origin, expected in ready:
        text = transform(relative, raw.decode("utf-8").replace("\r\n", "\n"))
        prefix = "#include <stdarg.h>\n#include <stdio.h>\n" if relative == "decomp/src/db/dbmenu.c" else ""
        data = (prefix + f'#line 1 "{origin}"\n' + text).encode("utf-8")
        outputs.append((relative, data))
        files.append({"path": relative, "origin": origin, "source_sha256": expected, "output_sha256": sha(data)})
    for relative, data in outputs:
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    manifest = {"format": 1, "restore_revision": revision, "files": files}
    (output / "debug-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    try:
        manifest = prepare(args.output.resolve())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(f"Prepared {len(manifest['files'])} debug overlay files in {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
