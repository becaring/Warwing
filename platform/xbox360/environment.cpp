// Xbox has no process environment. The caller owns the launch path and the
// decision to accept an absent optional file.
#include "environment.h"
#include "environment/launch_environment.h"

namespace {
Shipyard::Environment::Store values;
}

extern "C" int XboxEnv_LoadFromFile(const char* path) {
    using namespace Shipyard::Environment;
    if (values.Initialized()) return XBOX_ENV_ALREADY_INITIALIZED;
    if (!path || !*path) return XBOX_ENV_INVALID;
    std::string text;
    switch (ReadBoundedFile(path, text)) {
    case FileAbsent:
        values.PublishAbsent();
        return XBOX_ENV_ABSENT;
    case FileIoError: return XBOX_ENV_IO_ERROR;
    case FileInvalid: return XBOX_ENV_INVALID;
    case FileLoaded: break;
    }
    switch (values.PublishText(text)) {
    case PublishLoaded: return XBOX_ENV_LOADED;
    case PublishInvalid: return XBOX_ENV_INVALID;
    case PublishIoError: return XBOX_ENV_IO_ERROR;
    case PublishAlreadyInitialized: return XBOX_ENV_ALREADY_INITIALIZED;
    case PublishAbsentResult: break;
    }
    return XBOX_ENV_IO_ERROR;
}

extern "C" char* XboxEnv_Get(const char* name) {
    return const_cast<char*>(values.Get(name));
}
