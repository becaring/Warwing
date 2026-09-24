#include "atomic/atomic.h"
typedef Shipyard::Atomic::atomic<int,Shipyard::Atomic::native_relaxed_counter> DiagnosticAtomic;
typedef char FastAtomicMustRemainFourBytes[sizeof(DiagnosticAtomic)==4?1:-1];
typedef char FastAtomicMustRemainAligned[__alignof(DiagnosticAtomic)>=4?1:-1];

extern "C" __declspec(noinline) int ReadFastRelaxed(const DiagnosticAtomic* p) {
    return p->load(Shipyard::Atomic::memory_order_relaxed);
}
typedef char Atomic64MustRemainEightBytes[sizeof(Shipyard::Atomic::atomic<uint64_t>)==8?1:-1];
typedef char Atomic64MustRemainAligned[__alignof(Shipyard::Atomic::atomic<uint64_t>)>=8?1:-1];
extern "C" __declspec(noinline) uint64_t ReadAcquire64(const Shipyard::Atomic::atomic<uint64_t>* p) {
    return p->load(Shipyard::Atomic::memory_order_acquire);
}
extern "C" __declspec(noinline) unsigned ReadAcquire32(const Shipyard::Atomic::atomic<unsigned>* p) {
    return p->load(Shipyard::Atomic::memory_order_acquire);
}
extern "C" __declspec(noinline) uint64_t ReadSeq64(const Shipyard::Atomic::atomic<uint64_t>* p) {
    return p->load();
}
extern "C" __declspec(noinline) unsigned ReadSeq32(const Shipyard::Atomic::atomic<unsigned>* p) {
    return p->load();
}
extern "C" __declspec(noinline) uint64_t AcquireObserve64(const Shipyard::Atomic::atomic<uint64_t>* p,
        const unsigned* payload,unsigned* result) {
    const uint64_t generation=p->load(Shipyard::Atomic::memory_order_acquire);
    const unsigned seen=*payload;
    *result=seen+1;
    return generation+seen;
}
extern "C" __declspec(noinline) unsigned AcquireObserve32(const Shipyard::Atomic::atomic<unsigned>* p,
        const unsigned* payload,unsigned* result) {
    const unsigned generation=p->load(Shipyard::Atomic::memory_order_acquire);
    const unsigned seen=*payload;
    *result=seen+1;
    return generation+seen;
}
