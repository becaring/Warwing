"""Stage the real BattleShip startup and explicit Xbox capability branches.

This is a platform integration overlay, not a claim that its complete header
graph compiles yet. All game and LUS lifecycle functions remain authoritative.
"""
from pathlib import Path
import hashlib, json, runpy
ROOT=Path(__file__).resolve().parents[1]
UP=ROOT/'upstream/BattleShip'
OUT=ROOT/'scratch/startup-xdk'
BASE=ROOT/'platform/xbox360/cpp-compat/startup'
MAP=runpy.run_path(str(ROOT/'tools/prepare_prism_xdk.py'))['mapped']
LOCKS={'port/port.cpp': '1ec711478ca6308aaed1d58ae04aadb3579f6685588e0dc2780b173a2f6d8451', 'port/app_paths.cpp': 'f979b9f336d69c46d78c04185ce6e11bf78b530b2fce43899c5b7588f003a025', 'port/app_paths.h': '6e98e3aa2377fb5027e3172685072916027a05b7d0ae6c8845dce1f8543ad77b', 'libultraship/src/ship/Context.cpp': 'd4634c8cb547741b72cebd50a95128f0eb444120a0b8f564c2264efa5df09524', 'port/gameloop.cpp': '8d8e84cb0a6f57d37da8a1c515790f1469033caf5ceff5b5c21d58bd40810a67', 'port/gui/PortMenu.cpp': '934a4ee9728816870f8c5400490b554ca180ff5a23bbb7c9b65c1bfcd5e7691a', 'port/enhancements/enhancements.h': '7110bca49cbc4ae1ff264e6fc1eeed2f35bbc13571924823be5a0d7d02062ea3'}

def once(text, before, after, count=1):
    if text.count(before)!=count:
        raise ValueError('Startup source anchor drift: '+before[:110])
    return text.replace(before,after)

def guard(text, body):
    return once(text,body,'#if !defined(_XBOX)\n'+body+'\n#endif')

def transform(relative,text):
    if relative=='port/port.cpp':
        text=once(text,'#include "first_run.h"','#if !defined(_XBOX)\n#include "first_run.h"\n#endif')
        text=once(text,'#if !defined(__ANDROID__)\n#include "port_window_icon.h"','#if !defined(__ANDROID__) && !defined(_XBOX)\n#include "port_window_icon.h"')
        text=guard(text,'#include "renderdoc_trigger.h"')
        text=once(text,'#include "app_paths.h"','#include "app_paths.h"\n#ifdef _XBOX\n#include "startup/runtime.h"\n#include "runtime/runtime.h"\n#include "environment.h"\n#endif')
        text=once(text,'#if defined(_WIN32) && !defined(BATTLESHIP_UWP)','#if defined(_WIN32) && !defined(BATTLESHIP_UWP) && !defined(_XBOX)',2)
        text=once(text,'#if !defined(__ANDROID__) && !defined(BATTLESHIP_UWP)','#if !defined(__ANDROID__) && !defined(BATTLESHIP_UWP) && !defined(_XBOX)',2)
        text=once(text,'\t\tstd::string logPath;','\t\tstd::string logPath;\n#ifdef _XBOX\n        logPath = "smashsave:\\\\ssb64.log";\n#else')
        text=once(text,'\t\tport_log_init(logPath.c_str());','#endif\n\t\tport_log_init(logPath.c_str());')
        text=once(text,'int main(int argc, char* argv[]) {','int main(int argc, char* argv[]) {\n#ifdef _XBOX\n    if (!Smash360Startup::Initialize()) { Smash360Startup::Shutdown(); return 1; }\n    bool xboxGameStarted = false;\n#endif')
        text=guard(text,'\tportRenderDocInit();\n\tport_log("SSB64: RenderDoc hook initialized\\n");')
        text=guard(text,'\tportRenderDocShutdown();')
        text=guard(text,'\t\t\tcd->ShutdownRaphnet();')
        text=once(text,'\tif (PortInit(argc, argv) != 0) {\n\t\treturn 1;','\tif (PortInit(argc, argv) != 0) {\n#ifdef _XBOX\n        PortShutdown();\n        Smash360Startup::Shutdown();\n#endif\n\t\treturn 1;')
        text=once(text,'\tPortGameInit();','#ifdef _XBOX\n    xboxGameStarted = true;\n#endif\n\tPortGameInit();')
        text=once(text,'\tPortGameShutdown();','\tPortGameShutdown();\n#ifdef _XBOX\n    xboxGameStarted = false;\n#endif')
        text=once(text,'\t\tPortPushFrame();','\t\tPortPushFrame();\n#ifdef _XBOX\n        Smash360_PollShaderWrites();\n#endif')
        text=once(text,'\tPortShutdown();\n#if !defined(_XBOX)','\tPortShutdown();\n#ifdef _XBOX\n    Smash360Startup::Shutdown();\n#endif\n#if !defined(_XBOX)')
        # Only main catches get game/context cleanup. PortInit catches return to main.
        pos=text.index('int main(int argc, char* argv[])')
        prefix,main=text[:pos],text[pos:]
        main=once(main,'\t\tport_log_close();\n\t\treturn 1;', '#ifdef _XBOX\n        if (xboxGameStarted) PortGameShutdown();\n        PortShutdown();\n        Smash360Startup::Shutdown();\n#endif\n\t\tport_log_close();\n\t\treturn 1;',2)
        text=prefix+main
        text=once(text,'\t\tstd::vector<std::string> bootstrapPaths = {f3d};', '#ifdef _XBOX\n        if (!Smash360Startup::RequireArchive(f3d)) return 1;\n#endif\n        std::vector<std::string> bootstrapPaths(1, f3d);')
        text=once(text,'\t\tif (!sContext->InitResourceManager(bootstrapPaths, {}, 0,\n\t\t                                   /*allowEmptyPaths=*/true)) {', '\t\tif (!sContext->InitResourceManager(bootstrapPaths, std::unordered_set<uint32_t>(), 0,\n#ifdef _XBOX\n                                            false\n#else\n                                            true\n#endif\n                                            )) {')
        anchor='\t{\n#ifdef BATTLESHIP_UWP\n\t\t// A UWP app cannot launch'
        text=once(text,anchor,'\t{\n#ifdef _XBOX\n        if (!Smash360Startup::RequireArchive(PortLocateFile(SSB64_O2R_NAME))) return 1;\n#elif defined(BATTLESHIP_UWP)\n\t\t// A UWP app cannot launch')
        text=once(text,'\tport_log("SSB64: Config + CVars OK\\n");','\tport_log("SSB64: Config + CVars OK\\n");\n#ifdef _XBOX\n    sContext->GetConsoleVariables()->SetInteger("gControlNav", 1);\n    sContext->GetConfig()->SetWindowBackend(Ship::WindowBackend::FAST3D_XENOS);\n#endif')
        text=once(text,'\tsContext->GetConsole()->AddCommand("reset", { ResetCommandHandler, "Resets the game to the opening scene" });','    Ship::CommandEntry resetEntry;\n    resetEntry.Handler = ResetCommandHandler;\n    resetEntry.Description = "Resets the game to the opening scene";\n    sContext->GetConsole()->AddCommand("reset", resetEntry);')
        text=once(text,'if (const char *fromsource = std::getenv("SSB64_RELOC_FROMSOURCE");\n\t\t\tfromsource && fromsource[0] == \'1\') {','const char *fromsource = std::getenv("SSB64_RELOC_FROMSOURCE");\n        if (fromsource && fromsource[0] == \'1\') {')
        text=once(text,'\t\t\tconst auto start = std::chrono::steady_clock::now();','#ifdef _XBOX\n            const double start = Smash360_Time();\n#else\n\t\t\tconst auto start = std::chrono::steady_clock::now();\n#endif')
        text=once(text,'\t\t\tconst double elapsedMs = std::chrono::duration<double, std::milli>(\n\t\t\t\tstd::chrono::steady_clock::now() - start).count();','#ifdef _XBOX\n            const double elapsedMs = (Smash360_Time() - start) * 1000.0;\n#else\n\t\t\tconst double elapsedMs = std::chrono::duration<double, std::milli>(\n\t\t\t\tstd::chrono::steady_clock::now() - start).count();\n#endif')
        text=guard(text,'#include <chrono>')
        # Target-only overlay has immutable native env, not CRT process env.
        text=text.replace('std::getenv(', 'XboxEnv_Get(')
    elif relative=='port/app_paths.cpp':
        text=once(text,'#include <libultraship/libultraship.h>','#include "ship/Context.h"')
        text=once(text,'#if defined(_WIN32)','#if defined(_WIN32) && !defined(_XBOX)')
        text=once(text,'    std::filesystem::path root("E:/BattleShip");','#ifdef _XBOX\n    std::filesystem::path root("game:\\\\");\n#else\n    std::filesystem::path root("E:/BattleShip");\n#endif')
        text=once(text,'#if defined(__linux__)','#if defined(_XBOX)\n    return "game:\\\\";\n#elif defined(__linux__)')
    elif relative=='port/app_paths.h':
        text=once(text,'// Xbox removable-storage convention. Returns E:/BattleShip/<rel_path>;','// Xbox 360 uses game:\\<rel_path>; UWP uses E:/BattleShip/<rel_path>;')
    elif relative=='libultraship/src/ship/Context.cpp':
        text=guard(text,'#include "ship/install_config.h"')
        text=once(text,'#ifdef _WIN32','#if defined(_WIN32) && !defined(_XBOX)',2)
        text=once(text,'#if (!defined(_WIN32)) || defined(_DEBUG)','#if !defined(_XBOX) && ((!defined(_WIN32)) || defined(_DEBUG))')
        text=guard(text,'#include <spdlog/sinks/stdout_color_sinks.h>')
        text=once(text,'    GetWindow()->SaveWindowToConfig();','    if (GetWindow()) GetWindow()->SaveWindowToConfig();')
        text=once(text,'    GetConfig()->Save();','    if (GetConfig()) GetConfig()->Save();')
        text=once(text,'std::string Context::GetAppBundlePath() {','std::string Context::GetAppBundlePath() {\n#ifdef _XBOX\n    return "game:\\\\";\n#else')
        text=once(text,'std::string Context::GetAppDirectoryPath(std::string appName) {','#endif\nstd::string Context::GetAppDirectoryPath(std::string appName) {\n#ifdef _XBOX\n    return "smashsave:\\\\";\n#else')
        # Close each conditional within its function, never outside its brace.
        text=once(text,'    return ".";\n#endif\n}\n\n#endif','    return ".";\n#endif\n#endif\n}\n')
        text=once(text,'    return ".";\n}\n\nstd::string Context::GetPathRelativeToAppBundle','    return ".";\n#endif\n}\n\nstd::string Context::GetPathRelativeToAppBundle')
        text=once(text,'    return GetAppBundlePath() + "/" + path;', '    return (xbox_compat::filesystem::path(GetAppBundlePath()) / path).make_preferred().string();')
        text=once(text,'    return GetAppDirectoryPath(appName) + "/" + path;', '    return (xbox_compat::filesystem::path(GetAppDirectoryPath(appName)) / path).make_preferred().string();')
        text=once(text,'    return "./" + std::string(path);','    return xbox_compat::filesystem::absolute(path).string();')
        text=guard(text,'        SDL_ShowSimpleMessageBox(SDL_MESSAGEBOX_ERROR, "OTR file not found",\n                                 "Main OTR file not found. Please generate one", nullptr);')
    elif relative=='port/gameloop.cpp':
        text=guard(text,'#include "renderdoc_trigger.h"')
        text=guard(text,'\tssb64::enhancements::TickDiscordPresence(); // DRP')
        text=guard(text,'\tportRenderDocOnFrame(static_cast<unsigned int>(sFrameCount));')
    elif relative=='port/gui/PortMenu.cpp':
        # Existing guards own entire desktop widgets; retain their boundaries.
        for comment in ('    // DRP', '    // BUILT-IN UPDATER'):
            text=once(text,'#if !defined(__ANDROID__) && !defined(BATTLESHIP_UWP)\n'+comment, '#if !defined(__ANDROID__) && !defined(BATTLESHIP_UWP) && !defined(_XBOX)\n'+comment)
        start=text.index('    AddWidget(path, "Open App Files Folder"')
        end=text.index('\n\n    path.sidebarName = "Graphics";',start)
        text=guard(text,text[start:end])
    elif relative=='port/enhancements/enhancements.h':
        start=text.index('// Discord Rich Presence')
        end=text.index('// Libretro shader pack downloader.',start)
        text=guard(text,text[start:end])
    # Capability-only overlays are composed by their owning source generators.
    if relative in ('port/port.cpp','port/app_paths.cpp','libultraship/src/ship/Context.cpp'):
        text=text.replace('#include <filesystem>','#include "filesystem/filesystem.h"')
        text=text.replace('std::filesystem::','xbox_compat::filesystem::')
        text=text.replace('namespace fs = std::filesystem;', 'namespace fs = xbox_compat::filesystem;')
    return text

def prepare():
    changed={}
    for relative,expected in LOCKS.items():
        raw=(UP/relative).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=expected:
            raise ValueError('Startup pinned source drift: '+relative)
        changed[relative]=transform(relative,raw.decode('utf-8-sig').replace('\r\n','\n'))
    outputs={}
    for relative,text in changed.items():
        destination=OUT/'generated'/relative
        MAP('upstream/BattleShip/'+relative,text,destination)
        outputs[relative]=hashlib.sha256(destination.read_bytes()).hexdigest()
    (OUT/'manifest.json').write_text(json.dumps({'inputs':LOCKS,'outputs':outputs,'complete_application_compile':False,'capability_only':['port/gameloop.cpp','port/gui/PortMenu.cpp','port/enhancements/enhancements.h'],'backend_ids':{'FAST3D_XENOS':3,'XAUDIO2':4}},indent=2)+'\n')
    return outputs

if __name__=='__main__':
    prepare()
    print('Real startup platform overlay staged; complete dependency graph compilation remains separate.')
