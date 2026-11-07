"""Apply the reviewed Audio/Config patch, checking the source context exactly."""
from pathlib import Path
import hashlib, re

ROOT = Path(__file__).resolve().parents[4]
PATCH = ROOT / 'platform/xbox360/audio/integration-proposal.patch'
SHA = '72a997c9a81842508d2d3f62e56f000e2a826d3936113eb05a7efe99bcef0ba4'

def apply(relative, original):
    raw = PATCH.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SHA:
        raise ValueError('Reviewed audio integration patch changed')
    lines = raw.decode().splitlines(True)
    marker = '--- a/upstream/BattleShip/libultraship/' + relative + '\n'
    if marker not in lines:
        return original
    start = lines.index(marker) + 2
    source = original.splitlines(True)
    output, cursor = [], 0
    while start < len(lines) and not lines[start].startswith('--- '):
        match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', lines[start])
        if not match:
            raise ValueError('Invalid reviewed patch hunk')
        target = int(match.group(1)) - 1
        if target < cursor:
            raise ValueError('Overlapping reviewed patch hunks')
        output.extend(source[cursor:target]); cursor = target; start += 1
        while start < len(lines) and not lines[start].startswith(('@@ ', '--- ')):
            line = lines[start]; start += 1
            if line[0] in ' -':
                if cursor >= len(source) or source[cursor] != line[1:]:
                    raise ValueError('Reviewed audio patch context mismatch: ' + relative)
                cursor += 1
            if line[0] in ' +':
                output.append(line[1:])
    output.extend(source[cursor:])
    return ''.join(output)
