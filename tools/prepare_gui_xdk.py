"""Stage the real LUS GUI/presentation with SoH-derived Xbox backend dispatch.

The current Gui DrawGame, viewport, resource and frame flow remain authoritative.
This generator is deliberately fail-closed on source drift and unknown syntax.
"""
from pathlib import Path
import argparse, hashlib, json, re, runpy, subprocess
import texture_binding_projection
import profile_projections
ROOT=Path(__file__).resolve().parents[1]
from platform_base import resolve as resolve_platform_base
PLATFORM_BASE=resolve_platform_base(ROOT)
UP=ROOT/'upstream/BattleShip'
LUS=UP/'libultraship'
OUT=ROOT/'scratch/gui-xdk'
BASE=ROOT/'platform/xbox360/cpp-compat/gui'
PRISM=runpy.run_path(str(ROOT/'tools/prepare_prism_xdk.py'))
LOWER=runpy.run_path(str(ROOT/'platform/xbox360/cpp-compat/config/lowering.py'))
STAGE=runpy.run_path(str(ROOT/'platform/xbox360/game-compat/source_tree.py'))['stage_sources']
CONFIG=runpy.run_path(str(ROOT/'tools/prepare_config_xdk.py'))
once=PRISM['once']


def body_span(text, signature):
    start=text.index(signature)
    data=text.encode()
    matches=[n for n in PRISM['walk'](PRISM['PARSER'].parse(data).root_node)
             if n.type=='function_definition' and n.start_byte==len(text[:start].encode())]
    if len(matches)!=1: raise ValueError('Missing exact function AST: '+signature)
    body=PRISM['field'](matches[0],'body')
    return body.start_byte,body.end_byte


def platform_body(text, signature, native):
    data=text.encode(); start,end=body_span(text,signature)
    original=data[start+1:end-1].decode()
    replacement='{\n#ifdef _XBOX\n'+native+'\n#else\n'+original+'\n#endif\n}'
    return (data[:start]+replacement.encode()+data[end:]).decode()


def transform(relative,text):
    if relative=='include/ship/window/gui/Fonts.h':
        # XDK caps a concatenated string at 65535 bytes. Preserve the exact
        # static const char array, including its terminating zero, as numbers.
        marker='static const char fontawesome_compressed_data_base85[155710 + 1] ='
        first=text.index(marker);tail=text[first+len(marker):]
        tokens=re.findall(r'"((?:[^"\\]|\\.)*)"',tail)
        if re.sub(r'"(?:[^"\\]|\\.)*"','',tail).strip()!=';':raise ValueError('Font initializer changed')
        escapes={'?':'?','"':'"','\\':'\\'}
        joined=''.join(re.sub(r'\\(.)',lambda m:escapes[m[1]],token) for token in tokens)
        data=joined.encode('ascii')+b'\0'
        if len(data)!=155711:raise ValueError('Font byte count changed')
        text=text[:first]+marker+' {\n'+ '\n'.join(','.join(str(v) for v in data[i:i+64])+',' for i in range(0,len(data),64))+'\n};\n'
    elif relative=='include/ship/window/gui/Gui.h':
        text=once(text,'#include <SDL2/SDL.h>','#ifdef _XBOX\nstruct SDL_Renderer; // Opaque pointer in the existing Metal union member.\n#else\n#include <SDL2/SDL.h>\n#endif')
        # The public class stores pointers to these actual classes. Include their
        # definitions in Gui.cpp, avoiding unrelated implementation dependencies.
        for name in ('ConsoleWindow','InputEditorWindow','StatsWindow','GameOverlay','GuiWindow','GuiMenuBar'):
            text=once(text,'#include "ship/window/gui/'+name+'.h"','namespace Ship { class '+name+'; }')
        text=once(text,'#include "ship/controller/physicaldevice/SDLAddRemoveDeviceEventHandler.h"','namespace Ship { class SDLAddRemoveDeviceEventHandler; }')
        text=once(text,'#include "fast/resource/type/Texture.h"','namespace Fast { class Texture; }')
    elif relative=='src/ship/window/gui/Gui.cpp':
        # Boundary diagnostics for the real startup path, with no alternate
        # initialization or skipped GUI/resource operation.
        text = '#include "runtime/runtime.h"\n' + text
        for anchor, label in (
            ('    ImGuiContext* ctx = ImGui::CreateContext();', 'create context'),
            ('    mImGuiIo->Fonts->AddFontDefault();', 'default font'),
            ('    mImGuiIo->Fonts->AddFontFromMemoryCompressedBase85TTF(', 'icon font'),
            ('    GetGuiWindow("Stats")->Init();', 'Stats window'),
            ('    GetGuiWindow("Input Editor")->Init();', 'Input Editor'),
            ('    GetGuiWindow("Console")->Init();', 'Console window'),
            ('    GetGuiWindow("GfxDebuggerWindow")->Init();', 'graphics debugger'),
            ('    GetGameOverlay()->Init();', 'game overlay'),
            ('    ImGuiWMInit();', 'platform init'),
            ('    ImGuiBackendInit();', 'renderer init')):
            text = once(text, anchor, '    Smash360_Log("GUI startup: '+label+'");\n'+anchor)
        text = once(text, '    ImGuiBackendInit();', '    ImGuiBackendInit();\n    Smash360_Log("GUI startup complete");')
        direct='\n'.join('#include "ship/window/gui/'+name+'.h"' for name in ('ConsoleWindow','InputEditorWindow','StatsWindow','GameOverlay','GuiWindow','GuiMenuBar'))
        text=once(text,'#include "ship/window/gui/Gui.h"','#include "ship/window/gui/Gui.h"\n'+direct+'\n#include "ship/controller/physicaldevice/SDLAddRemoveDeviceEventHandler.h"\n#include "ship/window/MouseStateManager.h"\n#ifdef _XBOX\n#include "imgui_xenos.h"\n#endif')
        text=once(text,'#else\n#include <SDL2/SDL_hints.h>','#elif !defined(_XBOX)\n#include <SDL2/SDL_hints.h>')
        operations={
          'void Gui::ImGuiWMInit()':'    Smash360_ImGuiPlatformInit();',
          'void Gui::ImGuiBackendInit()':'    Shipyard_ImGuiRendererInit();',
          'void Gui::ImGuiWMNewFrame()':'    const auto window = Context::GetInstance()->GetWindow();\n    Smash360_ImGuiPlatformNewFrame(window->GetWidth(), window->GetHeight(), GetMenuOrMenubarVisible());',
          'void Gui::ImGuiRenderDrawData(ImDrawData* data)':'    Shipyard_ImGuiRender(data);',
          'void Gui::HandleWindowEvents(WindowEvent event)':'    // Xbox physical input is polled by the real platform frame and ControlDeck.\n    (void)event;',
          'void Gui::DrawFloatingWindows()':'    // Xbox has one native surface; SupportsViewports() reports false.\n    IM_ASSERT(!(mImGuiIo->ConfigFlags & ImGuiConfigFlags_ViewportsEnable));',
          'void Gui::ShutDownImGui(Ship::Window* window)':'    (void)window;\n    // Native renderer ownership ends in the derived Window destructor.\n    // The base destructor also calls here, including before a failed Init.\n    if (ImGui::GetCurrentContext() == NULL) return;\n    Smash360_ImGuiPlatformShutdown();\n    Shipyard_ImGuiRendererShutdown();\n    ImGui::DestroyContext();',
        }
        for signature,native in operations.items():text=platform_body(text,signature,native)
        text=once(text,'return mGuiTextures.contains(name);','return mGuiTextures.find(name) != mGuiTextures.end();')
        text=once(text,'if (mGuiTextures.contains(name))','if (mGuiTextures.find(name) != mGuiTextures.end())')
        text=once(text,'mGuiWindows.contains(guiWindow->GetName())','mGuiWindows.find(guiWindow->GetName()) != mGuiWindows.end()')
        text=once(text,'mGuiWindows.contains(name)','mGuiWindows.find(name) != mGuiWindows.end()')
        text=text.replace('switch (Context::GetInstance()->GetWindow()->GetWindowBackend())','switch (Context::GetInstance()->GetWindow()->GetWindowBackend().GetValue())')
        text=text.replace('dynamic_pointer_cast<','std::dynamic_pointer_cast<')
        text=text.replace('std::reinterpret_pointer_cast<','Smash360Gui::ReinterpretPointerCast<')
        text='#include "gui/compiler.h"\n'+text
        # Delegating ctor expansion uses the exact primary body and argument.
        first,last=body_span(text,'Gui::Gui(std::vector<std::shared_ptr<GuiWindow>> guiWindows)')
        original=text.encode()[first+1:last-1].decode()
        text=once(text,'Gui::Gui() : Gui(std::vector<std::shared_ptr<GuiWindow>>()) {\n}',
                  'Gui::Gui() : mNeedsConsoleVariableSave(false) {\n    std::vector<std::shared_ptr<GuiWindow>> guiWindows;'+original+'\n}')
    elif relative=='src/fast/Fast3dWindow.cpp':
        text=once(text,'Fast3dWindow::~Fast3dWindow() {','Fast3dWindow::~Fast3dWindow() {\n#ifdef _XBOX\n    GetGui()->ShutDownImGui(this); // Native GUI GPU resources precede native device destruction.\n#endif')
        first=text.index('#include "fast/backends/gfx_sdl.h"')
        last=text.index('#include "fast/backends/gfx_window_manager_api.h"')
        text=text[:first]+'#ifdef _XBOX\n#include "xenos_backend.h"\n#else\n'+text[first:last]+'#endif\n'+text[last:]
        text=once(text,'#ifdef _WIN32\n    AddAvailableWindowBackend', '#ifdef _XBOX\n    AddAvailableWindowBackend(Ship::WindowBackend::FAST3D_XENOS);\n#else\n#ifdef _WIN32\n    AddAvailableWindowBackend')
        text=once(text,'    AddAvailableWindowBackend(Ship::WindowBackend::FAST3D_SDL_OPENGL);','    AddAvailableWindowBackend(Ship::WindowBackend::FAST3D_SDL_OPENGL);\n#endif')
        text=once(text,'    switch (GetWindowBackend()) {','    switch (GetWindowBackend().GetValue()) {\n#ifdef _XBOX\n        case Ship::WindowBackend::FAST3D_XENOS:\n            mWindowManagerApi = new GfxWindowBackendXenos();\n            mRenderingApi = new GfxRenderingAPIXenos();\n            break;\n#endif')
        # The native surface dimensions, not a desktop window preference, govern
        # the initial presentation framebuffer. The real game viewport stays LUS.
        text=once(text,'    mInterpreter->Init(mWindowManagerApi,',
                  '#ifdef _XBOX\n    mWindowManagerApi->GetDimensions(&width, &height, &posX, &posY);\n    isFullscreen = true;\n#endif\n    mInterpreter->Init(mWindowManagerApi,')
        for qualified in ('Ship::Coords','Ship::CoordsF'):
            pattern=r'('+re.escape(qualified)+r' Fast3dWindow::\w+\(\) \{.*?)(    return \{ x, y \};)'
            text=re.sub(pattern,lambda m:m[1]+'    '+qualified+' result = { x, y };\n    return result;',text,flags=re.S)
        start,end=body_span(text,'Fast3dWindow::Fast3dWindow(std::shared_ptr<Ship::Gui> gui,')
        primary=text.encode()[start+1:end-1].decode()
        replacements=[
            ('std::shared_ptr<Ship::Gui> gui','Fast3dWindow(gui, std::make_shared<FastMouseStateManager>())','gui'),
            ('std::vector<std::shared_ptr<Ship::GuiWindow>> guiWindows','Fast3dWindow(std::make_shared<Ship::Gui>(guiWindows))','std::make_shared<Ship::Gui>(guiWindows)'),
            ('','Fast3dWindow(std::vector<std::shared_ptr<Ship::GuiWindow>>())','std::make_shared<Ship::Gui>(std::vector<std::shared_ptr<Ship::GuiWindow>>())')]
        for args,delegation,gui in replacements:
            old='Fast3dWindow::Fast3dWindow('+args+')'+ ('\n    : ' if args else ' : ')+delegation+' {\n}'
            new='Fast3dWindow::Fast3dWindow('+args+') : Ship::Window('+gui+', std::make_shared<FastMouseStateManager>()), mInterpreter(nullptr) {'+primary+'\n}'
            text=once(text,old,new)
        text=once(text,': Ship::Window(gui, mouseStateManager) {',': Ship::Window(gui, mouseStateManager), mInterpreter(nullptr) {')
        text=text.replace('std::span<','Smash360Fast3D::span<')
    elif relative=='include/fast/Fast3dWindow.h':
        text=once(text,'std::shared_ptr<Interpreter> mInterpreter = nullptr;','std::shared_ptr<Interpreter> mInterpreter;')
        text=text.replace('std::span<','Smash360Fast3D::span<')
    elif relative=='include/fast/FastMouseStateManager.h':
        text=once(text,'  public:\n','  public:\n    FastMouseStateManager() : mCursorVisibleSeconds(3) {}\n')
        text=once(text,'uint32_t mCursorVisibleSeconds = 3;','uint32_t mCursorVisibleSeconds;')
    elif relative=='include/ship/window/MouseStateManager.h':
        for a,b in [('bool mAutoCaptureMouse = false;','bool mAutoCaptureMouse;'),('bool mForceCursorVisibility = false;','bool mForceCursorVisibility;'),('uint32_t mCursorVisibleTicks = 180;','uint32_t mCursorVisibleTicks;'),('uint32_t mCursorVisibleTicksCounter = mCursorVisibleTicks;','uint32_t mCursorVisibleTicksCounter;')]:text=once(text,a,b)
    elif relative=='src/ship/window/MouseStateManager.cpp':
        text=once(text,'MouseStateManager::MouseStateManager() {','MouseStateManager::MouseStateManager() : mAutoCaptureMouse(false), mForceCursorVisibility(false), mCursorVisibleTicks(180), mCursorVisibleTicksCounter(mCursorVisibleTicks) {')
        text=once(text,'#include "ship/window/Window.h"','#include "ship/window/Window.h"\n#include "ship/window/gui/Gui.h"')
    elif relative=='src/ship/window/Window.cpp':
        text=CONFIG['transform'](relative,text)
        text=once(text,'#include "ship/controller/controldeck/ControlDeck.h"','#include "ship/config/Config.h"\n#include "ship/window/gui/Gui.h"\n#include "ship/window/MouseStateManager.h"')
        start,end=body_span(text,'Window::Window(std::shared_ptr<Gui> gui,')
        primary=text.encode()[start+1:end-1].decode()
        replacements=[
          ('std::shared_ptr<Gui> gui','Window(gui, std::make_shared<MouseStateManager>())','', 'std::make_shared<MouseStateManager>()'),
          ('std::vector<std::shared_ptr<GuiWindow>> guiWindows','Window(std::make_shared<Gui>(guiWindows))','    std::shared_ptr<Gui> gui = std::make_shared<Gui>(guiWindows);\n','std::make_shared<MouseStateManager>()'),
          ('','Window(std::vector<std::shared_ptr<GuiWindow>>())','    std::shared_ptr<Gui> gui = std::make_shared<Gui>(std::vector<std::shared_ptr<GuiWindow>>());\n','std::make_shared<MouseStateManager>()')]
        for args,delegation,locals,mouse in replacements:
            old='Window::Window('+args+') : '+delegation+' {\n}'
            # All Window members are scalar or default-empty shared_ptrs. Their
            # default construction has no allocation/user code; own a local copy
            # of each delegated argument through the original primary body.
            body=locals+'    std::shared_ptr<MouseStateManager> mouseStateManager = '+mouse+';\n'+primary
            text=once(text,old,'Window::Window('+args+') : mLastScancode(-1) {\n'+body+'\n}')
    text=re.sub(r'\b0b([01]+)\b',lambda m:hex(int(m[1],2)),text)
    text=LOWER['lower_ranges'](text.encode()).decode()
    if relative=='src/ship/window/gui/Gui.cpp':
        text=profile_projections.gui(text)
        text=texture_binding_projection.gui(text)
    return '#include "config/compiler.h"\n'+text


def prepare():
    locks=json.loads((BASE/'source-lock.json').read_text())
    records=[]
    for relative,expected in locks.items():
        source=LUS/relative
        if hashlib.sha256(source.read_bytes()).hexdigest()!=expected:raise ValueError('GUI source drift '+relative)
        text=transform(relative,source.read_text(encoding='utf-8-sig'))
        target=OUT/'overlay/libultraship'/relative
        PRISM['mapped'](source.relative_to(ROOT).as_posix(),text,target)
        records.append({'source':source.relative_to(ROOT).as_posix(),'sha256':expected,'generated_sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
    # Compose common owners physically so sibling quoted includes cannot bypass
    # an adapted header through an unchanged upstream directory.
    common=OUT/'common-overlay'
    headers={}
    for root,prefix in [(ROOT/'scratch/fast3d-xdk/overlay',''),
                        (ROOT/'scratch/graphics-xdk/include','libultraship/include'),
                        (ROOT/'scratch/audio-xdk/generated/include','libultraship/include'),
                        (ROOT/'scratch/binary-reader-xdk/generated/include','libultraship/include'),
                        (ROOT/'scratch/resources-xdk/generated/include','libultraship/include'),
                        (ROOT/'scratch/config-xdk/generated/include','libultraship/include'),
                        (ROOT/'scratch/gui-widgets-xdk/generated/include','libultraship/include'),
                        (ROOT/'scratch/controllers-xdk/generated/include','libultraship/include'),
                        (ROOT/'scratch/input-editor-xdk/overlay','')]:
        for path in root.rglob('*.h'):
            relative=(Path(prefix)/path.relative_to(root)).as_posix()
            if (OUT/'overlay'/relative).is_file():
                stale=common/relative
                if stale.is_file():stale.unlink()
                continue
            headers[relative]=path
    for relative,path in headers.items():
        target=common/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(path.read_bytes())
    tus=['libultraship/'+r for r in locks if r.endswith('.cpp')]
    staged=STAGE(UP,OUT/'compile-tree',tus,[OUT/'overlay',common])
    (OUT/'source-map.json').write_text(json.dumps({'transforms':records,'staged':staged},indent=2)+'\n')


def compile_xdk():
    sdk=Path('C:/Program Files (x86)/Microsoft Xbox 360 SDK');tree=OUT/'compile-tree'
    include=[tree/'libultraship/include',tree/'libultraship/src',tree/'include',
             ROOT/'platform/xbox360/cpp-compat',
             PLATFORM_BASE/'sources/json/include',PLATFORM_BASE/'sources/value_types',
             ROOT/'scratch/thread-pool-xdk',ROOT/'platform/xbox360/cpp-compat/thread-pool',ROOT/'platform/xbox360/cpp-compat/async',PLATFORM_BASE,PLATFORM_BASE/'sources',
             ROOT/'scratch/logging-xdk/core-include',ROOT/'scratch/logging-xdk/include',ROOT/'upstream/dependencies/fmt-xdk',
             ROOT/'scratch/imgui-xdk/source',ROOT/'platform/xbox360/imgui',ROOT/'platform/xbox360/graphics',ROOT/'platform/xbox360/input',ROOT/'upstream/dependencies/stb',sdk/'include/xbox']
    results=[]
    sources=[tree/'libultraship'/r for r in json.loads((BASE/'source-lock.json').read_text()) if r.endswith('.cpp')]
    sources += [ROOT/'platform/xbox360/imgui/gui_startup.cpp',ROOT/'platform/xbox360/graphics/shader_resources.cpp']
    for path in sources:
        relative=path.relative_to(ROOT).as_posix()
        command=[str(sdk/'bin/win32/cl.exe'),'/nologo','/c','/TP','/EHsc','/MT','/W3','/D_XBOX','/DNOMINMAX','/DDISABLE_SCRIPTING','/D_CRT_SECURE_NO_WARNINGS',
                 '/FI'+str(ROOT/'scratch/config-xdk/cvars.h')]+['/I'+str(p) for p in include]+['/Fo'+str(OUT/(path.stem+'.obj')),str(path)]
        run=subprocess.run(command,capture_output=True,text=True,cwd=ROOT)
        log=run.stdout+run.stderr;(OUT/(path.stem+'.log')).write_text(log)
        results.append({'source':relative,'command':command,'exit':run.returncode})
        print(path.name,run.returncode)
        print('\n'.join(l for l in log.splitlines() if 'error ' in l)[:2500])
    (OUT/'compile-report.json').write_text(json.dumps(results,indent=2)+'\n')
    return any(r['exit'] for r in results)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--compile',action='store_true');args=parser.parse_args()
    prepare()
    if args.compile:raise SystemExit(compile_xdk())
