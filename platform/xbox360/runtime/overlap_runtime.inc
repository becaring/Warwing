// Included at the end of the projected gameloop.cpp, after the sequential PortPushFrame.
// A worker resumes the game fibers for tick N+1 while the title thread replays tick N
// (Shipyard overlap/runtime.h). Interpolation settles before the first presentation,
// which builds one passive GUI and permits the next tick; every presentation redraws
// that capture. SP/DP completions keep their sequential order: tick N+1 draws into the
// other task context, and scene teardown or file loads wait for the replay with a fence.
#include "runtime/perf_trace.h"
#include "overlap/frame_worker.h"
#include "overlap/gui_frame_cache.h"
#include "overlap/runtime.h"
#include "imgui/gui_capture.h"
#include <ship/controller/controldeck/ControlDeck.h>
#include <libultraship/bridge/consolevariablebridge.h>
#include <libultraship/bridge/gfxdebuggerbridge.h>
#include <ship/config/ConsoleVariable.h>
#include <ship/window/gui/Gui.h>
#include <exception>
#include <stdexcept>
#include <vector>

namespace Ship { class IResource; }
extern "C" {
extern int gSYTaskmanTaskCount;
unsigned char port_diag_get_scene_curr(void);
int port_scene_wants_freeze_simulation(unsigned char scene_id);
float gfx_get_frame_tri_area_px(void);
}

namespace SmashOverlap {
typedef std::unordered_map<Mtx*, MtxF> ReplacementMap;
struct FramePacket {
    typedef Shipyard::Overlap::ResourceOwners<Ship::IResource> Owners;
    Gfx* commands;
    int viFrame;
    Owners resources;
    FramePacket() : commands(NULL), viFrame(0) {}
};

__declspec(thread) void* workerFiber = NULL;
// Reloc tokens, file ranges and fixup sets are shared with render lookups while a session runs.
// Sessions start and end at handoffs, so every lock pair sees the same session state.
struct RelocLock {
    CRITICAL_SECTION section;
    RelocLock() { InitializeCriticalSection(&section); }
};
static RelocLock relocLock;
__declspec(thread) int relocDepth = 0;
static int animationLoad;

static std::shared_ptr<Fast::Interpreter> CurrentInterpreter() {
    std::shared_ptr<Fast::Fast3dWindow> window =
        std::dynamic_pointer_cast<Fast::Fast3dWindow>(Ship::Context::GetInstance()->GetWindow());
    return window ? window->GetInterpreterWeak().lock() : std::shared_ptr<Fast::Interpreter>();
}
// The cached GUI draws through the native renderer, like Gui::ImGuiRenderDrawData.
struct GuiCapture : Shipyard::Overlap::ImGuiCapture {
    static void Draw(Cache& cache, uintptr_t texture) {
        if (std::shared_ptr<Fast::Interpreter> interpreter = CurrentInterpreter()) {
            interpreter->Flush();
            interpreter->XboxInvalidateTextureBindings();
        }
        Shipyard::Overlap::ImGuiCapture::Draw(cache, texture);
    }
};
static std::shared_ptr<Ship::Gui> CurrentGui() { return Ship::Context::GetInstance()->GetWindow()->GetGui(); }

struct Session : Shipyard::Overlap::Runtime<Session, FramePacket, GuiCapture> {
    Ship::ConsoleVariable::Snapshot frozenVariables;
    xbox_compat::chrono::steady_clock::time_point lastEnd;
    // Render-owned: every subframe's replacements, computed before the game resumes.
    std::vector<ReplacementMap> replacements;
    Session() : lastEnd(xbox_compat::chrono::steady_clock::now()) {}

    static void Log(const char* what, const char* detail) { port_log("SSB64: %s: %s\n", what, detail); }
    // Evaluated only while the game is idle at its handoff. Single-context scenes reuse the
    // replaying context, and freeze scenes time completions from the previous list's cost.
    static bool Requested() {
        return CVarGetInteger("gXbox.OverlapGameAndRender", 1) != 0 && !GfxDebuggerIsDebugging() &&
            gSYTaskmanTaskCount >= 2 && !port_scene_wants_freeze_simulation(port_diag_get_scene_curr()) &&
            !gbi_trace_is_enabled();
    }
    static bool InteractiveGui() { return CurrentGui()->XboxHasInteractiveGui(); }
    static void CommitGuiIntent() { CurrentGui()->XboxCommitOverlapIntent(); }
    static uintptr_t GameTexture() { return Ship::Context::GetInstance()->GetWindow()->GetGfxFrameBuffer(); }
    // Render lookups would wait on the reloc lock while the game waits on render.
    static void BeforeFence() {
        GameWorker& owner = session->worker;
        if (relocDepth && owner.retiredGeneration() < owner.previousGeneration())
            Abort("Replay fence under the reloc lock");
    }

    // One sequential tick without its render half; the packet carries the staged list.
    void BuildFrame() {
        // Game fibers return to whichever fiber resumed them.
        if (!workerFiber && !(workerFiber = ConvertThreadToFiber(NULL)))
            throw std::runtime_error("Worker fiber unavailable");
        FramePacket& packet = worker.buildingPacket();
        lbBackupApplyCheats();
        port_vi_simulate_vblank();
        osSendMesg(&gSYSchedulerTaskMesgQueue, port_make_os_mesg_int(INTR_VRETRACE), OS_MESG_NOBLOCK);
        CALL_EVENT(GamePreUpdateEvent);
        port_resume_service_threads();
        port_enhancement_stage_hazards_tick();
        packet.commands = sPendingDisplayList;
        sPendingDisplayList = nullptr;
        packet.viFrame = sFrameCount + 1;
        CALL_EVENT(GamePostUpdateEvent);
        sFrameCount++;
        if (!worker.publishAndWait()) throw std::runtime_error("Game handoff aborted");
    }

    void CaptureInput() { input.Capture(*Ship::Context::GetInstance()->GetControlDeck()); }
    void CaptureVariables() {
        Smash360PerfScope profileScope(SMASH_PERF_OVERLAP_VARIABLES);
        std::shared_ptr<Ship::ConsoleVariable> variables = Ship::Context::GetInstance()->GetConsoleVariables();
        variables->CaptureSnapshot(frozenVariables);
        variables->UseSnapshot(&frozenVariables);
    }
    void ReleaseVariables() { Ship::Context::GetInstance()->GetConsoleVariables()->UseSnapshot(NULL); }
    bool DrawPassiveGui() {
        Smash360PerfScope profileScope(SMASH_PERF_OVERLAP_GUI);
        std::shared_ptr<Ship::Gui> gui = CurrentGui();
        const bool passive = gui->XboxBeginOverlapDraw();
        gui->XboxFinishPassiveDraw();
        return passive;
    }

    void PresentIdle(Fast::Fast3dWindow& window, int subframes,
                     xbox_compat::chrono::steady_clock::time_point start) {
        static int sFreezePacing = -1;
        if (sFreezePacing < 0) {
            const char* env = XboxEnv_Get("SSB64_FREEZE_PACING");
            sFreezePacing = env != nullptr ? std::atoi(env) : 1;
        }
        if (!sFreezePacing) return;
        bool presented = false;
        for (int sub = 0; sub < subframes; sub++) {
            presented = window.PresentCurrentFramebuffer();
            if (!presented) break;
        }
        if (presented) return;
        auto target = start + xbox_compat::chrono::microseconds(16667);
        auto now = xbox_compat::chrono::steady_clock::now();
        if (now < target - xbox_compat::chrono::microseconds(2000))
            Shipyard::Clock::SleepFor(target - xbox_compat::chrono::microseconds(2000) - now);
        while (xbox_compat::chrono::steady_clock::now() < target) {
        }
    }

    void DrawCommands(Fast::Fast3dWindow& window, Gfx* commands, int subframes) {
        gbi_trace_begin_frame();
        portInterpBeginDraw();
        if (replacements.size() < static_cast<size_t>(subframes)) replacements.resize(subframes);
        for (int sub = 1; sub <= subframes; sub++) replacements[sub - 1] = portInterpGetReplacements(sub, subframes);
        // The first presentation permits the next tick, which records into a cleared set.
        portInterpEndDraw();
        for (int sub = 1; sub <= subframes; sub++) {
            sFrameTriCount = 0;
            sFrameRectPx = 0;
            sFrameLoadBytes = 0;
            try {
                window.DrawAndRunGraphicsCommands(commands, replacements[sub - 1]);
            } catch (long hr) {
                port_log("SSB64: CAUGHT DX shader exception HRESULT=0x%08lX\n", hr);
                break;
            } catch (...) {
                port_log("SSB64: CAUGHT unknown exception while processing display list\n");
                break;
            }
            if (sub == 1) {
                sLastDLTris = sFrameTriCount;
                sLastDLRectPx = sFrameRectPx;
                sLastDLLoadBytes = sFrameLoadBytes;
                sLastDLTriAreaPx = gfx_get_frame_tri_area_px();
            }
        }
        gbi_trace_end_frame();
    }

    void RenderReplays(const Ticket&, const FramePacket& packet) {
        const auto start = xbox_compat::chrono::steady_clock::now();
        std::shared_ptr<Fast::Fast3dWindow> window =
            std::dynamic_pointer_cast<Fast::Fast3dWindow>(Ship::Context::GetInstance()->GetWindow());
        if (!window) throw std::runtime_error("Overlap render window unavailable");
        window->HandleEvents();
        // Fast3D owns the widescreen flag; set it while the game is idle.
        port_widescreen_tick();
        gbi_trace_set_vi_frame(packet.viFrame);
        const int subframes = portInterpActiveSubframes();
        if (packet.commands) DrawCommands(*window, packet.commands, subframes);
        else PresentIdle(*window, subframes, start);
        const auto end = xbox_compat::chrono::steady_clock::now();
        portInterpNoteTicDuration(
            xbox_compat::chrono::duration_cast<xbox_compat::chrono::microseconds>(end - lastEnd).count());
        lastEnd = end;
        port_watchdog_note_frame_end();
        port_screenshot_init_once();
        port_screenshot_maybe_capture(packet.viFrame);
        if (packet.viFrame <= 60 || packet.viFrame % 60 == 0) {
            static auto sStartTime = end;
            port_log("SSB64: Frame %d complete (t=%.2fs, overlap)\n", packet.viFrame,
                     xbox_compat::chrono::duration<double>(end - sStartTime).count());
        }
    }
};
}

extern "C" int Shipyard_OverlapIsGameWorker(void) { return SmashOverlap::Session::OnGameWorker() ? 1 : 0; }
extern "C" int Shipyard_OverlapDrawGui(int begin) { return SmashOverlap::Session::DrawGui(begin); }
extern "C" int Shipyard_OverlapInputBlocked(unsigned kind, int* value) {
    return SmashOverlap::Session::InputBlocked(kind, value);
}
extern "C" void Shipyard_OverlapFence(void) { SmashOverlap::Session::Fence(); }
extern "C" void Smash360_RelocLock(void) {
    if (!SmashOverlap::Session::session) return;
    EnterCriticalSection(&SmashOverlap::relocLock.section);
    ++SmashOverlap::relocDepth;
}
extern "C" void Smash360_RelocUnlock(void) {
    if (!SmashOverlap::Session::session) return;
    --SmashOverlap::relocDepth;
    LeaveCriticalSection(&SmashOverlap::relocLock.section);
}
extern "C" void Smash360_OverlapSetAnimationLoad(int active) { SmashOverlap::animationLoad = active; }
extern "C" int Smash360_OverlapAnimationLoad(void) {
    return SmashOverlap::Session::OnGameWorker() && SmashOverlap::animationLoad;
}
// Other loads overwrite memory the replay may still read.
extern "C" void Smash360_RelocPrepareMutation(void) {
    if (!Smash360_OverlapAnimationLoad()) Shipyard_OverlapFence();
}
extern "C" void Shipyard_OverlapRunOnRender(void (*callback)(void*), void* context) {
    SmashOverlap::Session::RunOnRender(callback, context);
}
void Shipyard_OverlapRetainResource(const std::shared_ptr<Ship::IResource>& resource) {
    SmashOverlap::Session::Retain(resource);
}

void PortPushFrame(void) {
    if (!SmashOverlap::Session::RunFrame()) PortPushFrameSequential();
}
