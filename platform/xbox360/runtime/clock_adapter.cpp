#include "chrono/chrono.h"
#include "runtime.h"

double Smash360_Time() {
    return static_cast<double>(xbox_compat::chrono::steady_clock::now().time_since_epoch().count()) / 1000000000.0;
}
