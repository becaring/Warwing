#include "snprintf.h"
#include <stdio.h>
#include <string.h>
#include <errno.h>
typedef char SmashHostMustBeIlp32[(sizeof(size_t) == 4 && sizeof(ptrdiff_t) == 4) ? 1 : -1];
static int repeated(char *first, char *second, const char *format, ...) {
    va_list arguments;
    va_start(arguments, format);
    int a = Smash360_Vsnprintf(first, 128, format, arguments);
    int b = Smash360_Vsnprintf(second, 128, format, arguments);
    va_end(arguments);
    return a == b && strcmp(first, second) == 0;
}
int main() {
    char result[128], again[128];
    struct {
        char before;
        char bytes[4];
        char after;
    } guarded = {'A', {1, 2, 3, 4}, 'Z'};
    if (Smash360_snprintf(guarded.bytes, 4, "%s", "abcdef") != 6 || strcmp(guarded.bytes, "abc") ||
        guarded.before != 'A' || guarded.after != 'Z')
        return 1;
    if (Smash360_snprintf(NULL, 0, "%s-%d", "abcdef", 42) != 9)
        return 2;
    result[0] = '!';
    if (Smash360_snprintf(result, 0, "abc") != 3 || result[0] != '!')
        return 3;
    if (Smash360_snprintf(result, 1, "abc") != 3 || result[0] != 0)
        return 4;
    if (Smash360_snprintf(result, 4, "abc") != 3 || strcmp(result, "abc"))
        return 5;
    if (Smash360_snprintf(result, 128, "%zu %06zX %.*zu %%zu", (size_t)256, (size_t)0x1234, 4, (size_t)7) != 19 ||
        strcmp(result, "256 001234 0007 %zu"))
        return 6;
    if (!repeated(result, again, "%d/%I64u/%.2f/%s", -256, (unsigned __int64)0x100000002, 1.25, "tail"))
        return 7;
    if (strcmp(result, "-256/4294967298/1.25/tail"))
        return 8;
    if (Smash360_snprintf(result, 128, "%zd", (ptrdiff_t)-512) != 4 || strcmp(result, "-512"))
        return 9;
    errno = 0;
    if (Smash360_snprintf(NULL, 2, "abc") != -1 || errno != EINVAL)
        return 10;
    if (Smash360_snprintf(result, 128, "") != 0 || result[0] != 0)
        return 11;
    errno = 0;
    if (Smash360_snprintf(result, 128, "%zq", 7) != -1 || errno != EINVAL)
        return 12;
    char longFormat[600];
    memset(longFormat, 'a', sizeof(longFormat));
    longFormat[590] = '%';
    longFormat[591] = 'z';
    longFormat[592] = 'u';
    longFormat[593] = 0;
    if (Smash360_snprintf(result, 3, longFormat, (size_t)7) != 591 || result[0] != 'a' || result[1] != 'a' ||
        result[2] != 0)
        return 13;
    return 0;
}
