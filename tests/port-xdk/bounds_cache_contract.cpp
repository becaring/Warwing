#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <thread>
#include <atomic>
#include <vector>
#include "port_dl_ranges.h"
extern "C" void original_register(const void*,size_t,const char*);
extern "C" void original_unregister(const void*);
extern "C" int original_check(uintptr_t);
extern thread_local unsigned testBoundsScans;
static const uintptr_t maxAddress=~uintptr_t(0);
static void require(bool ok,const char* message) { if(!ok) { fprintf(stderr,"FAIL %s\n",message); exit(1); } }
static void add(uintptr_t b,size_t n,const char*label="test") { original_register((void*)b,n,label);port_dl_range_register((void*)b,n,label); }
static void remove(uintptr_t b) { original_unregister((void*)b);port_dl_range_unregister((void*)b); }
static int compare(uintptr_t a) { int expected=original_check(a), got=port_dl_check_addr(a); if(got!=expected) { fprintf(stderr,"addr=%llx expected=%d got=%d\n",(unsigned long long)a,expected,got); require(false,"classification differs from pinned checker"); } return got; }
static uint32_t rng=0x3911abde;
static uint32_t next() { rng=rng*1664525u+1013904223u; return rng; }
int main() {
    require(sizeof(uintptr_t)==4,"test must exercise Xbox-width unsigned arithmetic");
    // Consecutive unknown commands must reuse a proved gap, not rescan all ranges.
    add(0x20000,0x100); add(0x60000,0x100);
    require(compare(0x48000)==PORT_DL_UNKNOWN,"gap address");
    unsigned scans=testBoundsScans;
    for(uintptr_t a=0x48008;a<0x49000;a+=8) compare(a);
    require(testBoundsScans==scans,"unknown command walk must not lock/scan repeatedly");
    // Exact boundaries, positive precedence over another range's walked-past tail.
    for(uintptr_t a=0x1fff8;a<=0x30108;a+=8) compare(a);
    add(0x28000,0x1000); require(compare(0x28000)==PORT_DL_IN_RANGE,"overlap overrides walked-past");
    remove(0x28000); require(compare(0x28000)==PORT_DL_WALKED_PAST,"unregister invalidates hit");
    compare(0x48000); add(0x48000,8); require(compare(0x48000)==PORT_DL_IN_RANGE,"new range invalidates negative cache");
    require(compare(0x48008)==PORT_DL_WALKED_PAST,"new tail invalidates negative cache");
    add(0x48000,0x2000); require(compare(0x49000)==PORT_DL_IN_RANGE,"resize invalidates cache");
    add(0x48000,0x2000,"renamed"); compare(0x49000);
    remove(0x48000); remove(0x20000); remove(0x60000);
    // Preserve the original unsigned wrapped-end behavior, including at zero.
    const uintptr_t bases[]={1,0x100,0x10000,maxAddress-0x10000,maxAddress-15,maxAddress};
    const size_t lengths[]={1,16,0x10000,0x10001,size_t(-1)};
    const uintptr_t probes[]={0,1,2,15,16,0xff,0x100,0xffff,0x10000,0x10001,maxAddress-0x10000,maxAddress-16,maxAddress-15,maxAddress-1,maxAddress};
    for(unsigned b=0;b<6;++b) for(unsigned n=0;n<5;++n) {
        add(bases[b],lengths[n]);
        for(unsigned round=0;round<2;++round) for(unsigned p=0;p<15;++p) compare(probes[p]);
        for(unsigned k=0;k<1500;++k) compare(next());
        remove(bases[b]);
    }
    // Random mutation plus queries around every meaningful interval endpoint.
    std::vector<uintptr_t> live;
    for(unsigned i=0;i<4000;++i) {
        uintptr_t b=(next()&0xfffff000u)|0x100u; size_t n=(next()&0x3ffffu)+1;
        if(live.size()>30) { remove(live.front()); live.erase(live.begin()); }
        add(b,n); live.push_back(b);
        const uintptr_t points[]={b-1,b,b+1,b+n-1,b+n,b+n+1,b+n+0xffff,b+n+0x10000,b+n+0x10001};
        for(unsigned j=0;j<9;++j) compare(points[j]);
        for(unsigned j=0;j<100;++j) compare(next());
        if(i%3==0) { add(b,n+0x20000); compare(b+n); }
    }
    for(size_t i=0;i<live.size();++i) remove(live[i]);
    // Release/acquire handshake: each reader reuses its own TLS cache across
    // registrations on another thread, then observes the newly published state.
    std::atomic<unsigned> phase(0),done(0);
    std::thread reader([&] {
        for(unsigned i=1;i<=2000;++i) {
            while(phase.load(std::memory_order_acquire)!=i) std::this_thread::yield();
            int expected=(i&1)?PORT_DL_IN_RANGE:PORT_DL_UNKNOWN;
            require(port_dl_check_addr(0x810000)==expected,"cross-thread generation invalidation");
            require(port_dl_check_addr(0x810008)==expected,"cross-thread repeated hit");
            done.store(i,std::memory_order_release);
        }
    });
    for(unsigned i=1;i<=2000;++i) {
        if(i&1) port_dl_range_register((void*)0x810000,0x100,"thread"); else port_dl_range_unregister((void*)0x810000);
        phase.store(i,std::memory_order_release);
        while(done.load(std::memory_order_acquire)!=i) std::this_thread::yield();
    }
    reader.join();
    puts("PASS ILP32 real checker: unknown scan elimination, original classification differential, overflow, overlap, mutation, concurrent TLS invalidation");
}
