#include "runtime.h"
#include "storage/device.h"
#include "../graphics/native_display.h"
#include "async/native.h"

namespace {
Shipyard::Async::mutex storageMutex;
bool mounted;
bool inContainer;
const char* const mountName = "warwingsave";
}

bool Smash360_PrepareAppStorage() {
    Shipyard::Async::lock_guard<Shipyard::Async::mutex> lock(storageMutex);
    if (mounted) return true;
    const Shipyard::Storage::MountPolicy policy = {
        0, 1024 * 1024, mountName, "Warwing", L"Warwing"
    };
    const Shipyard::Storage::StartupDisplay display = {
        Fast::InitializeNativeDisplay, Fast::PresentNativeStartupUI
    };
    const Shipyard::Storage::MountResult result = Shipyard::Storage::SelectAndMount(policy, display);
    inContainer = result.status == ERROR_SUCCESS;
    // Some exploit loaders, BadAvatar among them, refuse the profile container; the game folder stays writable.
    if (!inContainer)
        Smash360_Log("save mount stage=%u error=%lu extended=%08lx device=%lu; saves stay in game:\\",
                     result.stage, result.status, result.extendedStatus, result.deviceId);
    mounted = true;
    return true;
}

std::string Smash360_AppDataPath(const char* name) {
    return std::string(inContainer ? "warwingsave:\\" : "game:\\") + name;
}

void Smash360_CloseAppStorage() {
    Shipyard::Async::lock_guard<Shipyard::Async::mutex> lock(storageMutex);
    if (!mounted) return;
    if (!inContainer) {
        mounted = false;
        return;
    }
    DWORD result = Shipyard::Storage::Flush(mountName);
    if (result != ERROR_SUCCESS) Smash360_Log("final save container flush error=%lu", result);
    result = Shipyard::Storage::Close(mountName);
    if (result != ERROR_SUCCESS) Smash360_Log("save container close error=%lu", result);
    else mounted = false;
}
