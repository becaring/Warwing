#pragma once

struct XboxTrianglePipelineTraits {
    template<class Owner> static bool ShaderPresent(const Owner& owner) {
        return !owner.mShaderStack.empty();
    }
    template<class Owner> static int64_t ShaderIdentity(const Owner& owner) {
        return owner.mShaderStack.empty() ? 0 : owner.mShaderStack.top();
    }
    template<class Owner> static bool Redirect(const Owner& owner) {
        return owner.RdpColorImageIsZBuffer();
    }
    template<class Owner> static GfxClipParameters Clip(const Owner& owner) {
        return owner.mXboxClipParameters;
    }
    template<class Owner> static unsigned EffectiveTile(const Owner& owner, unsigned slot) {
        const unsigned first = owner.mRdp->first_tile_index;
        return slot == 1 && first >= 2 ? first : first + slot;
    }
};
