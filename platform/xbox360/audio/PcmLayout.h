#ifndef SMASH360_PCM_LAYOUT_H
#define SMASH360_PCM_LAYOUT_H

#include "sources/audio/PcmLayout.h"

namespace Smash360 {
using ShipyardAudio::PcmLayout;
using ShipyardAudio::PcmBufferPool;
inline bool ComputePcmLayout(int32_t rate, int32_t channels, AudioChannelsSetting setting,
                             int32_t sampleLength, int32_t desired, PcmLayout& out) {
    return ShipyardAudio::ComputePcmLayout(rate, channels, setting, sampleLength, desired, out, false);
}
}

#endif
