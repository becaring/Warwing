#pragma once
#include <stdint.h>
// The linker must not select this fallback archive member: BattleShip owns
// VI scheduling. It is left undefined so an accidental selection fails at link.
extern "C" void Smash360_UnavailableLusFallbackViTimer(uint32_t interval,
    uint32_t (*callback)(uint32_t, void*), void* context);
