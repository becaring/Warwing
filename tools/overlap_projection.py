"""Game/render overlap: the game worker builds tick N+1 while render replays tick N.

The runtime is platform/xbox360/runtime/overlap_runtime.inc. Shared libultraship
hooks (CVar snapshot, resource retention, texture cache jobs) come from Shipyard.
"""
import re
from profile_projections import enter


def once(text, old, new, count=1):
    if text.count(old) != count:
        raise ValueError("Overlap projection anchor drift: " + repr(old[:100]))
    return text.replace(old, new)


def gameloop(text):
    text = once(text, 'void PortPushFrame(void)\n{', 'static void PortPushFrameSequential(void)\n{')
    return once(text, 'void PortGameShutdown(void)\n{',
                '#include "overlap_runtime.inc"\n\nvoid PortGameShutdown(void)\n{\n\tSmashOverlap::Session::Shutdown();')


def gui_header(text):
    from xbox360_platform import overlap_lus
    return overlap_lus.gui_header(text)


def gui(text):
    """The first presentation of each tick builds one passive GUI while the game waits;
    every presentation redraws that capture. Apply after range lowering."""
    from xbox360_platform import overlap_lus
    text = overlap_lus.gui_capture(
        text, "    uintptr_t fb = Ship::Context::GetInstance()->GetWindow()->GetGfxFrameBuffer();")
    return overlap_lus.gui_passive_game(overlap_lus.gui_passive(text), "Gui")


def taskman(source):
    # Scene teardown follows the gfx-idle wait; the replay may still read scene memory.
    source = once(source, b'func_80005BFC();', b'func_80005BFC(); Shipyard_OverlapFence();')
    # The replaying context stays busy until the game's next handoff.
    source = once(source, b'if (D_80046638[i] == 0)',
                  b'if (D_80046638[i] == 0 && !(Shipyard_OverlapIsGameWorker() && i == gSYTaskmanTaskID'
                  b' && gSYTaskmanTaskCount > 1))')
    return b'void Shipyard_OverlapFence(void);\nint Shipyard_OverlapIsGameWorker(void);\n' + source


RELOC = '''extern "C" void Smash360_RelocLock(void);
extern "C" void Smash360_RelocUnlock(void);
extern "C" void Smash360_RelocPrepareMutation(void);
struct Smash360RelocGuard {
    Smash360RelocGuard() { Smash360_RelocLock(); }
    ~Smash360RelocGuard() { Smash360_RelocUnlock(); }
};
'''
LOCKED = 'Smash360RelocGuard relocGuard;'
# Loads replace bytes the replay may read; only fighter animation heaps are game-only.
MUTATING = 'Smash360_RelocPrepareMutation(); Smash360RelocGuard relocGuard;'
# Render reads reloc state per lookup; the game holds it across whole loads and fixups.
RELOC_FUNCTIONS = {
    'port/resource/RelocPointerTable.cpp': (
        [], ['portRelocRegisterPointer', 'portRelocResolvePointer', 'portRelocResolvePointerDebug',
             'portRelocTryResolvePointer', 'portRelocInvalidateRange', 'portRelocResetPointerTable']),
    'port/bridge/lbreloc_bridge.cpp': (
        ['portRelocLoadFileFromBytes', 'portRelocLoadFileFromBytesPrivate',
         'port_taskman_evict_arena_caches', 'lbRelocInitSetup'],
        ['portRelocFindContainingFile', 'portRelocFindFileIdAndBase', 'portRelocEvictFileRangesInRange']),
    'port/bridge/particle_bank_bridge.cpp': (['portParticleLoadBank'], []),
}
BYTESWAP = re.compile(r'(?m)^extern "C" [^;{]*?\b((?:portFixup|portReloc)\w*)\s*\([^;{}]*\)\s*\{')
CAPTURE = {
    'port_capture_register_fb_for_subrect': '''if (Shipyard_OverlapIsGameWorker()) {
        struct Job {
            const void* base; unsigned int size; float u0, v0, u1, v1; int result;
            static void Run(void* opaque) {
                Job& job = *static_cast<Job*>(opaque);
                job.result = port_capture_register_fb_for_subrect(job.base, job.size, job.u0, job.v0, job.u1, job.v1);
            }
        } job = {base, size_bytes, u0, v0, u1, v1, 0};
        Shipyard_OverlapRunOnRender(Job::Run, &job);
        return job.result;
    }''',
    'port_capture_release_range': '''if (Shipyard_OverlapIsGameWorker()) {
        struct Job {
            const void* base;
            static void Run(void* opaque) { port_capture_release_range(static_cast<Job*>(opaque)->base); }
        } job = {base};
        Shipyard_OverlapRunOnRender(Job::Run, &job);
        return;
    }''',
    'port_capture_release_all': '''if (Shipyard_OverlapIsGameWorker()) {
        struct Job { static void Run(void*) { port_capture_release_all(); } };
        Shipyard_OverlapRunOnRender(Job::Run, NULL);
        return;
    }''',
    'port_capture_set_force_render_to_fb': '''if (Shipyard_OverlapIsGameWorker()) {
        struct Job {
            int enable;
            static void Run(void* opaque) { port_capture_set_force_render_to_fb(static_cast<Job*>(opaque)->enable); }
        } job = {enable};
        Shipyard_OverlapRunOnRender(Job::Run, &job);
        return;
    }''',
}
WORKER = ('extern "C" int Shipyard_OverlapIsGameWorker(void);\n'
          'extern "C" void Shipyard_OverlapRunOnRender(void (*callback)(void*), void* context);\n')


def port(relative, text):
    """Run after the port projector's lowering for each file."""
    if relative in RELOC_FUNCTIONS:
        mutating, locked = RELOC_FUNCTIONS[relative]
        for name in mutating:
            text = enter(text, name, MUTATING)
        for name in locked:
            text = enter(text, name, LOCKED)
        return RELOC + text
    if relative == 'port/bridge/lbreloc_byteswap.cpp':
        text, count = BYTESWAP.subn(lambda match: match.group(0) + '\n    ' + LOCKED, text)
        if count < 15:
            raise ValueError('Reloc fixup entry drift: ' + str(count))
        return RELOC + text
    if relative == 'port/bridge/framebuffer_capture.cpp':
        # Capture issues GPU work; the game's calls run on render after the replay.
        for name, code in CAPTURE.items():
            text = enter(text, name, code)
        return WORKER + text
    return text


def figatree(source):
    # Status changes reload the fighter's animation heap, which display lists never read.
    statement = re.compile(rb'lbRelocGetForceExternHeapFile\(motion_desc->anim_file_id,[^;]*;')
    text, count = statement.subn(lambda match: b'Smash360_OverlapSetAnimationLoad(1); ' + match.group(0)
                                 + b' Smash360_OverlapSetAnimationLoad(0);', source)
    if count != 1:
        raise ValueError('Figatree load drift: ' + str(count))
    return b'void Smash360_OverlapSetAnimationLoad(int active);\n' + text


def interpreter(text):
    # Animation loads skip cache eviction: no texture or list was ever drawn from that heap.
    for name in ('portTextureCacheDeleteRange', 'portPackedDisplayListCacheDeleteRange'):
        text = enter(text, name, 'if (Smash360_OverlapAnimationLoad()) return;')
    return 'extern "C" int Smash360_OverlapAnimationLoad(void);\n' + text
