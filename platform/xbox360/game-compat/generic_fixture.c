/* Host/XDK compiler fixture only; never linked into BattleShip. */
typedef unsigned long u32;
typedef struct PortRefGfx { u32 token; } PortRefGfx;
typedef struct PortRefDObjDLLink { u32 token; } PortRefDObjDLLink;
typedef struct Descriptor { PortRefGfx dl; PortRefDObjDLLink link; u32 raw; } Descriptor;
static int effects;
static unsigned int portRefU32Token(unsigned int value) { return value; }
static unsigned int portRefGfxToken(PortRefGfx value) { return value.token + 100; }
static unsigned int portRefDObjDLLinkToken(PortRefDObjDLLink value) { return value.token + 200; }
#define TOKEN(value) _Generic((value), PortRefGfx: portRefGfxToken, PortRefDObjDLLink: portRefDObjDLLinkToken, default: portRefU32Token)(value)
static PortRefGfx next_gfx(void) { PortRefGfx v = { 7 }; ++effects; return v; }
static u32 identity(u32 value) { return value; }
typedef struct Anonymous { union { u32 plain; PortRefGfx wrapped; }; } Anonymous;
int main(void) {
    Descriptor values[2] = { { { 1 }, { 2 }, 3 }, { { 4 }, { 5 }, 6 } };
    Descriptor *p = values;
    PortRefDObjDLLink *link = &p->link;
    u32 raw = 9;
    Anonymous anonymous;
    unsigned int sum = TOKEN(p->dl) + TOKEN(*link) + TOKEN(values[1].raw);
    sum += TOKEN(next_gfx()) + TOKEN((u32)4) + TOKEN(raw);
    { PortRefGfx raw = { 8 }; sum += TOKEN(raw); }
    sum += TOKEN(identity(TOKEN(next_gfx())));
    anonymous.wrapped.token = 3;
    sum += TOKEN(anonymous.wrapped);
    return sum == 747 && effects == 2 ? 0 : 1;
}
