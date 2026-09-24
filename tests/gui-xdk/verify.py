"""Check untouched production frame flow and exact emitted font payload."""
from pathlib import Path
import hashlib,json,re,runpy
ROOT=Path(__file__).resolve().parents[2]
G=runpy.run_path(str(ROOT/'tools/prepare_gui_xdk.py'))
UP=ROOT/'upstream/BattleShip/libultraship'
OUT=ROOT/'scratch/gui-xdk'
def main():
    original=(UP/'src/ship/window/gui/Gui.cpp').read_text()
    adapted=G['transform']('src/ship/window/gui/Gui.cpp',original)
    methods=['void Gui::DrawGame()','void Gui::CalculateGameViewport()',
             'void Gui::ApplyResolutionChanges()','int16_t Gui::GetIntegerScaleFactor()',
             'void Gui::StartDraw()','void Gui::EndDraw()','void Gui::StartFrame()',
             'void Gui::EndFrame()']
    for signature in methods:
        a,b=G['body_span'](original,signature);c,d=G['body_span'](adapted,signature)
        assert original.encode()[a:b]==adapted.encode()[c:d],signature+' production body changed'
    font=(UP/'include/ship/window/gui/Fonts.h').read_text()
    literals=re.findall(r'"((?:[^"\\]|\\.)*)"',font[font.index('static const char'):])
    escape={'?':b'?','"':b'"','\\':b'\\'}
    payload=b''
    # Independently decode only the actual C escapes in this pinned base85 data.
    for literal in literals:
        parts=re.split(r'(\\.)',literal)
        payload+=b''.join(escape[p[1]] if p.startswith('\\') else p.encode('ascii') for p in parts)
    payload+=b'\0'
    obj=(OUT/'Gui.obj').read_bytes()
    assert len(payload)==155711
    assert obj.count(payload)==1,'Native production Gui object lacks the exact original font bytes'
    report={'unchanged_production_methods':methods,'font_bytes':len(payload),
            'font_sha256':hashlib.sha256(payload).hexdigest(),'font_present_in_real_gui_powerpc_object':True,
            'gui_object_sha256':hashlib.sha256(obj).hexdigest(),'boot_proven':False}
    (OUT/'production-flow-verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS eight actual frame/viewport methods unchanged; all155711 font bytes present in native Gui object')
if __name__=='__main__':main()
