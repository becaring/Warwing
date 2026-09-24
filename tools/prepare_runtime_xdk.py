"""Compile the direct Smash diagnostics adapter and Shipyard queue with XDK."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
from platform_base import resolve

ROOT = Path(__file__).resolve().parents[1]
SHIPYARD = resolve(ROOT)
PLATFORM = ROOT / 'platform/xbox360/runtime'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    output = ROOT / 'scratch/runtime-xdk'
    output.mkdir(parents=True, exist_ok=True)
    # A prior generated donor shadow must never satisfy a later project build.
    shadow = output / 'diagnostics.cpp'
    if shadow.exists():
        shadow.unlink()
    xedk = Path(os.environ.get('XEDK', 'C:/Program Files (x86)/Microsoft Xbox 360 SDK'))
    compiler = xedk / 'bin/win32/cl.exe'
    report = {'objects': []}
    for name, source in (
        ('diagnostics_adapter', PLATFORM / 'diagnostics_adapter.cpp'),
        ('diagnostics_queue', SHIPYARD / 'sources/diagnostics/queue.cpp'),
    ):
        obj = output / (name + '.obj')
        command = [str(compiler), '/nologo', '/c', '/TP', '/EHsc', '/MT', '/W4',
                   '/D_XBOX', '/DNOMINMAX', '/I' + str(xedk / 'include/xbox'),
                   '/I' + str(PLATFORM), '/I' + str(SHIPYARD / 'sources'),
                   '/Fo' + str(obj), str(source)]
        result = subprocess.run(command, capture_output=True, text=True)
        (output / (name + '.log')).write_text(result.stdout + result.stderr)
        print(name, 'PASS' if result.returncode == 0 else 'FAIL')
        if result.returncode:
            print(result.stdout, result.stderr)
            raise RuntimeError('XDK compilation failed')
        report['objects'].append({'source': str(source), 'sha256': digest(source),
                                  'object_sha256': digest(obj), 'command': command})
    (output / 'provenance.json').write_text(json.dumps(report, indent=2) + '\n')

if __name__ == '__main__':
    main()
