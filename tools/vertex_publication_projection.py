"""SoH finite fog selects and delayed bounded RGB byte loads.

The loaded vertex is fully published before the next vertex, shade cache store,
or command. Source aliases and exceptional integer lighting retain original
publication. This does not defer any game-observable work across commands.
"""
from profile_projections import once

def transform(text):
    start=text.index('void Interpreter::GfxSpVertex(')
    end=text.index('void Interpreter::GfxSpModifyVertex(',start)
    original=text[start:end]
    vertex=once(original,'    const bool xboxFiniteClip=xboxVectorPositions &&',
        '''    // SoH computes its aspect factor once per batch. Keep BattleShip's
    // exact window-derived multiplication, including the framebuffer bypass.
    const float xboxAspectScale=xboxTransformBatch && !mFbActive?GetWidescreenClipXScale():1.0f;
    const bool xboxFiniteClip=xboxVectorPositions &&''')
    vertex=once(vertex,'Shipyard::Fast3D::FiniteUnitClipScale(GetWidescreenClipXScale())',
                'Shipyard::Fast3D::FiniteUnitClipScale(xboxAspectScale)')
    vertex=once(vertex,'        x = AdjXForAspectRatio(x);',
                '        x = xboxTransformBatch?(mFbActive?x:x*xboxAspectScale):AdjXForAspectRatio(x);')
    vertex=once(vertex,'        const F3DVtx_t* v = &vertices[i].v;',
        '''        Shipyard::Fast3D::DeferredVertexBytes xboxColorBytes;
        bool xboxDeferredRgb=false;
        const F3DVtx_t* v = &vertices[i].v;''')
    publication='''            if (xboxFloatLight) {
                r = (int)xboxLightR;
                g = (int)xboxLightG;
                b = (int)xboxLightB;
            }

            d->color.r = r > 255 ? 255 : r;
            d->color.g = g > 255 ? 255 : g;
            d->color.b = b > 255 ? 255 : b;'''
    vertex=once(vertex,publication,'''            if(xboxFloatLight && xboxTransformBatch) {
                // FPR conversion stores now; integer loads follow fog/UV work.
                // These channels are finite nonnegative integers below 2^23.
                xboxColorBytes.Store(0,Shipyard::Fast3D::VertexColorLimit(xboxLightR));
                xboxColorBytes.Store(1,Shipyard::Fast3D::VertexColorLimit(xboxLightG));
                xboxColorBytes.Store(2,Shipyard::Fast3D::VertexColorLimit(xboxLightB));
                xboxDeferredRgb=true;
            } else {
'''+publication+'''
            }''')
    start=vertex.index('            if (fabsf(w) < 0.001f) {')
    end=vertex.index('            float fog_z = ',start)
    reciprocal=vertex[start:end].replace('float winv =','winv =')
    vertex=once(vertex,vertex[start:end],'''            float winv;
            if(xboxFiniteClip)winv=Shipyard::Fast3D::VertexFogReciprocalFinite(w);
            else {
'''+reciprocal+'''            }
''')
    vertex=once(vertex,'        // Cache only the fully published vertex attributes.',
        '''        if(xboxDeferredRgb) {
            d->color.r=xboxColorBytes.Load(0);
            d->color.g=xboxColorBytes.Load(1);
            d->color.b=xboxColorBytes.Load(2);
        }
        // Cache only the fully published vertex attributes.''')
    return '#include "fast3d/numeric.h"\n'+once(text,original,vertex)
