"""Inventory actual format calls; keep diagnostic deviations out of data keys."""
from pathlib import Path
import hashlib,json,runpy
ROOT=Path(__file__).resolve().parents[1]
UP=ROOT/'upstream/BattleShip'
P=runpy.run_path(str(ROOT/'tools/prepare_prism_xdk.py'))


def main():
    manifest=json.loads((ROOT/'scratch/application-xdk/source-manifest.json').read_text())
    files={UP/r['path'] for r in manifest['sources'] if r['selected']}
    files.update((UP/'libultraship/include').rglob('*.h'))
    files.update((UP/'port').rglob('*.h'));files.update((UP/'port').rglob('*.hpp'))
    records=[]
    known={'port/gui/UIWidgets.cpp':'UI IDs: string name plus integer flag index',
           'port/gui/PortMenu.cpp':'UI labels and paths: strings and integer player/count values',
           'port/gui/Menu.cpp':'UI labels, IDs and errors: strings and integer indices',
           'libultraship/src/libultraship/window/gui/GfxDebuggerWindow.cpp':'Debugger display; breakpoint ID uses pointer, texture resource name uses integer index',
           'libultraship/src/fast/interpreter.cpp':'Error messages only; no formatted data feeds interpreter state'}
    for path in sorted(files):
        relative=path.relative_to(UP).as_posix()
        if not path.exists():path=ROOT/'scratch/generated'/relative
        data=path.read_bytes()
        if b'fmt::' not in data and b'SPDLOG_' not in data:continue
        for node in P['walk'](P['PARSER'].parse(data).root_node):
            if node.type!='call_expression':continue
            callee=P['field'](node,'function').text.decode()
            if P['field'](node,'function').type=='field_expression':continue
            if not (callee.startswith('fmt::') or callee.startswith('SPDLOG_')):continue
            if callee=='fmt::ptr':continue
            args=P['field'](node,'arguments').named_children
            if callee.startswith('fmt::') and (callee!='fmt::format' or relative not in known):
                raise ValueError('Unreviewed nonlogging formatter consumer '+relative+': '+callee)
            row={'path':relative,'sha256':hashlib.sha256(data).hexdigest(),'line':node.start_point.row+1,
                 'callee':callee,'arguments':[n.text.decode() for n in args],
                 'classification':'diagnostic logger output' if callee.startswith('SPDLOG_') else known[relative]}
            if callee=='fmt::format' and len(args)-1>15:raise ValueError('Direct formatter arity exceeds verified fixed API')
            if callee.startswith('SPDLOG_') and len(args)-1>39:raise ValueError('Logger arity exceeds verified fixed API')
            records.append(row)
    output=ROOT/'scratch/audit/format-consumers.json'
    output.write_text(json.dumps({'scope':'Selected production translation units and all current public/port headers; AST calls exclude comments but conservatively include inactive preprocessor branches',
                                 'limits':'No arbitrary new fmt API permitted; default float spelling deviation limited to displayed diagnostics. Actual argument type proofs require reviewed expressions and native compilation.',
                                 'calls':records},indent=2)+'\n')
    print('Reviewed formatter inventory:',len(records),'calls;',sum(r['callee']=='fmt::format' for r in records),'direct fmt calls')


if __name__=='__main__':main()
