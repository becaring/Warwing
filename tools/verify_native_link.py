"""Verify production symbol ownership and record the actual XEX; not boot proof."""
from pathlib import Path
import hashlib, json, re

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / 'scratch/application-xdk/native/build'
EXPECTED = {
    'syMainLoop': 'decomp__src__sys__main.obj',
    'osSendMesg': 'port__stubs__n64_stubs.obj',
    'osRecvMesg': 'port__stubs__n64_stubs.obj',
    'osViGetCurrentFramebuffer': 'port__stubs__n64_stubs.obj',
}

def main():
    text = (BUILD / 'Smash360.map').read_text(errors='strict')
    expected = dict(EXPECTED)
    items = json.loads((BUILD.parent / 'project-items.json').read_text())['Smash360']
    for symbol, source in [('port_coroutine_create', 'port/coroutine_win32.cpp'),
                           ('PortGameInit', 'port/gameloop.cpp')]:
        if sum(item['path'] == source for item in items) != 1:
            raise RuntimeError('Missing production source: ' + source)
        expected[symbol] = '%s_%s.obj' % (Path(source).stem, hashlib.sha256(source.encode()).hexdigest()[:16])
    symbols = {}
    for symbol, owner in expected.items():
        matches = re.findall(r'^\s*\w+:\w+\s+' + re.escape(symbol) +
                             r'\s+([\da-fA-F]+)\s+f\s+(.+)$', text, re.M)
        if len(matches) != 1 or matches[0][1].strip() != owner:
            raise RuntimeError('Incorrect production symbol owner: ' + symbol + ' ' + repr(matches))
        symbols[symbol] = {'address': matches[0][0], 'object': owner}
    if 'UnavailableLusFallbackViTimer' in text or re.search(r'\bos_(?:vi|mesg)\.obj\b', text):
        raise RuntimeError('A competing LUS game-scheduler fallback was linked')
    executable = (BUILD / 'Warwing.xex').read_bytes()
    if executable[:4] != b'XEX2':
        raise RuntimeError('Output is not an XEX2 executable')
    result = {'xex': str((BUILD / 'Warwing.xex').relative_to(ROOT)),
              'bytes': len(executable), 'sha256': hashlib.sha256(executable).hexdigest(),
              'symbols': symbols, 'visible_boot_verified': False,
              'scope': 'Static executable and production symbol ownership only'}
    (BUILD / 'native-link-verification.json').write_text(json.dumps(result, indent=2) + '\n')
    print('XEX2 and actual BattleShip scheduler/VI/message symbol ownership verified')

if __name__ == '__main__':
    main()
