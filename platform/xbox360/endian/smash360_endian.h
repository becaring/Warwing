#ifndef SMASH360_ENDIAN_H
#define SMASH360_ENDIAN_H

/* Actual host ordering, independent of PORT and compiler brand. Keep this
 * predicate synchronized with the generated LUS endianness.h detection. */
#if (defined(_XBOX) && defined(_M_PPC)) || \
    (defined(__BYTE_ORDER__) && (__BYTE_ORDER__ == __ORDER_BIG_ENDIAN__)) || defined(__BIG_ENDIAN__)
#define SMASH360_HOST_BIG_ENDIAN 1
#else
#define SMASH360_HOST_BIG_ENDIAN 0
#endif

/* These helpers name the representation being repaired. They must never
 * replace general-purpose BSWAP primitives or header-driven BinaryReader. */
static __inline unsigned int smash360UndoLEWordSwap(unsigned int value)
{
#if SMASH360_HOST_BIG_ENDIAN
    return value;
#else
    return ((value >> 24) & 0xffu) | ((value >> 8) & 0xff00u) |
           ((value << 8) & 0xff0000u) | ((value << 24) & 0xff000000u);
#endif
}

static __inline unsigned int smash360UndoLEHalfSwap(unsigned int value)
{
#if SMASH360_HOST_BIG_ENDIAN
    return value;
#else
    return (value << 16) | (value >> 16);
#endif
}

/* Alignment-safe transfer of a BE IEEE-754 binary32 representation. This
 * function changes byte order only; it performs no numerical conversion. */
static __inline void smash360CopyBEFloatBytes(void *destination, const unsigned char *source)
{
    unsigned char *out = (unsigned char *)destination;
    const unsigned char a = source[0], b = source[1], c = source[2], d = source[3];
#if SMASH360_HOST_BIG_ENDIAN
    out[0] = a; out[1] = b; out[2] = c; out[3] = d;
#else
    out[0] = d; out[1] = c; out[2] = b; out[3] = a;
#endif
}
#endif
