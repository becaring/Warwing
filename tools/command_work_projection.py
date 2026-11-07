"""Narrow Xbox adaptations to the command walk and cost callback."""
import re
from profile_projections import once

def header(text):
    return '#include "fast3d/command_stack.h"\n'+once(text,
        'std::stack<F3DGfx*> cmd_stack = {};',
        'Shipyard::Fast3D::CommandStack<F3DGfx*> cmd_stack = {};')

def port(text):
    return once(text,
        '\tgbi_trace_log_cmd((unsigned long long)w0, (unsigned long long)w1, dl_depth);',
        '\tif (gbi_trace_is_enabled())\n\t\tgbi_trace_log_cmd((unsigned long long)w0, (unsigned long long)w1, dl_depth);')

def interpreter(text):
    operations=set(re.findall(r'\bcmd_stack\.(\w+)\s*\(',text))
    if operations!={'empty','pop','push','top','size'}:
        raise ValueError('Re-audit cached command-stack operations: '+str(operations))
    # The old XDK deque::back materializes iterators even in Release. This
    # read exists only for debugger path construction; defer it until needed.
    # Keep the original container and references across G_DL pushes intact.
    text = once(text,
        '        auto cmd = g_exec_stack.cmd_stack.top();\n\n        if (dbg->IsDebugging()) {',
        '        if (dbg->IsDebugging()) {\n            auto cmd = g_exec_stack.cmd_stack.top();')
    # SoH uses native Gfx directly. BattleShip additionally handles widened
    # desktop lists, whose stride correction may already equal SegAddr's
    # result on Xenon. Do not scan reloc files when that correction cannot
    # change the result. Keep all corrections and token precedence intact.
    return once(text, '''            if (segBase != 0) {
                uintptr_t segFileBase = 0;''', '''            const uint32_t xboxN64Offset = (uint32_t)(cmd->words.w1 & 0x00FFFFFF);
            const uintptr_t xboxStridedAddress = segBase + (xboxN64Offset / PORT_PACKED_GFX_SIZE) * sizeof(F3DGfx);
            if (segBase != 0 && (xboxN64Offset & 7u) == 0u &&
                (uintptr_t)subGFX != xboxStridedAddress) {
                uintptr_t segFileBase = 0;''')

# Syncs are ~12% of SSB64's intro commands and their handler does nothing; each
# still paid a full Run iteration. Step over a run of them where it starts,
# bounds-checking each before reading it, only when the handler left this
# list on top. Traced, GBI-traced and debugger walks keep one step per command.
STUB_SKIP = '''    ++cmd;
    if (!TraceCommand && sXboxTriangleRunEnabled && !sXboxGbiTrace && &cmd == &g_exec_stack.currCmd() &&
        ucode_handler_index < ucode_handlers.size()) {
        const UcodeHandler& xboxHandlers = *ucode_handlers[ucode_handler_index];
        while (!(sDLBoundsCheck && XboxWalkedPast((uintptr_t)cmd)) &&
               xboxHandlers.at((int8_t)(cmd->words.w0 >> 24)).second == gfx_stubbed_command_handler) {
            Smash360_PerfCount(SMASH_COUNT_COMMANDS);
            ++cmd;
        }
    }
}

void Interpreter::SpReset() {'''

def skip_stubs(text):
    """Apply after rcp_cost_projection, which owns sXboxGbiTrace."""
    return once(text, '    ++cmd;\n}\n\nvoid Interpreter::SpReset() {', STUB_SKIP)
