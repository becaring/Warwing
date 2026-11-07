#ifndef SMASH360_GAME_COMPILER_COMPAT_H
#define SMASH360_GAME_COMPILER_COMPAT_H

/* Spelling compatibility only. Keep all upstream layout predicates active. */
#if !defined(_XBOX) || !defined(_MSC_VER) || defined(__cplusplus)
#error This header is for the XDK C compiler only
#endif
#define SMASH360_JOIN_INNER(a, b) a##b
#define SMASH360_JOIN(a, b) SMASH360_JOIN_INNER(a, b)
#define _Static_assert(condition, message) \
    typedef char SMASH360_JOIN(smash360_static_assert_, __COUNTER__)[(condition) ? 1 : -1]
#define inline __inline
/* SoH360's active CALL_2 rescan workaround, namespaced for this C boundary. */
#define SMASH360_GBI_APPLY(macro, arguments) macro arguments

/* The platform layer supplies the environment and configuration. This
 * declaration adds no fallback value and no stub that returns success.
 * The platform implementation must keep getenv's pointer lifetime. */
extern char *XboxEnv_Get(const char *name);
#define getenv XboxEnv_Get

#endif
