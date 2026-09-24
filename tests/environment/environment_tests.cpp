#include "environment.h"
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#define CHECK(x) do { if (!(x)) { fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #x); return 1; } } while (0)

int main(int argc, char **argv) {
    CHECK(argc == 3);
    const int expected = atoi(argv[2]);
    CHECK(XboxEnv_Get("SSB64_MAX_FRAMES") == NULL);
    CHECK(XboxEnv_LoadFromFile(NULL) == XBOX_ENV_INVALID);
    CHECK(XboxEnv_LoadFromFile("") == XBOX_ENV_INVALID);
    CHECK(XboxEnv_LoadFromFile(argv[1]) == expected);
    if (expected == XBOX_ENV_LOADED) {
        char *value = XboxEnv_Get("SSB64_MAX_FRAMES");
        CHECK(value && strcmp(value, "123") == 0);
        CHECK(strcmp(XboxEnv_Get("VALUE"), " a=b #literal ") == 0);
        CHECK(strcmp(XboxEnv_Get("EMPTY"), "") == 0);
        CHECK(XboxEnv_Get("missing") == NULL);
        CHECK(XboxEnv_Get("ssb64_max_frames") == NULL);
        CHECK(XboxEnv_Get(NULL) == NULL);
        CHECK(XboxEnv_LoadFromFile("other.env") == XBOX_ENV_ALREADY_INITIALIZED);
        CHECK(XboxEnv_Get("SSB64_MAX_FRAMES") == value);
    } else {
        CHECK(XboxEnv_Get("SSB64_MAX_FRAMES") == NULL);
        if (expected == XBOX_ENV_ABSENT)
            CHECK(XboxEnv_LoadFromFile("other.env") == XBOX_ENV_ALREADY_INITIALIZED);
    }
    puts("environment test PASS");
    return 0;
}
