#include "atomic/atomic.h"
#include "clock/sleep.h"
#include "math/color.h"
#include "port_log.h"
#include <cassert>
#include <cstdio>
#include <cstring>
#include <string>
#ifndef _XBOX
#include <cmath>
#include <limits>
#endif

static Shipyard::Atomic::atomic<uint64_t> count(0);
static Shipyard::Atomic::atomic<bool> ready(false);
static Shipyard::Atomic::atomic<uint64_t> publication(0), acknowledgement(0);
static uint64_t payload[2];
static void published_reader(void*) {
    for (uint64_t i=1;i<=10000;++i) {
        while(publication.load(Shipyard::Atomic::memory_order_acquire)!=i) Sleep(0);
        assert(payload[0]==i && payload[1]==~i);
        acknowledgement.store(i,Shipyard::Atomic::memory_order_release);
    }
}
static void worker(void*) {
    while (!ready.load(Shipyard::Atomic::memory_order_acquire)) Sleep(0);
    for (int i = 0; i < 25000; ++i) count.fetch_add(1, Shipyard::Atomic::memory_order_relaxed);
}
int main() {
#ifndef _XBOX
    for(int sample=-20000;sample<=20000;++sample) {
        float component=float(sample)/10000;
        assert(Shipyard::Math::ColorByte(component)==static_cast<uint8_t>(std::fmin(std::fmax(double(component*255),0.0),255.0)));
    }
    assert(Shipyard::Math::ColorByte(std::numeric_limits<float>::quiet_NaN())==0);
    assert(Shipyard::Math::ColorByte(std::numeric_limits<float>::infinity())==255);
    assert(Shipyard::Math::ColorByte(-std::numeric_limits<float>::infinity())==0);
#endif
    assert(sizeof(size_t) == 4);
    Shipyard::Atomic::atomic<uint64_t> wide(UINT64_C(0xfffffffffffffffe));
    assert(wide.fetch_add(3) == UINT64_C(0xfffffffffffffffe));
    assert(wide.load() == 1);
    wide.store(UINT64_C(0x8000000012345678));
    uint64_t expected = 1;
    assert(!wide.compare_exchange_strong(expected, 9));
    assert(expected == UINT64_C(0x8000000012345678));
    assert(wide.compare_exchange_strong(expected, 9));
    Shipyard::Atomic::atomic<int> signedValue(-1);
    assert(signedValue.fetch_add(1) == -1 && signedValue.load() == 0);
    Shipyard::Atomic::atomic<unsigned> live(4);
    assert(live.fetch_sub(1,Shipyard::Atomic::memory_order_acq_rel)==4 && live.load()==3);
    live.store(0);assert(live.fetch_sub(1)==0 && live.load()==0xffffffffu);
    assert(live.fetch_add(1)==0xffffffffu && live.load()==0);
    Shipyard::Atomic::atomic<int> minimum(INT32_MIN);
    assert(minimum.fetch_sub(INT32_MIN)==INT32_MIN && minimum.load()==0);
    bool no = false;
    assert(ready.compare_exchange_strong(no, false));
    xbox_compat::joining_thread a(worker, 0), b(worker, 0), c(worker, 0), d(worker, 0);
    ready.store(true, Shipyard::Atomic::memory_order_release);
    a.join(); b.join(); c.join(); d.join();
    assert(count.load() == 100000);
    xbox_compat::joining_thread reader(published_reader,0);
    for(uint64_t i=1;i<=10000;++i) {
        payload[0]=i;payload[1]=~i;
        publication.store(i,Shipyard::Atomic::memory_order_release);
        while(acknowledgement.load(Shipyard::Atomic::memory_order_acquire)!=i) Sleep(0);
    }
    reader.join();
    assert(Shipyard::Clock::WaitMilliseconds(-1) == 0);
    assert(Shipyard::Clock::WaitMilliseconds(0) == 0);
    assert(Shipyard::Clock::WaitMilliseconds(1) == 1);
    assert(Shipyard::Clock::WaitMilliseconds(1000000) == 1);
    assert(Shipyard::Clock::WaitMilliseconds(1000001) == 2);
    assert(Shipyard::Clock::WaitMilliseconds(INT64_MAX) == 0xfffffffeu);
    typedef Shipyard::Clock::steady_clock Clock;
    Clock::time_point begin = Clock::now();
    Shipyard::Clock::SleepFor(Shipyard::Clock::milliseconds(15));
    assert(Clock::now() - begin >= Shipyard::Clock::milliseconds(15));
    Shipyard::Clock::SleepFor(Shipyard::Clock::nanoseconds(-100));

    port_log("ignored before open %d", 1);
    assert(port_log_get_fd() == -1);
    port_log_init("port-log-contract.bin");
    assert(port_log_get_fd() >= 0);
    port_log_init("must-not-reopen.bin");
    std::string large(20000, 'X');
    port_log("size=%zu hex=%08zX signed=%zd value=%lld fraction=%.2f\n", size_t(4294967295u), size_t(0xabcd), ptrdiff_t(-7), INT64_C(1234567890123), 1.25);
    port_log("%s%cEND", large.c_str(), 0);
    port_log_close();
    assert(port_log_get_fd() == -1);
    FILE* file = fopen("port-log-contract.bin", "rb");
    assert(file);
    char buffer[21000]; size_t length = fread(buffer, 1, sizeof(buffer), file); fclose(file);
    const char prefix[] = "size=4294967295 hex=0000ABCD signed=-7 value=1234567890123 fraction=1.25\r\n";
    assert(length == sizeof(prefix)-1 + large.size() + 4);
    assert(memcmp(buffer, prefix, sizeof(prefix)-1) == 0);
    assert(memcmp(buffer + sizeof(prefix)-1, large.data(), large.size()) == 0);
    assert(memcmp(buffer + length - 4, "\0END", 4) == 0);
    port_log("ignored after close");
    return 0;
}
