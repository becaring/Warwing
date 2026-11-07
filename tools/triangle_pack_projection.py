"""Adapt SoH's three-row packing: invariant work once, exact BattleShip values.

Retain the stream layout and arithmetic, including Smash framebuffer UVs,
primitive depth, fog-alpha mux and blend-color mode. Draw batching is unchanged.
"""
from profile_projections import once

HELPERS='''// XBOX THREE ROW PACK HELPERS BEGIN
static __forceinline void XboxCoordinate3(float& a,float& b,float& c,
    float v0,float v1,float v2,int shift,float start,bool half,float dimension,float scale,float offset) {
    a=Shipyard::Fast3D::Coordinate(v0,shift,start,half,dimension)*scale+offset;
    b=Shipyard::Fast3D::Coordinate(v1,shift,start,half,dimension)*scale+offset;
    c=Shipyard::Fast3D::Coordinate(v2,shift,start,half,dimension)*scale+offset;
}
// XBOX THREE ROW PACK HELPERS END

'''

def transform(text):
    start=text.index('    float* xboxVertexOutput = mBufVbo + mBufVboLen;')
    end=text.index('    mBufVboLen = (size_t)(xboxVertexOutput - mBufVbo);',start)
    end+=len('    mBufVboLen = (size_t)(xboxVertexOutput - mBufVbo);')
    original=text[start:end]
    # Keep the depth conversion block verbatim.
    pos_start=original.index('        float z =')
    pos_end=original.index('        for (int t =',pos_start)
    positions=original[pos_start:pos_end]
    switch_start=original.index('                switch (comb->shader_input_mapping[k][j])')
    switch_end=original.index('                if (k == 0)',switch_start)
    selection=original[switch_start:switch_end].replace('v_arr[i]','v_arr[0]')
    if positions.count('*xboxVertexOutput++')!=4 or selection.count('case ')!=8:
        raise ValueError('Re-audit BattleShip position/combiner packing')
    replacement='''    // SoH packs the same attribute for three rows together. Resolve stride
    // once; no position, texture, fog, shade or combiner field is omitted.
    unsigned xboxStride=4;
    for(unsigned t=0;t<2;++t)if(usedTextures[t])
        xboxStride+=2+((tm>>(2*t))&1)+((tm>>(2*t+1))&1);
    if(use_fog)xboxStride+=4;
    if(use_grayscale)xboxStride+=4;
    xboxStride+=numInputs*(use_alpha?4:3);
    float* xboxRows[3]={mBufVbo+mBufVboLen,mBufVbo+mBufVboLen+xboxStride,
                       mBufVbo+mBufVboLen+2*xboxStride};
    for(int i=0;i<3;++i) {
        float* xboxVertexOutput=xboxRows[i];
'''+positions+'''    }
    unsigned xboxOffset=4;
    const bool xboxHalfTexel=!is_rect && (mRdp->other_mode_h & (3U<<G_MDSFT_TEXTFILT))!=G_TF_POINT;
    for(int t=0;t<2;++t) {
        if(!usedTextures[t])continue;
        const uint32_t tile=effective_tile[t];
        const FbUvTransform& xf=mFbUvTransform[t];
        XboxCoordinate3(xboxRows[0][xboxOffset],xboxRows[1][xboxOffset],xboxRows[2][xboxOffset],
            v_arr[0]->u,v_arr[1]->u,v_arr[2]->u,mRdp->texture_tile[tile].shifts,
            mRdp->texture_tile[tile].uls,xboxHalfTexel,xboxTextureWidth[t],xf.scaleU,xf.offsetU);
        ++xboxOffset;
        XboxCoordinate3(xboxRows[0][xboxOffset],xboxRows[1][xboxOffset],xboxRows[2][xboxOffset],
            v_arr[0]->v,v_arr[1]->v,v_arr[2]->v,mRdp->texture_tile[tile].shiftt,
            mRdp->texture_tile[tile].ult,xboxHalfTexel,xboxTextureHeight[t],xf.scaleV,xf.offsetV);
        ++xboxOffset;
        if(tm & (1<<(2*t))) {
            float limit=(xboxTextureBoundWidth[t]-0.5f)/xboxTextureWidth[t];
            limit=limit*xf.scaleU+xf.offsetU;
            for(int i=0;i<3;++i)xboxRows[i][xboxOffset]=limit;
            ++xboxOffset;
        }
        if(tm & (1<<(2*t+1))) {
            float limit=(xboxTextureBoundHeight[t]-0.5f)/xboxTextureHeight[t];
            limit=limit*xf.scaleV+xf.offsetV;
            for(int i=0;i<3;++i)xboxRows[i][xboxOffset]=limit;
            ++xboxOffset;
        }
    }
    if(use_fog) {
        const RGBA& fogRgb=use_blend_color?mRdp->blend_color:mRdp->fog_color;
        const float r=Shipyard::Fast3D::UnitColor(fogRgb.r),g=Shipyard::Fast3D::UnitColor(fogRgb.g),
                    b=Shipyard::Fast3D::UnitColor(fogRgb.b);
        const bool constantAlpha=use_blend_color || ((mRdp->other_mode_l>>26)&3)==G_BL_A_FOG;
        const float alpha=Shipyard::Fast3D::UnitColor(mRdp->fog_color.a);
        for(int i=0;i<3;++i) {
            xboxRows[i][xboxOffset]=r;xboxRows[i][xboxOffset+1]=g;xboxRows[i][xboxOffset+2]=b;
            xboxRows[i][xboxOffset+3]=constantAlpha?alpha:Shipyard::Fast3D::UnitColor(v_arr[i]->color.a);
        }
        xboxOffset+=4;
    }
    if(use_grayscale) {
        const float r=Shipyard::Fast3D::UnitColor(mRdp->grayscale_color.r),g=Shipyard::Fast3D::UnitColor(mRdp->grayscale_color.g),
                    b=Shipyard::Fast3D::UnitColor(mRdp->grayscale_color.b),a=Shipyard::Fast3D::UnitColor(mRdp->grayscale_color.a);
        for(int i=0;i<3;++i) {
            xboxRows[i][xboxOffset]=r;xboxRows[i][xboxOffset+1]=g;
            xboxRows[i][xboxOffset+2]=b;xboxRows[i][xboxOffset+3]=a;
        }
        xboxOffset+=4;
    }
    for(int j=0;j<numInputs;++j) {
        RGBA* color;RGBA tmp;
        for(int k=0;k<1+(use_alpha?1:0);++k) {
'''+selection+'''            const bool shade=color==&v_arr[0]->color;
            if(k==0) {
                const float r=Shipyard::Fast3D::UnitColor(color->r),g=Shipyard::Fast3D::UnitColor(color->g),b=Shipyard::Fast3D::UnitColor(color->b);
                for(int i=0;i<3;++i) {
                    xboxRows[i][xboxOffset]=shade?Shipyard::Fast3D::UnitColor(v_arr[i]->color.r):r;
                    xboxRows[i][xboxOffset+1]=shade?Shipyard::Fast3D::UnitColor(v_arr[i]->color.g):g;
                    xboxRows[i][xboxOffset+2]=shade?Shipyard::Fast3D::UnitColor(v_arr[i]->color.b):b;
                }
                xboxOffset+=3;
            } else {
                const float a=Shipyard::Fast3D::UnitColor(color->a);
                for(int i=0;i<3;++i)xboxRows[i][xboxOffset]=
                    shade?(use_fog && !use_blend_color?1.0f:Shipyard::Fast3D::UnitColor(v_arr[i]->color.a)):a;
                ++xboxOffset;
            }
        }
    }
    mBufVboLen += 3*xboxStride;'''
    text=once(text,original,replacement)
    text=once(text,'void Interpreter::GfxSpTri1(',HELPERS+'void Interpreter::GfxSpTri1(')
    return '#include "fast3d/coordinate.h"\n'+text
