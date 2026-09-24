"""SoH combiner constant reuse, keyed by BattleShip's complete value inputs.

Cache storage belongs to each ColorCombiner (same lifetime as its mappings).
Shade remains per vertex. Distance LOD uses the first vertex exactly as before.
No command-side invalidation assumptions or retained RDP/resource pointers.
"""
from profile_projections import once

FIELDS='''    struct XboxConstantKey {
        uint32_t prim,env,w;
        uint8_t inputs,flags,fraction;
        bool operator==(const XboxConstantKey& rhs) const {
            return prim==rhs.prim && env==rhs.env && w==rhs.w &&
                inputs==rhs.inputs && flags==rhs.flags && fraction==rhs.fraction;
        }
    };
    struct XboxConstantValue {
        uint8_t shadeRgb,shadeAlpha;
        float constants[28];
    };
    Shipyard::Fast3D::MaterialValueCache<XboxConstantKey,XboxConstantValue> xboxConstants;'''

def header(text):
    text=once(text,'#pragma once','#pragma once\n#include "fast3d/material_value_cache.h"')
    return once(text,'    uint8_t shader_input_mapping[2][7];',
                '    uint8_t shader_input_mapping[2][7];\n'+FIELDS)

def helpers(text):
    first=text.index('                switch (comb->shader_input_mapping[k][j])',
                     text.index('    // SoH packs the same attribute'))
    last=text.index('            const bool shade=',first)
    selection=text[first:last].replace('v_arr[0]','v1')
    return '''// XBOX TRIANGLE CONSTANT HELPERS BEGIN
static __declspec(noinline) void XboxBuildTriangleConstants(ColorCombiner* comb,const RDP* mRdp,
        LoadedVertex* v1,unsigned numInputs,bool use_alpha,ColorCombiner::XboxConstantValue& value) {
    // TEST CONSTANT BUILD
    const RGBA* color;RGBA tmp;
    value.shadeRgb=value.shadeAlpha=0;
    float* output=value.constants;
    for(unsigned j=0;j<numInputs;++j)for(int k=0;k<1+(use_alpha?1:0);++k) {
'''+selection+'''
        const bool shade=color==&v1->color;
        if(k==0) {
            if(shade)value.shadeRgb|=1<<j;
            *output++=shade?0.0f:Shipyard::Fast3D::UnitColor(color->r);
            *output++=shade?0.0f:Shipyard::Fast3D::UnitColor(color->g);
            *output++=shade?0.0f:Shipyard::Fast3D::UnitColor(color->b);
        } else {
            if(shade)value.shadeAlpha|=1<<j;
            *output++=shade?0.0f:Shipyard::Fast3D::UnitColor(color->a);
        }
    }
}
struct XboxTriangleConstantBuilder {
    ColorCombiner* comb;
    const RDP* rdp;
    LoadedVertex* first;
    unsigned inputs;
    bool alpha;
    void Rebuild(ColorCombiner::XboxConstantValue& value) {
        XboxBuildTriangleConstants(comb,rdp,first,inputs,alpha,value);
    }
};
static __forceinline const ColorCombiner::XboxConstantValue& XboxTriangleConstants(ColorCombiner* comb,const RDP* mRdp,
        LoadedVertex* v1,unsigned numInputs,bool use_alpha) {
    ColorCombiner::XboxConstantKey key;
    memcpy(&key.prim,&mRdp->prim_color,4);memcpy(&key.env,&mRdp->env_color,4);
    const bool lod=(mRdp->other_mode_l&G_TL_LOD)!=0;
    key.w=0;
    if(lod)memcpy(&key.w,&v1->w,4);
    key.inputs=(uint8_t)numInputs;
    key.flags=(use_alpha?1:0)|(lod?2:0);
    key.fraction=mRdp->prim_lod_fraction;
    XboxTriangleConstantBuilder builder={comb,mRdp,v1,numInputs,use_alpha};
    return comb->xboxConstants.Load(key,builder);
}
// XBOX TRIANGLE CONSTANT HELPERS END

'''

def transform(text):
    body=helpers(text)
    start=text.index('    for(int j=0;j<numInputs;++j)',text.index('    // SoH packs the same attribute'))
    end=text.index('    mBufVboLen += 3*xboxStride;',start)
    text=text[:start]+'''    const ColorCombiner::XboxConstantValue* xboxValue=numInputs?
        &XboxTriangleConstants(comb,mRdp,v1,numInputs,use_alpha):nullptr;
    const float* xboxConstants=xboxValue?xboxValue->constants:nullptr;
    for(int j=0;j<numInputs;++j) {
        const bool shadeRgb=(xboxValue->shadeRgb&(1<<j))!=0;
        for(int i=0;i<3;++i) {
            xboxRows[i][xboxOffset]=shadeRgb?Shipyard::Fast3D::UnitColor(v_arr[i]->color.r):xboxConstants[0];
            xboxRows[i][xboxOffset+1]=shadeRgb?Shipyard::Fast3D::UnitColor(v_arr[i]->color.g):xboxConstants[1];
            xboxRows[i][xboxOffset+2]=shadeRgb?Shipyard::Fast3D::UnitColor(v_arr[i]->color.b):xboxConstants[2];
        }
        xboxOffset+=3;xboxConstants+=3;
        if(use_alpha) {
            const bool shadeAlpha=(xboxValue->shadeAlpha&(1<<j))!=0;
            for(int i=0;i<3;++i)xboxRows[i][xboxOffset]=shadeAlpha?
                (use_fog && !use_blend_color?1.0f:Shipyard::Fast3D::UnitColor(v_arr[i]->color.a)):*xboxConstants;
            ++xboxOffset;++xboxConstants;
        }
    }
'''+text[end:]
    return once(text,'// XBOX THREE ROW PACK HELPERS BEGIN',body+'// XBOX THREE ROW PACK HELPERS BEGIN')
