#include "audio/services.h"
#include "runtime/runtime.h"
#include <cstdarg>
#include <cstdio>

void ShipyardAudioLog(const char* format, ...) {
    char buffer[1024];
    va_list args;
    va_start(args, format);
    _vsnprintf_s(buffer, sizeof(buffer), _TRUNCATE, format, args);
    va_end(args);
    Smash360_Log("%s", buffer);
}

__declspec(noreturn) void ShipyardAudioFatal(const char* operation, HRESULT result) {
    Smash360_Fatal(operation, result);
}
