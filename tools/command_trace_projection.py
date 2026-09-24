"""Sample the whole original command walk, preserving debugger and early exits."""
from profile_projections import once,enter

def transform(text):
    text='#include "runtime/command_trace.h"\n'+text
    text=enter(text,'Interpreter::Run','SmashWalkTrace walkTrace;')
    text=once(text,'    g_exec_stack.start((F3DGfx*)commands);',
        '    walkTrace.Mark(SMASH_WALK_EXECUTE);\n    g_exec_stack.start((F3DGfx*)commands);')
    text=once(text,'    while (!g_exec_stack.cmd_stack.empty()) {',
        '    while (!g_exec_stack.cmd_stack.empty()) {\n        SmashCommandTrace commandTrace;')
    text=once(text,'        gfx_step();',
        '        if (commandTrace.active) gfx_step<true>(commandTrace);\n        else gfx_step<false>(commandTrace);')
    text=once(text,'    } // Release the dispatch pin before the existing final Flush/compose.',
        '    } // Release the dispatch pin before the existing final Flush/compose.\n    walkTrace.Mark(SMASH_WALK_FINISH);')
    text=once(text,'static void gfx_step() {',
        'static int sXboxWalkedPastWarningCount = 0;\ntemplate<bool TraceCommand>\nstatic void gfx_step(SmashCommandTrace& commandTrace) {\n    if (TraceCommand) commandTrace.Mark(SMASH_CMD_FETCH);')
    # Both diagnostic instantiations execute the same production path. Keep
    # the original ten-warning budget shared across sampled/unsampled calls.
    text=once(text,'static int sCount = 0;\n            if (sCount < 10)',
        'int& sCount = sXboxWalkedPastWarningCount;\n            if (sCount < 10)')
    text=once(text,'        Smash360PerfScope boundsScope(SMASH_PERF_DL_BOUNDS);',
        '        if (TraceCommand) commandTrace.Mark(SMASH_CMD_BOUNDS);\n        Smash360PerfScope boundsScope(SMASH_PERF_DL_BOUNDS);')
    text=once(text,'    int8_t opcode = (int8_t)(cmd->words.w0 >> 24);\n\n    if (sGbiTraceCallback)',
        '    if (TraceCommand) commandTrace.Mark(SMASH_CMD_TRACE);\n    int8_t opcode = (int8_t)(cmd->words.w0 >> 24);\n    if (TraceCommand) commandTrace.Opcode(static_cast<uint8_t>(opcode));\n\n    if (sGbiTraceCallback)')
    text=once(text,'    Smash360PerfScope opcodeScope(',
        '    if (TraceCommand) commandTrace.Mark(SMASH_CMD_DISPATCH);\n    Smash360PerfScope opcodeScope(')
    return text
