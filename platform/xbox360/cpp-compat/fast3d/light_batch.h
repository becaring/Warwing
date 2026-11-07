#pragma once
#include "vertex_lighting.h"
#include "fast3d/light_color_cache.h"
#include "fast3d/vertex_transform.h"
#include <float.h>
#include <stdint.h>

namespace Smash360Fast {
// SoH's gfx_pc.cpp caches RGB floats when a light is written. BattleShip's RSP
// state can be read from outside, so also check every RGB key against its value
// at the command boundary. Zero-initialization represents black.
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
