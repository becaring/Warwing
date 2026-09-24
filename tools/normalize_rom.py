"""Validate the user's dump and normalize byte order without changing the dump."""
from pathlib import Path
import argparse
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SHA1 = "e2929e10fccc0aa84e5776227e798abc07cedabf"


def normalize(data):
    if len(data) != 16 * 1024 * 1024:
        raise ValueError("Expected a 16 MiB original US retail dump")
    magic = data[:4].hex()
    if magic == "80371240":
        result = data
    elif magic == "37804012":
        result = bytearray(len(data))
        result[0::2], result[1::2] = data[1::2], data[0::2]
    elif magic == "40123780":
        result = bytearray(len(data))
        for index in range(4):
            result[index::4] = data[3-index::4]
    else:
        raise ValueError("Unrecognized N64 dump byte order")
    if hashlib.sha1(result).hexdigest() != EXPECTED_SHA1:
        raise ValueError("Dump is not pinned BattleShip's supported original US ROM")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rom", type=Path)
    args = parser.parse_args()
    source = args.rom.resolve()
    data = source.read_bytes()
    canonical = normalize(data)
    output = ROOT / "baserom.us.z64"
    if output.exists():
        if output.read_bytes() != canonical:
            raise ValueError("Existing baserom.us.z64 differs; refusing to replace it")
    else:
        output.write_bytes(canonical)
    report = {
        "source": str(source), "source_sha1": hashlib.sha1(data).hexdigest(),
        "source_magic": data[:4].hex(), "canonical": output.name,
        "canonical_sha1": hashlib.sha1(canonical).hexdigest(),
        "canonical_sha256": hashlib.sha256(canonical).hexdigest(),
        "size": len(canonical), "title": canonical[0x20:0x34].decode("ascii"),
        "game_code": canonical[0x3b:0x3f].decode("ascii"),
    }
    audit = ROOT / "scratch/audit"
    audit.mkdir(parents=True, exist_ok=True)
    (audit / "rom.json").write_text(json.dumps(report, indent=2) + "\n")
    print("Verified canonical US ROM:", report["canonical_sha1"])


if __name__ == "__main__":
    main()
