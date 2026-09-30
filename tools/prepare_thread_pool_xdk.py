"""Generate the pinned BS thread-pool adapter from Shipyard."""

from pathlib import Path

from platform_base import resolve

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "upstream/dependencies/thread-pool/include/BS_thread_pool.hpp"
OUTPUT = ROOT / "scratch/thread-pool-xdk"


def main(source=None, output=None):
    resolve(ROOT)
    from xbox360_platform.bs_thread_pool import generate

    return generate(source or SOURCE, output or OUTPUT)


if __name__ == "__main__":
    main()
