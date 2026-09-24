#pragma once
#include "vertex_lighting.h"
#include "fast3d/light_color_cache.h"
#include "fast3d/vertex_transform.h"
#include <float.h>
#include <stdint.h>

namespace Smash360Fast {
// Current SoH gfx_pc.cpp caches exact RGB floats at light writes. BattleShip's
// RSP is externally visible, so validate all current value-owned RGB keys at
// the command boundary as well. Zero-initialization correctly represents black.
struct LightColorFloats {
    Shipyard::Fast3D::LightColorValueCache<33> cache;
    template<class Light> const float (*Prepare(const Light* lights,unsigned count))[3] {
        for(unsigned i=0;i<count;++i) {
            const uint8_t* color=lights[i].l.col;
            cache.Refresh(i,color,Shipyard::Fast3D::LightByteFloat);
        }
        return cache.Values();
    }
};

// Numeric division is owned by Shipyard; cache layout and refresh remain local.
using Shipyard::Fast3D::DivideNormal127;
using Shipyard::Fast3D::DivideNormalByte127;
}
