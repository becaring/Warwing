/* The ovl8 window calls that the restored debug menu (db/dbmenu.c) makes.
 * ovl8 is a vtable-driven UI library with undecompiled parts; the menu only
 * needs one window holding a bitmap with rect fills and 8x8 glyphs, drawn on top
 * of the scene. The bitmap is RGBA5551 in host order, which is N64 order on Xbox.
 * Fast3D caches textures by address, so a changed bitmap is invalidated in the
 * display list before it is drawn. It is drawn in strips that fit 4 KB of TMEM. */
#include <db/debug.h>
#include <lb/library.h>
#include <sys/objhelper.h>
#include <string.h>

// The highest link a camera's 64-bit mask can name; the game uses up to 38.
#define DBWINDOW_DLLINK 63
#define DBWINDOW_MAX_W 128
#define DBWINDOW_MAX_H 160

extern DBFont dDBMenuDefaultFont;
extern u32 dDBMenuTextColor;

static u16 sDBWindowPixels[DBWINDOW_MAX_W * DBWINDOW_MAX_H];
static DBMenuPosition sDBWindowPosition;
static s32 sDBWindowStride;
static s32 sDBWindowCursorX;
static s32 sDBWindowCursorY;
static sb32 sDBWindowIsDirty;
static GObj *sDBWindowGObj;
static GObj *sDBWindowCamera;

static u16 dbWindowPackColor(u32 rgba)
{
	return (u16)((((rgba >> 27) & 0x1F) << 11) | (((rgba >> 19) & 0x1F) << 6) | (((rgba >> 11) & 0x1F) << 1) | ((rgba & 0xFF) ? 1 : 0));
}

static void dbWindowFill(s32 x, s32 y, s32 w, s32 h, u16 color)
{
	s32 i, j;

	for (j = y; j < y + h; j++)
	{
		for (i = x; i < x + w; i++)
		{
			if ((i >= 0) && (j >= 0) && (i < sDBWindowPosition.w) && (j < sDBWindowPosition.h))
			{
				sDBWindowPixels[j * sDBWindowStride + i] = color;
			}
		}
	}
	sDBWindowIsDirty = TRUE;
}

static void dbWindowDraw(GObj *gobj)
{
	Gfx *dl;
	s32 rows = 4096 / (sDBWindowStride * sizeof(u16));
	s32 y;

	if (sDBWindowPosition.h == 0)
	{
		return;
	}
	dl = gSYTaskmanDLHeads[0];

	gDPPipeSync(dl++);
	gDPSetCycleType(dl++, G_CYC_1CYCLE);
	gDPSetRenderMode(dl++, G_RM_OPA_SURF, G_RM_OPA_SURF2);
	gDPSetCombineMode(dl++, G_CC_DECALRGBA, G_CC_DECALRGBA);
	gDPSetTexturePersp(dl++, G_TP_NONE);
	gDPSetTextureFilter(dl++, G_TF_POINT);
	gDPSetTextureLUT(dl++, G_TT_NONE);

	for (y = 0; y < sDBWindowPosition.h; y += rows)
	{
		s32 h = ((sDBWindowPosition.h - y) < rows) ? (sDBWindowPosition.h - y) : rows;
		u16 *strip = &sDBWindowPixels[y * sDBWindowStride];

		if (sDBWindowIsDirty != FALSE)
		{
			// LUS G_INVALTEXCACHE: drop the cached texture at this address.
			dl->words.w0 = (uintptr_t)0x34 << 24;
			dl->words.w1 = (uintptr_t)strip;
			dl++;
		}
		gDPLoadTextureBlock
		(
			dl++,
			strip,
			G_IM_FMT_RGBA,
			G_IM_SIZ_16b,
			sDBWindowStride,
			h,
			0,
			G_TX_CLAMP,
			G_TX_CLAMP,
			G_TX_NOMASK,
			G_TX_NOMASK,
			G_TX_NOLOD,
			G_TX_NOLOD
		);
		gSPTextureRectangle
		(
			dl++,
			sDBWindowPosition.x << 2,
			(sDBWindowPosition.y + y) << 2,
			(sDBWindowPosition.x + sDBWindowPosition.w) << 2,
			(sDBWindowPosition.y + y + h) << 2,
			G_TX_RENDERTILE,
			0,
			0,
			1 << 10,
			1 << 10
		);
	}
	gDPPipeSync(dl++);

	gSYTaskmanDLHeads[0] = dl;
	sDBWindowIsDirty = FALSE;
}

// Opens the window for a menu and returns its handle.
s32 func_ovl8_80381C80(DBMenu *menu)
{
	sDBWindowPosition = menu->position;

	if (sDBWindowPosition.w > DBWINDOW_MAX_W)
	{
		sDBWindowPosition.w = DBWINDOW_MAX_W;
	}
	if (sDBWindowPosition.h > DBWINDOW_MAX_H)
	{
		sDBWindowPosition.h = DBWINDOW_MAX_H;
	}
	sDBWindowStride = (sDBWindowPosition.w + 3) & ~3;

	dbWindowFill(0, 0, sDBWindowPosition.w, sDBWindowPosition.h, dbWindowPackColor(GPACK_RGBA8888(menu->bg_color.r, menu->bg_color.g, menu->bg_color.b, 0xFF)));

	return 1;
}

// Makes the actor whose display proc draws the window, plus a camera for its link.
GObj* func_ovl8_80374910(s32 window)
{
	sDBWindowCamera = gcMakeCameraGObj(5, NULL, 12, GOBJ_PRIORITY_DEFAULT, lbCommonDrawSprite, 10, COBJ_MASK_DLLINK(DBWINDOW_DLLINK), -1, 0, 1, NULL, 1, 0);
	sDBWindowGObj = gcMakeGObjSPAfter(0, NULL, 12, GOBJ_PRIORITY_DEFAULT);
	gcAddGObjDisplay(sDBWindowGObj, dbWindowDraw, DBWINDOW_DLLINK, GOBJ_PRIORITY_DEFAULT, ~0);

	return sDBWindowGObj;
}

DBMenuPosition* func_ovl8_803749BC(s32 window)
{
	return &sDBWindowPosition;
}

void func_ovl8_80374A54(s32 window, DBMenu *menu)
{
	menu->position = sDBWindowPosition;
}

// Fills a rectangle; color is the address of an RGBA8888 word.
void func_ovl8_80377AEC(DBMenuPosition *target, DBMenuPosition *rect, u32 color, s32 unused)
{
	dbWindowFill(rect->x, rect->y, rect->w, rect->h, dbWindowPackColor(*(u32*)color));
}

void func_ovl8_8037DFCC(s16 x, s16 y)
{
	sDBWindowCursorX = x;
	sDBWindowCursorY = y;
}

// Draws text at the cursor with the menu's 1 bpp font.
void func_ovl8_8037DD60(DBMenuPosition *target, char *str)
{
	const u8 *glyphs = (const u8*)dDBMenuDefaultFont.glyphs;
	u16 color = dbWindowPackColor(dDBMenuTextColor);
	s32 x = sDBWindowCursorX;

	for (; *str != '\0'; str++)
	{
		s32 index = (u8)*str - ' ';
		s32 row, column, width;

		if ((index < 0) || (index > ('~' - ' ')))
		{
			index = '?' - ' ';
		}
		width = dDBMenuDefaultFont.width - dDBMenuDefaultFont.padding[index].right_padding;

		for (row = 0; row < dDBMenuDefaultFont.height; row++)
		{
			u8 bits = glyphs[index * dDBMenuDefaultFont.height + row];

			for (column = 0; column < width; column++)
			{
				if (bits & (0x80 >> column))
				{
					dbWindowFill(x + column, sDBWindowCursorY + row, 1, 1, color);
				}
			}
		}
		x += width;
	}
}

static void dbWindowClose(void)
{
	if (sDBWindowGObj != NULL)
	{
		gcEjectGObj(sDBWindowGObj);
		gcEjectGObj(sDBWindowCamera);
		sDBWindowGObj = sDBWindowCamera = NULL;
	}
	sDBWindowPosition.h = 0;
}

void func_ovl8_8037488C(s32 window)
{
	dbWindowClose();
}

void func_ovl8_8037BB78(void)
{
	dbWindowClose();
}

// Runs at each debug scene start; a window left open by the previous scene went with its heap.
void func_ovl8_8037B98C(DBTextBuffer *buffer)
{
	sDBWindowGObj = sDBWindowCamera = NULL;
	sDBWindowPosition.h = 0;
}

// Font and color setup: the window draws with the menu font and text color directly.
void func_ovl8_8037D6D4(DBFont *font) {}
void func_ovl8_8037D9D0(u32 *color) {}
void func_ovl8_8037D9B4(u32 *colors) {}
void func_ovl8_8037D95C(s32 *attributes) {}
void func_ovl8_8037D908(s32 *attributes) {}

// The Back menu checkbox; boot and console reset enter the battle debug menu while it is set.
sb32 portDebugBattleIsBootScene(void)
{
	extern int CVarGetInteger(const char *name, int default_value);

	return CVarGetInteger("gDeveloperTools.BootToDebugBattle", 0) != 0;
}
