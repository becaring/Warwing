#ifndef SMASH360_STARTUP_RUNTIME_H
#define SMASH360_STARTUP_RUNTIME_H
#include <string>
namespace Smash360Startup {
// Called on the application thread before LUS starts any workers.
bool Initialize();
// Called after game and Context teardown, while diagnostics still exist.
void Shutdown();
bool RequireArchive(const std::string& path);
}
#endif
