#include "startup/runtime.h"
#include "runtime/runtime.h"
#include "environment.h"
#include "filesystem/filesystem.h"
#include "graphics/native_display.h"
#include <exception>

namespace Smash360Startup {
bool Initialize() {
    // Match SoH360 main.cpp: the title/render thread owns hardware thread 0.
    if (XSetThreadProcessor(GetCurrentThread(), 0) == (DWORD)-1) {
        Smash360_Log("application processor setup failed code=%lu", GetLastError());
        return false;
    }
    Smash360_Log("THREAD application hardware=%lu", GetCurrentProcessorNumber());
    // The donor QPC frequency cache must initialize before worker creation.
    (void)Smash360_Time();
    const int status = XboxEnv_LoadFromFile("game:\\smash360.env");
    if (status != XBOX_ENV_LOADED && status != XBOX_ENV_ABSENT) {
        Smash360_Log("startup environment failed status=%d", status);
        return false;
    }
    std::error_code error;
    if (!xbox_compat::filesystem::InitWorkingDirectory("game:\\", error)) {
        Smash360_Log("startup working directory failed code=%d: %s", error.value(), error.message().c_str());
        return false;
    }
    Smash360_Log("BattleShip Xbox startup environment=%s cwd=game:\\", status == XBOX_ENV_LOADED ? "loaded" : "absent");
    if (!Smash360_PrepareAppStorage()) return false;
    Smash360_Log("BattleShip writable app data mounted at smashsave:\\");
    return true;
}
bool RequireArchive(const std::string& path) {
    std::error_code error;
    if (xbox_compat::filesystem::is_regular_file(path, error)) return true;
    Smash360_Log("required archive unavailable: %s (error=%d %s); prepare assets on PC and copy beside the XEX",
                 path.c_str(), error.value(), error.message().c_str());
    return false;
}
void Shutdown() {
    Smash360_ShutdownShaderWrites();
    Smash360_CloseAppStorage();
    // Handles cancellation before Context exists; normal renderer teardown has
    // already released this same device, so the second call is harmless.
    Fast::ShutdownNativeDisplay();
    Smash360_FlushLogs();
    Smash360_ShutdownDiagnostics();
}
}
