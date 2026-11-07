"""Prepare a strict, reproducible sparse endian overlay of pinned BattleShip.

No source-tree writes. Apply this overlay before XDK preprocessing/lowering.
The manifest records each original/output hash and checked transformation.
"""

from pathlib import Path
import argparse
import hashlib
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
SUPPORT = ROOT / "platform/xbox360/endian"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def transform(relative, source, mapping_path=None):
    """Transform only reviewed cases; preserve line counts or emit an explicit reset."""
    text = source
    edits = []

    def replace(old, new, count=1):
        nonlocal text
        found = text.count(old)
        if found != count:
            raise ValueError(f"{relative}: expected {count} exact matches, found {found}: {old!r}")
        if old.count("\n") != new.count("\n"):
            raise ValueError("transformation must preserve source line count")
        text = text.replace(old, new)
        edits.append({"match": old, "count": count})

    if relative == "decomp/include/config.h":
        replace(
            "#ifdef PORT\n#define IS_BIG_ENDIAN 0",
            "#if defined(PORT) && !SMASH360_HOST_BIG_ENDIAN\n#define IS_BIG_ENDIAN 0",
        )
        replace(
            "#define BITFIELD_SEXT(x, bits) ((s32)(((u32)(x) ^ (1u << ((bits) - 1))) - (1u <<"
            " ((bits) - 1))))",
            "#define BITFIELD_SEXT(x, bits) ((s32)((((u32)(x) & ((1u << (bits)) - 1u)) ^ (1u <<"
            " ((bits) - 1))) - (1u << ((bits) - 1))))",
        )
    elif relative == "decomp/include/PR/guint.h":
        replace(
            "#if defined(_MSC_VER) || (defined(__BYTE_ORDER__) && __BYTE_ORDER__ =="
            " __ORDER_LITTLE_ENDIAN__)",
            "#if !SMASH360_HOST_BIG_ENDIAN",
        )
    elif relative == "decomp/src/lb/lbparticle.c":
        replace(
            "u8 swapped[4] = { bytes[3], bytes[2], bytes[1], bytes[0] };\n\t\tmemcpy(f, swapped,"
            " sizeof(f32));",
            "/* Preserve BE bytecode; only native representation changes."
            " */\n\t\tsmash360CopyBEFloatBytes(f, bytes);",
        )
    elif relative == "decomp/src/sys/audio.c":
        # SBK payload remains N64 BE. n_alCSeqNew reads these 17 header words
        # natively; the PORT reversal is only needed on a little-endian host.
        replace(
            "                        {\n                            u32 *hdr = (u32"
            " *)sSYAudioBGMSequenceDatas[port_i];",
            "                        if (!SMASH360_HOST_BIG_ENDIAN) {\n                           "
            " u32 *hdr = (u32 *)sSYAudioBGMSequenceDatas[port_i];",
        )
        # Not endian: Shipyard audio_cpu freezes the port volume CVars (volume.cpp)
        # for exactly the PORT loop's synthesis call, on the audio thread.
        for statement, function in (
            ("acmd_trace_begin_task();", "ShipyardAudioControls_Begin"),
            ("acmd_trace_end_task();", "ShipyardAudioControls_End"),
        ):
            replace(statement, "{ extern void %s(void); %s(); } %s" % (function, function, statement))
    elif relative == "port/bridge/lbreloc_byteswap.cpp":
        # Every use in this translation unit repairs this same LE pass-one.
        calls = list(re.finditer(r"\bBSWAP32\(", text))
        if len(calls) != 12:
            raise ValueError(f"{relative}: expected 12 LE BSWAP32 calls")
        text = re.sub(r"\bBSWAP32\(", "smash360UndoLEWordSwap(", text)
        edits.append({"match": "audited LE BSWAP32 call sites", "count": 12})
        replace("return (w << 16) | (w >> 16);", "return smash360UndoLEHalfSwap(w);")
        for value, count in [
            ("words[i]", 1),
            ("*word", 1),
            ("region[i * 4 + 0]", 2),
            ("region[i * 4 + 1]", 2),
            ("region[i * 4 + 2]", 2),
        ]:
            replace(
                f"{value} = ({value} << 16) | ({value} >> 16);",
                f"{value} = smash360UndoLEHalfSwap({value});",
                count,
            )
        replace(
            "if (data == nullptr || size < 4)",
            "if (data == nullptr || size < 4 || SMASH360_HOST_BIG_ENDIAN)",
        )
        replace(
            "static void fixup_u16_u8u8(uint32_t *word)\n{",
            "static void fixup_u16_u8u8(uint32_t *word)\n{ if (SMASH360_HOST_BIG_ENDIAN) return;",
        )
        # Native BE blobs never underwent LE pass-one. Runtime texture/vertex
        # repairs and their private idempotency tables therefore have no data
        # effect. Keep the complete body for explicit asset diagnostics. Sprite
        # deswizzle, token relocation and Fast3D callers are separate and intact.
        for signature in (
            (
                'extern "C" void portRelocFixupTextureAtRuntime(const void *addr, unsigned int'
                " num_bytes)"
            ),
            'extern "C" void portRelocFixupVertexAtRuntime(const void *addr, unsigned int num_vtx)',
        ):
            replace(
                signature + "\n{",
                signature
                + "\n{ if (SMASH360_HOST_BIG_ENDIAN && !stage_audit_enabled() && !tex_log_enabled()"
                " && !tex_dump_enabled()) return;",
            )
        for index, le_index in enumerate([3, 2, 1, 0, 7, 6]):
            replace(
                f"sFixed[{index}] = src[{le_index}];",
                f"sFixed[{index}] = src[SMASH360_HOST_BIG_ENDIAN ? {index} : {le_index}];",
            )
    elif relative == "port/bridge/lbreloc_bridge.cpp":
        # This also suppresses halfswapped-range registration and its repair
        # consumers. Token traversal/assignment and heap eviction stay intact.
        replace(
            "bool is_fighter_figatree =\n\t\tforce_figatree_fixup ||"
            " portRelocIsFighterFigatreeFile(file_id);",
            "bool is_fighter_figatree = !SMASH360_HOST_BIG_ENDIAN &&\n\t\t(force_figatree_fixup ||"
            " portRelocIsFighterFigatreeFile(file_id));",
        )
    elif relative == "port/bridge/particle_bank_bridge.cpp":
        for width in (16, 32):
            old = f"static inline void bswap{width}At(uint8_t *p, size_t off) {{"
            replace(old, old + " if (SMASH360_HOST_BIG_ENDIAN) return;")
    elif relative == "port/bridge/audio_bridge.cpp":
        replace(
            "dst[w*4 + 0] = src[w*4 + 3];\n                    dst[w*4 + 1] = src[w*4 + 2];\n      "
            "              dst[w*4 + 2] = src[w*4 + 1];\n                    dst[w*4 + 3] = src[w*4"
            " + 0];",
            "smash360CopyBEFloatBytes(dst + w*4, src + w*4);\n                    /* Source is BE;"
            " native host selects copy order. */\n                    /* Preserve source line"
            " mapping. */\n                    /* Preserve source line mapping. */",
        )
    elif relative == "decomp/src/wp/wptypes.h":
        old = "    s32 angle : 10;"
        if text.count(old) != 1:
            raise ValueError("WPAttributes angle field must match once")
        next_line = text[: text.index(old) + len(old)].count("\n") + 2
        path = mapping_path or ROOT / "upstream/BattleShip" / relative
        new = (
            "#ifndef PORT\n"
            + old
            + "\n#endif\n#line "
            + str(next_line)
            + ' "'
            + path.as_posix()
            + '"'
        )
        text = text.replace(old, new)
        edits.append(
            {
                "match": old,
                "count": 1,
                "reason": "PORT already stores the original angle explicitly at offset 0x26",
            }
        )
    else:
        raise ValueError(f"unrecognized source: {relative}")
    return text, edits


def prepare(source_root, output):
    source_root = source_root.resolve()
    output = output.resolve()
    original = (ROOT / "upstream").resolve()
    if (
        output == source_root
        or source_root in output.parents
        or output in source_root.parents
        or output == original
        or original in output.parents
    ):
        raise ValueError("output must not overlap the source or reference tree")
    if ROOT not in output.parents:
        raise ValueError("output must be inside the Smash360 workspace")
    lock = json.loads((SUPPORT / "source-lock.json").read_text())
    ready = []
    for relative, expected in lock.items():
        path = source_root / relative
        raw = path.read_bytes()
        if sha(raw) != expected:
            raise ValueError(f"source hash mismatch: {relative}")
        text, edits = transform(relative, raw.decode("utf-8").replace("\r\n", "\n"), path)
        mapped = f'#include <smash360_endian.h>\n#line 1 "{path.as_posix()}"\n' + text
        data = mapped.encode("utf-8")
        ready.append(
            (
                relative,
                data,
                {
                    "path": relative,
                    "source_sha256": expected,
                    "output_sha256": sha(data),
                    "edits": edits,
                },
            )
        )
    # Fail closed: validate every input and transformation before first write.
    header = (SUPPORT / "smash360_endian.h").read_bytes()
    for relative, data, _ in ready:
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    (output / "smash360_endian.h").write_bytes(header)
    manifest = {
        "format": 1,
        "source_root": source_root.as_posix(),
        "helper_sha256": sha(header),
        "files": [row for _, _, row in ready],
    }
    (output / "endian-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=ROOT / "upstream/BattleShip")
    parser.add_argument("--output", type=Path, default=ROOT / "scratch/endian-xdk/source")
    args = parser.parse_args()
    try:
        manifest = prepare(args.source_root, args.output)
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(f"Prepared {len(manifest['files'])} endian overlay files in {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
