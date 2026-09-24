#ifndef SMASH360_ENVIRONMENT_H
#define SMASH360_ENVIRONMENT_H

#ifdef __cplusplus
extern "C" {
#endif

enum XboxEnvStatus {
    XBOX_ENV_LOADED = 0,
    XBOX_ENV_ABSENT = 1,
    XBOX_ENV_IO_ERROR = 2,
    XBOX_ENV_INVALID = 3,
    XBOX_ENV_ALREADY_INITIALIZED = 4
};

/* Initialize once, before starting workers. Values then remain valid for the
 * process lifetime. Missing optional file means an empty environment. */
int XboxEnv_LoadFromFile(const char *path);
char *XboxEnv_Get(const char *name);

#ifdef __cplusplus
}
#endif
#endif
