"""SoH scalar projection reuse, preserving BattleShip cull and RCP area math."""
from profile_projections import once

def transform(text):
    text='#include "fast3d/cull_projection.h"\n'+text
    text=once(text,'static std::weak_ptr<Interpreter> mInstance;', '''static std::weak_ptr<Interpreter> mInstance;
static __declspec(thread) Smash360Fast::CullProjection sXboxCullProjection[MAX_VERTICES + 4];''')
    old='''        float dx1 = v1->x / (v1->w) - v2->x / (v2->w);
        float dy1 = v1->y / (v1->w) - v2->y / (v2->w);
        float dx2 = v3->x / (v3->w) - v2->x / (v2->w);
        float dy2 = v3->y / (v3->w) - v2->y / (v2->w);'''
    new='''        Smash360Fast::CullProjection& p1 = sXboxCullProjection[vtx1_idx];
        Smash360Fast::CullProjection& p2 = sXboxCullProjection[vtx2_idx];
        Smash360Fast::CullProjection& p3 = sXboxCullProjection[vtx3_idx];
        p1.Load(v1->x, v1->y, v1->w);
        p2.Load(v2->x, v2->y, v2->w);
        p3.Load(v3->x, v3->y, v3->w);
        float dx1 = p1.x - p2.x;
        float dy1 = p1.y - p2.y;
        float dx2 = p3.x - p2.x;
        float dy2 = p3.y - p2.y;'''
    text=once(text,old,new)
    text=once(text,'        float sx[3], sy[3];','''        float sx[3], sy[3];
        const uint8_t projectionIndices[3] = { vtx1_idx, vtx2_idx, vtx3_idx };''')
    text=once(text,'''            sx[i] = v_arr[i]->x / w;
            sy[i] = v_arr[i]->y / w;''','''            Smash360Fast::CullProjection& projection = sXboxCullProjection[projectionIndices[i]];
            projection.Load(v_arr[i]->x, v_arr[i]->y, v_arr[i]->w);
            sx[i] = projection.x;
            sy[i] = projection.y;''')
    return text
