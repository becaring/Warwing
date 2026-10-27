"""Count the port's RCP cost model inline instead of through the GBI trace callback.

gameloop installs gbi_trace_callback unconditionally so the cost counters see
every command. That puts an indirect call on every command, and the callback's
presence also disables TRI2 runs, so shared triangle rows and the run NDC
cache are never used. The interpreter now counts the same opcodes itself, and
only calls the callback while GBI tracing is actually logging.
"""
import re
from profile_projections import once

COUNTERS = (('sFrameTriCount', 'gSmashRcpFrameTris'),
            ('sFrameRectPx', 'gSmashRcpFrameRectPx'),
            ('sFrameLoadBytes', 'gSmashRcpFrameLoadBytes'))

def port(text):
    for local, shared in COUNTERS:
        text = once(text, 'static int %s = 0;\n' % local,
                    'extern "C" int %s = 0;\nstatic int& %s = %s;\n' % (shared, local, shared))
    # Keep the logging; the interpreter owns the opcode switch now.
    body = re.compile(r'\n\tuint8_t opcode = \(uint8_t\)\(\(w0 >> 24\) & 0xFFu\);\n\tswitch \(opcode\) \{.*?\n\tdefault:\n\t\tbreak;\n\t\}\n\}', re.S)
    if len(body.findall(text)) != 1:
        raise ValueError('RCP cost callback anchor changed')
    return body.sub('\n}', text, 1)

COUNT = '''// Same opcode costs gameloop's gbi_trace_callback used to accumulate for
// port_get_last_dl_defer_n; see port/gameloop.cpp for the derivation.
extern "C" int gSmashRcpFrameTris, gSmashRcpFrameRectPx, gSmashRcpFrameLoadBytes;
extern "C" int gbi_trace_is_enabled(void);
// Snapshotted per Run: the callback only logs while GBI tracing is enabled.
static bool sXboxGbiTrace = false;
static inline void XboxCountRcpCost(uintptr_t w0, uintptr_t w1) {
    switch ((uint8_t)(w0 >> 24)) {
    case 0x05: gSmashRcpFrameTris += 1; break;
    case 0x06: case 0x07: gSmashRcpFrameTris += 2; break;
    case 0xE4: case 0xF6: {
        const int w = ((int)((w0 >> 12) & 0xFFF) - (int)((w1 >> 12) & 0xFFF)) >> 2;
        const int h = ((int)(w0 & 0xFFF) - (int)(w1 & 0xFFF)) >> 2;
        if (w > 0 && h > 0) gSmashRcpFrameRectPx += w * h;
        break;
    }
    case 0xF3: case 0xF4: gSmashRcpFrameLoadBytes += 512; break;
    }
}
'''

def interpreter(text):
    text = once(text, 'bool gfx_tri2_handler_f3dex(F3DGfx** cmd0) {', COUNT + 'bool gfx_tri2_handler_f3dex(F3DGfx** cmd0) {')
    text = once(text, '    if (sGbiTraceCallback) {',
                '    XboxCountRcpCost(cmd->words.w0, cmd->words.w1);\n    if (sXboxGbiTrace) {')
    run = re.compile(r'\n    sXboxTriangleRunEnabled = [^\n]*;\n')
    if len(run.findall(text)) != 1:
        raise ValueError('Triangle run start anchor changed')
    text = run.sub(lambda m: m.group(0) + '    sXboxGbiTrace = sGbiTraceCallback != nullptr && gbi_trace_is_enabled() != 0;\n', text, 1)
    text = once(text, '!sXboxTracedDispatch && !sGbiTraceCallback;', '!sXboxTracedDispatch && !sXboxGbiTrace;')
    # Commands a TRI2 run consumes never reach gfx_step; count them here.
    return once(text, '        *cmd0 = ++cmd;\n',
                '        XboxCountRcpCost((cmd + 1)->words.w0, (cmd + 1)->words.w1);\n        *cmd0 = ++cmd;\n')
