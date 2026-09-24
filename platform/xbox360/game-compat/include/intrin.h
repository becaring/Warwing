#ifndef SMASH360_GAME_NATIVE_INTRIN_H
#define SMASH360_GAME_NATIVE_INTRIN_H
#if !defined(_XBOX) || !defined(_M_PPC)
#error This declaration is for the native Xbox 360 compiler only
#endif
/* XDK rtcapi.h declares this native compiler intrinsic for C++; the C game
 * needs the same zero-argument declaration without desktop intrin.h. */
#ifdef __cplusplus
extern "C" {
#endif
void *_ReturnAddress(void);
#pragma intrinsic(_ReturnAddress)
#ifdef __cplusplus
}
#endif
#endif
