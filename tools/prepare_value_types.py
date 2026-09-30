"""Verify the physical Shipyard value-type implementation."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
from platform_base import resolve as resolve_platform_base


def verify():
    base = resolve_platform_base(ROOT)
    sys.path.insert(0, str(base / "python"))
    from xbox360_platform.value_types import variant_header

    header = base / "sources/value_types/xbox_compat/variant.h"
    if header.read_text() != variant_header():
        raise ValueError("Shipyard variant header differs from its canonical generator")
    for name in ("common.h", "optional.h", "variant.h"):
        stale = ROOT / "scratch/value-types/include/xbox_compat" / name
        if stale.is_file():
            stale.unlink()
    manifest = ROOT / "scratch/value-types/include/value-types-manifest.json"
    if manifest.is_file():
        manifest.unlink()
    return header


if __name__ == "__main__":
    print(verify())
