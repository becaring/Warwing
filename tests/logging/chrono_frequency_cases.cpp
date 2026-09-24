#include "platform/xbox360/cpp-compat/async/native.h"
#include "platform/xbox360/cpp-compat/chrono/chrono.h"
#include <cassert>
#include <cstdio>
#include <thread>

// Mock only the two OS clock queries; execute the production clock body.
static __declspec(thread) unsigned frequencyCalls, counterCalls;
static __declspec(thread) int frequencyMode, counterMode;
static BOOL TestFrequency(LARGE_INTEGER* value) {
    ++frequencyCalls;
    if (frequencyMode == 1) { SetLastError(ERROR_NOT_READY); return FALSE; }
    value->QuadPart = frequencyMode == 2 ? 0 :
        frequencyMode == 3 ? INT64_C(9223372037) : INT64_C(50000000);
    return TRUE;
}
static BOOL TestCounter(LARGE_INTEGER* value) {
    ++counterCalls;
    if (counterMode) { SetLastError(ERROR_NOT_READY); return FALSE; }
    value->QuadPart = INT64_C(1234567890123) + counterCalls;
    return TRUE;
}
#define QueryPerformanceFrequency TestFrequency
#define QueryPerformanceCounter TestCounter
#include "sources/clock/chrono.cpp"
#undef QueryPerformanceFrequency
#undef QueryPerformanceCounter

static void Exercise(int mode) {
    frequencyMode = mode;
    if (mode) {
        bool failed = false;
        try { xbox_compat::chrono::steady_clock::now(); }
        catch (const std::overflow_error&) { failed = mode == 3; }
        catch (const xbox_compat::native_error&) { failed = mode != 3; }
        assert(failed);
        frequencyMode = 0;
    }
    const unsigned initialQueries = frequencyCalls;
    for (unsigned i = 0; i < 1000; ++i) {
        const int64_t observed = xbox_compat::chrono::steady_clock::now().time_since_epoch().count();
        const int64_t counter = INT64_C(1234567890123) + counterCalls;
        const int64_t expected = (counter / INT64_C(50000000)) * INT64_C(1000000000) +
            (counter % INT64_C(50000000)) * INT64_C(1000000000) / INT64_C(50000000);
        assert(observed == expected);
    }
    assert(frequencyCalls == initialQueries + 1);
    counterMode = 1;
    bool failed = false;
    try { xbox_compat::chrono::steady_clock::now(); }
    catch (const xbox_compat::native_error& error) { failed = error.native_code() == ERROR_NOT_READY; }
    assert(failed);
    assert(frequencyCalls == initialQueries + 1);
}
int main() {
    std::thread workers[8];
    for (int i = 0; i < 8; ++i) workers[i] = std::thread(Exercise, i % 4);
    for (int i = 0; i < 8; ++i) workers[i].join();
    puts("PASS per-thread frequency reuse, 8000 exact timestamps, invalid-query retries, counter errors");
}
