/* Verify the donor macro rescan preserves both command words and pkt++. */
#include <PR/mbi.h>
#if defined(_XBOX) && defined(_M_PPC)
/* Fast3D advances by two native pointer words. Padding here breaks TEXRECT's
 * continuation packets even when ordinary one-packet draws still render. */
typedef char check_gfx_stride[(sizeof(Gfx) == 8) ? 1 : -1];
typedef char check_popmtx_layout[(sizeof(Gpopmtx) == 8) ? 1 : -1];
typedef char check_setcolor_layout[(sizeof(Gsetcolor) == 8) ? 1 : -1];
#endif
Gfx rectangle_words[] = {
    gsSPTextureRectangle(40, 80, 120, 160, 0, 32, 64, 1024, 2048)
};
Gfx mode_words[4] = {
    gsDPSetCombineMode(G_CC_PRIMITIVE, G_CC_MODULATEIA_PRIM),
    gsDPSetCombineMode(G_CC_MODULATEIA_PRIM, G_CC_SHADE),
    gsDPSetCombineMode(G_CC_SHADE, G_CC_DECALRGB),
    gsDPSetCombineMode(G_CC_DECALRGB, G_CC_PRIMITIVE)
};
Gfx explicit_words[4] = {
    gsDPSetCombineLERP(0,0,0,PRIMITIVE,0,0,0,PRIMITIVE,TEXEL0,0,PRIMITIVE,0,TEXEL0,0,PRIMITIVE,0),
    gsDPSetCombineLERP(TEXEL0,0,PRIMITIVE,0,TEXEL0,0,PRIMITIVE,0,0,0,0,SHADE,0,0,0,SHADE),
    gsDPSetCombineLERP(0,0,0,SHADE,0,0,0,SHADE,0,0,0,TEXEL0,0,0,0,SHADE),
    gsDPSetCombineLERP(0,0,0,TEXEL0,0,0,0,SHADE,0,0,0,PRIMITIVE,0,0,0,PRIMITIVE)
};
int main(void) {
    Gfx values[4];
    Gfx *cursor = values;
    int i;
    gDPSetCombineMode(cursor++, G_CC_PRIMITIVE, G_CC_MODULATEIA_PRIM);
    gDPSetCombineMode(cursor++, G_CC_MODULATEIA_PRIM, G_CC_SHADE);
    gDPSetCombineMode(cursor++, G_CC_SHADE, G_CC_DECALRGB);
    gDPSetCombineMode(cursor++, G_CC_DECALRGB, G_CC_PRIMITIVE);
    if (cursor != values + 4) return 1;
    for (i = 0; i < 4; ++i) {
        if (values[i].words.w0 != explicit_words[i].words.w0 ||
            values[i].words.w1 != explicit_words[i].words.w1 ||
            mode_words[i].words.w0 != explicit_words[i].words.w0 ||
            mode_words[i].words.w1 != explicit_words[i].words.w1) return 2;
    }
    return 0;
}
