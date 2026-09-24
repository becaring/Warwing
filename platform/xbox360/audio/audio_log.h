#ifndef SMASH360_AUDIO_LOG_H
#define SMASH360_AUDIO_LOG_H
#ifdef _XBOX
#include "../runtime/runtime.h"
#else
// Host decoder/ownership contract tests provide this diagnostic sink only.
void Smash360_Log(const char* format, ...);
#endif
#endif
