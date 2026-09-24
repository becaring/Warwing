#pragma once
#include <stdint.h>
// This fallback archive member must remain unselected: actual BattleShip owns
// VI scheduling. Deliberately undefined: accidental selection fails at link.
extern "C" void Smash360_UnavailableLusFallbackViTimer(uint32_t interval,
    uint32_t (*callback)(uint32_t, void*), void* context);
