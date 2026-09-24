"""Summarize final /W3 logs without hiding source or ABI-sensitive warnings."""
from pathlib import Path
from collections import Counter
import json
import re

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'scratch/game-xdk'


def main():
    report = json.loads((OUT / 'compile-audit.json').read_text())
    warnings, booleans = [], []
    for result in report['results']:
        for line in (ROOT / result['log']).read_text(errors='replace').splitlines():
            match = re.search(r'warning (C\d+): (.*)', line)
            if match:
                warnings.append({'translation_unit': result['path'], 'code': match[1], 'message': match[2], 'diagnostic': line})
        if result.get('boolean_lowering'):
            booleans.append({'translation_unit': result['path'], **result['boolean_lowering']})
    implicit = sorted({re.search(r"'([^']+)'", warning['message'])[1] for warning in warnings if warning['code'] == 'C4013'})
    summary = {'compiled': report['passed'], 'selected': report['selected'],
               'warnings_by_code': dict(sorted(Counter(w['code'] for w in warnings).items())),
               'implicit_declarations': implicit, 'boolean_translation_units': booleans, 'warnings': warnings}
    (OUT / 'diagnostics.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({key: value for key, value in summary.items() if key not in ('warnings', 'boolean_translation_units')}, indent=2))


if __name__ == '__main__':
    main()
