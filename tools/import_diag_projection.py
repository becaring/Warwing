"""Move BattleShip's import-log acceptance before its diagnostic argument reads."""
import re
from profile_projections import once

GUARD='''    bool armed = Ssb64RenderDiagArmedTake();
    if (!armed && (!Ssb64RenderDiagMatches(metadata, addr) || !Ssb64RenderDiagTakeSlot())) {
        return;
    }

'''

def transform(text):
    text=once(text,GUARD,'')
    text=once(text,'static void Ssb64RenderDiagLogImport(','''// Xbox: preserve armed/filter/quota ordering before preparing the log payload.
static bool Ssb64RenderDiagShouldLogImport(const RawTexMetadata* metadata, const void* addr) {
    bool armed = Ssb64RenderDiagArmedTake();
    return armed || (Ssb64RenderDiagMatches(metadata, addr) && Ssb64RenderDiagTakeSlot());
}

static void Ssb64RenderDiagLogImport(''')
    pattern=r'(?m)^([ ]*)Ssb64RenderDiagLogImport\("(?:import|cache-hit|cache-miss)"[\s\S]*?importReplacement\);'
    calls=list(re.finditer(pattern,text))
    if len(calls)!=3 or text.count('Ssb64RenderDiagLogImport(')!=4:
        raise ValueError('Re-audit import diagnostic callers and payload side effects')
    for match in reversed(calls):
        indent=match[1]
        call='\n'.join('    '+line for line in match[0].splitlines())
        text=text[:match.start()]+indent+'if (Ssb64RenderDiagShouldLogImport(metadata, origAddr)) {\n'+call+'\n'+indent+'}'+text[match.end():]
    return text
