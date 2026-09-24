"""Retain one selected interpreter owner for the existing production DL walk."""
from profile_projections import once

def transform(text):
    text = '#include "fast3d/dispatch_owner.h"\n' + text
    text = once(text, 'static std::weak_ptr<Interpreter> mInstance;', '''static std::weak_ptr<Interpreter> mInstance;
typedef Shipyard::Fast3D::DispatchOwner<Interpreter> XboxDispatchOwner;
static __declspec(thread) XboxDispatchOwner* sXboxDispatchOwner = 0;
static __forceinline Interpreter* XboxDispatchInterpreter() {
    if (sXboxDispatchOwner) return sXboxDispatchOwner->Get(mInstance);
    return XboxDispatchOwner::TemporaryBorrow(mInstance);
}''')
    text = once(text, '    mInstance = gfx;', '''    mInstance = gfx;
    XboxDispatchOwner::Invalidate(sXboxDispatchOwner);''')
    anchor = 'gfx = mInstance.lock().get();'
    if text.count(anchor) != 90:
        raise ValueError('Expected 90 profiled temporary interpreter owners')
    text = text.replace(anchor, 'gfx = XboxDispatchInterpreter();')
    text = once(text, '    g_exec_stack.start((F3DGfx*)commands);', '''    {
    XboxDispatchOwner dispatchOwner(sXboxDispatchOwner, mInstance);
    g_exec_stack.start((F3DGfx*)commands);''')
    text = once(text, '        gfx_step();\n    }\n\n    Flush();', '''        gfx_step();
    }
    } // Release the dispatch pin before the existing final Flush/compose.

    Flush();''')
    return text
