#include "filesystem.h"
void unsupported_operation_must_not_compile() {
    xbox_compat::filesystem::remove_all("game:/unsafe-recursion");
}
