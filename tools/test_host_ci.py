"""Run repository checks that need no SDK, ROM, or generated source tree."""

from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    scripts = ['tools/check_hygiene.py', 'tools/check_projector_style.py', 'tools/test_hygiene.py', 'tools/test_rom_entries.py']
    for script in scripts:
        result = subprocess.run([sys.executable, "-B", str(ROOT / script)], cwd=ROOT)
        if result.returncode:
            return result.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
