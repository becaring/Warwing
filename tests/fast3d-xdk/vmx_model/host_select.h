#pragma once
// Test-only scalar semantics of the donor FPR select. Production uses XDK.
inline double __fsel(double test,double positive,double negative) {
    return test>=0.0?positive:negative;
}
