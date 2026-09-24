#include <stdint.h>
#include <stdio.h>
#include <string.h>
extern "C" float __libm_qnan_f;
int main() {
    uint32_t bits = 0;
    memcpy(&bits, &__libm_qnan_f, sizeof(bits));
    if (sizeof(float) != 4 || bits != 0x7fc00000u || __libm_qnan_f == __libm_qnan_f) return 1;
    puts("PASS actual game NaN symbol after CRT initialization: 7fc00000");
    return 0;
}
