"""Reuse pure material values using SoH360's Xbox cache pattern.

Donor: platform/xbox360/fast3d_texture_math.h (SoHTextureGeometry) and
gfx_pc.cpp (SoHDrawOptionsCache). BattleShip's arithmetic is extracted verbatim
into cold rebuilds, with identifiers mapped explicitly below. No texture
import, binding, flush, shader lifetime or framebuffer operation is skipped.
"""
import hashlib
from profile_projections import once


def transform(text):
    tri = text.split('void Interpreter::GfxSpTri1(', 1)[1]
    options = tri[tri.index('    uint64_t cc_options ='):tri.index('    if (!mShaderStack.empty())')]
    geometry = tri[tri.index('            uint8_t cms ='):tri.index('            if (mRenderingState.mTextures[i] == nullptr)')]
    # A change to the arithmetic needs a review of its dependencies and keys.
    for block, expected in [(options, '6a8fb6f826598cc00d36fac574d25d8bd53d81cb2729cc14745fdfdac98e7390'),
                            (geometry, '8adb2085235d034dfc11a8a04c33aa34fb671c79f386871829f658b9265e8f21')]:
        if hashlib.sha256(block.encode()).hexdigest() != expected:
            raise ValueError('Re-audit BattleShip material arithmetic and complete cache dependencies')
    option_body = options.replace('mRdp->', 'rdp->')
    geometry_body = geometry.replace('mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index]', 'loaded')
    geometry_body = geometry_body.replace('mRdp->texture_tile[tile]', 'tile')
    for old, new in [('tex_width2[i]', 'boundWidth'), ('tex_height2[i]', 'boundHeight'),
                     ('tex_width[i]', 'width'), ('tex_height[i]', 'height'),
                     ('tm |= 1 << 2 * i + 1', 'clampMask |= 2'), ('tm |= 1 << 2 * i', 'clampMask |= 1')]:
        geometry_body = geometry_body.replace(old, new)
    if 'mRdp' in geometry_body or '[i]' in geometry_body:
        raise ValueError('Unmapped texture geometry dependency')
    helpers = '''// XBOX MATERIAL MATH BEGIN
// BattleShip owns these complete keys and exact formula bodies. Shipyard owns
// the value cache's comparison, storage, cold rebuild, and publication.
struct XboxDrawOptionsKey {
    uint32_t modeL,modeH;
    bool grayscale;
    bool operator==(const XboxDrawOptionsKey& rhs) const {
        return modeL==rhs.modeL && modeH==rhs.modeH && grayscale==rhs.grayscale;
    }
};
struct XboxDrawOptionsValue { uint64_t options; bool alpha,fog,blend,grayscale; };
struct XboxDrawOptionsBuilder {
    const RDP* rdp;
    __declspec(noinline) void Rebuild(XboxDrawOptionsValue& result) {
        // TEST REBUILD OPTIONS
OPTION_BODY
        result.options=cc_options;result.alpha=use_alpha;result.fog=use_fog;
        result.blend=use_blend_color;result.grayscale=use_grayscale;
    }
};
struct XboxTextureGeometryKey {
    uint32_t tileLine,loadedLine,loadedSize,loadedFullLine,loadedOriginalSize;
    unsigned rounding;
    float uls,ult,lrs,lrt;
    uint8_t fmt,siz,cms,cmt,masks,maskt;
    bool operator==(const XboxTextureGeometryKey& rhs) const {
        return tileLine==rhs.tileLine && loadedLine==rhs.loadedLine &&
            loadedSize==rhs.loadedSize && loadedFullLine==rhs.loadedFullLine &&
            loadedOriginalSize==rhs.loadedOriginalSize && rounding==rhs.rounding &&
            fmt==rhs.fmt && siz==rhs.siz &&
            cms==rhs.cms && cmt==rhs.cmt && masks==rhs.masks && maskt==rhs.maskt &&
            uls==rhs.uls && ult==rhs.ult && lrs==rhs.lrs && lrt==rhs.lrt;
    }
};
struct XboxTextureGeometryValue {
    uint32_t width,height,boundWidth,boundHeight,clampMask;
    float widthFloat,heightFloat,boundWidthFloat,boundHeightFloat;
    uint8_t cms,cmt;
};
template<class Tile,class Loaded> struct XboxTextureGeometryBuilder {
    const Tile& tile;
    const Loaded& loaded;
    __declspec(noinline) void Rebuild(XboxTextureGeometryValue& result) {
        // TEST REBUILD GEOMETRY
        uint32_t width,height,boundWidth,boundHeight,clampMask=0;
GEOMETRY_BODY
        result.width=width;result.height=height;
        result.boundWidth=boundWidth;result.boundHeight=boundHeight;
        // Keep the original conversion before the UV divisions.
        result.widthFloat=(float)width;result.heightFloat=(float)height;
        result.boundWidthFloat=(float)boundWidth;result.boundHeightFloat=(float)boundHeight;
        result.cms=cms;result.cmt=cmt;result.clampMask=clampMask;
    }
};
template<class Tile,class Loaded>
const XboxTextureGeometryValue& XboxGeometry(
    Shipyard::Fast3D::MaterialMemo<XboxTextureGeometryKey,XboxTextureGeometryValue,256>& cache,
    const Tile& tile,const Loaded& loaded) {
    XboxTextureGeometryKey key={tile.line_size_bytes,loaded.line_size_bytes,
        loaded.size_bytes,loaded.full_image_line_size_bytes,loaded.orig_size_bytes,
        Shipyard::Fast3D::ProjectionRoundingMode(),
        tile.uls,tile.ult,tile.lrs,tile.lrt,tile.fmt,tile.siz,tile.cms,tile.cmt,tile.masks,tile.maskt};
    XboxTextureGeometryBuilder<Tile,Loaded> builder={tile,loaded};
    unsigned bounds[4];
    memcpy(bounds,&key.uls,sizeof(bounds));
    const unsigned hash=Shipyard::Fast3D::HashMaterialKey(key.tileLine^(key.loadedSize*33U)^bounds[0]^
        (bounds[1]*17U)^(bounds[2]*31U)^(bounds[3]*47U)^(unsigned(key.siz)<<12)^(unsigned(key.cms)<<16)^
        (unsigned(key.cmt)<<20)^(unsigned(key.masks)<<24)^(unsigned(key.maskt)<<28)^key.rounding);
    return cache.Load(key,hash,builder);
}
static __declspec(thread) Shipyard::Fast3D::MaterialValueCache<XboxDrawOptionsKey,XboxDrawOptionsValue> sXboxDrawOptions;
// Alternating materials keep their geometry; storage is outside Xenon's TLS section.
static __declspec(thread) Shipyard::Fast3D::MaterialMemo<XboxTextureGeometryKey,XboxTextureGeometryValue,256> sXboxTextureGeometry0;
static __declspec(thread) Shipyard::Fast3D::MaterialMemo<XboxTextureGeometryKey,XboxTextureGeometryValue,256> sXboxTextureGeometry1;
static void XboxReleaseTextureGeometry() {
    sXboxTextureGeometry0.Release();
    sXboxTextureGeometry1.Release();
}
// XBOX MATERIAL MATH END

'''.replace('OPTION_BODY', option_body).replace('GEOMETRY_BODY', geometry_body)
    text = once(text, options, '''    XboxDrawOptionsKey drawKey={mRdp->other_mode_l,mRdp->other_mode_h,mRdp->grayscale};
    XboxDrawOptionsBuilder drawBuilder={mRdp};
    const XboxDrawOptionsValue& drawOptions=sXboxDrawOptions.Load(drawKey,drawBuilder);
    uint64_t cc_options = drawOptions.options;
    bool use_alpha = drawOptions.alpha;
    bool use_fog = drawOptions.fog;
    bool use_blend_color = drawOptions.blend;
    bool use_grayscale = drawOptions.grayscale;

''')
    text = once(text, geometry, '''            uint8_t cms = 0, cmt = 0;
            const XboxTextureGeometryValue& geometry = XboxGeometry(
                i ? sXboxTextureGeometry1 : sXboxTextureGeometry0,mRdp->texture_tile[tile],
                mRdp->loaded_texture[mRdp->texture_tile[tile].tmem_index]);
            cms = geometry.cms; cmt = geometry.cmt;
            tex_width[i] = geometry.width; tex_height[i] = geometry.height;
            tex_width2[i] = geometry.boundWidth; tex_height2[i] = geometry.boundHeight;
            xboxTextureWidth[i] = geometry.widthFloat; xboxTextureHeight[i] = geometry.heightFloat;
            xboxTextureBoundWidth[i] = geometry.boundWidthFloat; xboxTextureBoundHeight[i] = geometry.boundHeightFloat;
            tm |= geometry.clampMask << (2 * i);

''')
    text = once(text, '    uint32_t tm = 0;', '''    uint32_t tm = 0;
    float xboxTextureWidth[2], xboxTextureHeight[2], xboxTextureBoundWidth[2], xboxTextureBoundHeight[2];''')
    # Same implicit uint32 -> float conversion, once per material rebuild.
    # Do not use reciprocal approximations, reorder operations, or change the
    # framebuffer sub-rectangle transform in the packing loop.
    for old,new,count in [('u / tex_width[t]', 'u / xboxTextureWidth[t]', 2),
                          ('v / tex_height[t]', 'v / xboxTextureHeight[t]', 2),
                          ('(tex_width2[t] - 0.5f) / tex_width[t]', '(xboxTextureBoundWidth[t] - 0.5f) / xboxTextureWidth[t]', 1),
                          ('(tex_height2[t] - 0.5f) / tex_height[t]', '(xboxTextureBoundHeight[t] - 0.5f) / xboxTextureHeight[t]', 1)]:
        if text.count(old)!=count:raise ValueError('Re-audit texture float operand '+old)
        text=text.replace(old,new)
    text = once(text, 'void Interpreter::GfxSpTri1(', helpers+'void Interpreter::GfxSpTri1(')
    text = once(text, 'Interpreter::~Interpreter() {',
                'static void XboxReleaseTextureGeometry();\nInterpreter::~Interpreter() {\n    XboxReleaseTextureGeometry();')
    return ('#include <float.h>\n#include "fast3d/material_value_cache.h"\n#include "fast3d/material_memo.h"\n'
            '#include "fast3d/projection_cache.h"\n' + text)
