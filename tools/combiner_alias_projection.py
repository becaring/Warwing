"""Let SSB64's SHADE-only fighter parts share the PRIM*SHADE parts' program.

Fighters alternate (PRIM-0)*SHADE+0 and SHADE-only parts with otherwise equal
combiners, so every joint changed program and flushed its batch. A SHADE-only
first cycle that reads PRIM nowhere is written as PRIM*SHADE with PRIM pinned
to white (bit 63, which GenerateCC never reads): x*1.0f == x, the program
and row layout are the same, and the triangles stay in one batch.
"""
from profile_projections import once

PIN = '''// Bit 63 of combine_mode is unused by every combiner field (cycle 2 ends at bit 55).
static const uint64_t XBOX_PRIM_WHITE = 1ull << 63;
static __forceinline bool XboxReadsPrim(uint64_t mode) {
    for (unsigned i = 0; i < 2; ++i) {
        const uint32_t rgb = (uint32_t)(mode >> (i * 28)) & 0xffff, alpha = (uint32_t)(mode >> (i * 28 + 16)) & 0xfff;
        const uint32_t c = (rgb >> 8) & 0x1f;
        if ((rgb & 0xf) == G_CCMUX_PRIMITIVE || ((rgb >> 4) & 0xf) == G_CCMUX_PRIMITIVE ||
            c == G_CCMUX_PRIMITIVE || c == G_CCMUX_PRIMITIVE_ALPHA || ((rgb >> 13) & 7) == G_CCMUX_PRIMITIVE)
            return true;
        for (unsigned f = 0; f < 4; ++f)
            if (((alpha >> (3 * f)) & 7) == G_ACMUX_PRIMITIVE) return true;
    }
    return false;
}
static __forceinline uint64_t XboxPinShadePrim(uint64_t mode) {
    const uint32_t rgb = (uint32_t)mode & 0xffff;
    uint32_t a = rgb & 0xf, b = (rgb >> 4) & 0xf;
    if (a >= 8) a = G_CCMUX_0;
    if (b >= 8) b = G_CCMUX_0;
    // GenerateCC reduces a zero product to D alone.
    const bool shadeOnly = (a == b || ((rgb >> 8) & 0x1f) >= 16) && ((rgb >> 13) & 7) == G_CCMUX_SHADE;
    if (!shadeOnly || XboxReadsPrim(mode)) return mode;
    const uint64_t primShade = G_CCMUX_PRIMITIVE | (15u << 4) | (G_CCMUX_SHADE << 8) | (7u << 13);
    return (mode & ~(uint64_t)0xffff) | primShade | XBOX_PRIM_WHITE;
}
'''

SET = '    mRdp->combine_mode = rgb | (alpha << 16) | ((uint64_t)rgb_cyc2 << 28) | ((uint64_t)alpha_cyc2 << 44);'


def transform(text):
    """Apply after triangle_constants_projection, which emits the constant helpers."""
    text = once(text, 'void Interpreter::GfxDpSetCombineMode(uint32_t rgb, uint32_t alpha, uint32_t rgb_cyc2, uint32_t alpha_cyc2) {',
                PIN + 'void Interpreter::GfxDpSetCombineMode(uint32_t rgb, uint32_t alpha, uint32_t rgb_cyc2, uint32_t alpha_cyc2) {')
    text = once(text, SET, SET.replace('mRdp->combine_mode = rgb', 'mRdp->combine_mode = XboxPinShadePrim(rgb').replace(';', ');'))
    text = once(text, '// XBOX TRIANGLE CONSTANT HELPERS BEGIN',
                '// XBOX TRIANGLE CONSTANT HELPERS BEGIN\nstatic const RGBA kXboxPrimWhite = { 255, 255, 255, 255 };')
    text = once(text, '                        color = &mRdp->prim_color;',
                '                        color = (mRdp->combine_mode >> 63) ? &kXboxPrimWhite : &mRdp->prim_color;')
    return once(text, '    memcpy(&key.prim,&mRdp->prim_color,4);',
                '    memcpy(&key.prim,(mRdp->combine_mode >> 63) ? &kXboxPrimWhite : &mRdp->prim_color,4);')
