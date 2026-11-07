#pragma once
#include <xtl.h>
#include <stdint.h>
#include <string>
#include <vector>
#include "../environment.h"

// The platform services are link requirements; the graphics compile probe links
// no stand-in for them. The application owns their lifetime.
void Smash360_Log(const char* format, ...);
void Shipyard_Log(const char* format, ...);
__declspec(noreturn) void Shipyard_Fatal(const char* operation, HRESULT result);
inline void Shipyard_Check(HRESULT result,const char* operation){if(FAILED(result))Shipyard_Fatal(operation,result);}
bool Shipyard_WriteFile(const char* relative,const void* data,size_t size);
bool Shipyard_VerifyFast3DReuse();
void Smash360_InitializeGuiForXenos();
__declspec(noreturn) void Smash360_Fatal(const char* operation, HRESULT result);
double Smash360_Time();
bool Smash360_WriteFile(const char* relative, const void* data, size_t size);
bool Smash360_QueueShaderCacheWrite(const std::string& record, bool truncate,
                                  void (*complete)(bool));
inline void Smash360_Check(HRESULT result, const char* operation) {
    if (FAILED(result)) Smash360_Fatal(operation, result);
}

// The app supplies event processing and GUI pointer state. A console without
// a mouse reports that here, not in the renderer glue.
struct Smash360WindowInput {
    int32_t x, y, deltaX, deltaY;
    float wheelX, wheelY;
    uint32_t buttons;
    bool captured, running;
};
void Smash360_PollWindowInput(Smash360WindowInput* state,
                             bool (*keyDown)(int), bool (*keyUp)(int), void (*allKeysUp)(),
                             bool (*mouseDown)(int), bool (*mouseUp)(int));
void Smash360_SetPointerPosition(int32_t x, int32_t y);
void Smash360_SetPointerVisible(bool visible);
void Smash360_SetPointerCaptured(bool captured);
const char* Smash360_KeyName(int scancode);
