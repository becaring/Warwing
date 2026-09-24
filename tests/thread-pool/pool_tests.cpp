#define BS_THREAD_POOL_ENABLE_PRIORITY
#define BS_THREAD_POOL_ENABLE_PAUSE
#include "BS_thread_pool.hpp"
#include "native.h"
#include <cstdio>
#include <stdexcept>
#include <string>
#include <vector>
#ifdef TEST_UPSTREAM
namespace results = std;
#else
namespace results = Shipyard::Async;
#endif

static void check(bool condition, const char* message) { if (!condition) throw std::runtime_error(message); }
#define CHECK(x) check(!!(x), #x)

struct Resource { int id; std::string path; };
struct Identifier { int id; std::string path; };
struct InitData { int offset; };
struct Filter { std::string path; };

// Uses both actual ResourceManager capture/result shapes, plus its void submissions.
struct ResourceWork {
    BS::thread_pool pool;
    ResourceWork() : pool(3) {}
    std::shared_ptr<Resource> process(Identifier id, bool exact, std::shared_ptr<InitData> init) {
        std::shared_ptr<Resource> result(new Resource());
        result->id = id.id + init->offset + (exact ? 1 : 0);
        result->path = id.path;
        return result;
    }
    results::shared_future<std::shared_ptr<Resource> > submit(Identifier identifier, bool loadExact, std::shared_ptr<InitData> initData) {
        return pool.submit_task([this, identifier, loadExact, initData]() -> std::shared_ptr<Resource> {
            return process(identifier, loadExact, initData);
        }, BS::pr::highest);
    }
    results::shared_future<std::shared_ptr<std::vector<std::shared_ptr<Resource> > > > directory(Filter filter) {
        return pool.submit_task([this, filter]() -> std::shared_ptr<std::vector<std::shared_ptr<Resource> > > {
            std::shared_ptr<std::vector<std::shared_ptr<Resource> > > list(new std::vector<std::shared_ptr<Resource> >());
            Identifier id = { 6, filter.path };
            std::shared_ptr<InitData> init(new InitData()); init->offset = 4;
            list->push_back(submit(id, true, init).get());
            return list;
        }, BS::pr::normal);
    }
};

static void resource_shapes_and_actual_workers() {
    volatile LONG initialized = 0;
    {
        BS::thread_pool initializedPool(2, [&initialized]() { InterlockedIncrement(&initialized); });
        initializedPool.wait();
        CHECK(initialized == 2 && initializedPool.get_thread_count() == 2);
    }
    ResourceWork work;
    Identifier id = { 20, "resource/path" };
    std::shared_ptr<InitData> init(new InitData()); init->offset = 8;
    results::shared_future<std::shared_ptr<Resource> > resource = work.submit(id, true, init);
    init.reset();
    CHECK(resource.get()->id == 29 && resource.get()->path == "resource/path");
    CHECK(resource.get() == resource.get());
    Filter filter = { "directory/path" };
    CHECK(work.directory(filter).get()->at(0)->id == 11);
    DWORD caller = GetCurrentThreadId();
    results::future<DWORD> workerId = work.pool.submit_task([]() -> DWORD { return GetCurrentThreadId(); });
    CHECK(workerId.get() != caller);
    int dirty = 0;
    results::future<void> dirtied = work.pool.submit_task([&dirty]() -> void { dirty = 1; });
    dirtied.get();
    CHECK(dirty == 1 && !dirtied.valid());
}

static void priorities_pause_and_drain() {
    BS::thread_pool pool(1);
    pool.pause();
    pool.wait();
    std::vector<int> order;
    results::future<int> normal = pool.submit_task([&order]() -> int { order.push_back(1); return 1; }, BS::pr::normal);
    results::future<int> high = pool.submit_task([&order]() -> int { order.push_back(2); return 2; }, BS::pr::highest);
    CHECK(pool.is_paused());
    CHECK(pool.get_tasks_queued() == 2 && pool.get_tasks_running() == 0);
    pool.wait(); // Paused wait drains only running tasks, not queued ones.
    CHECK(order.empty());
    pool.unpause();
    pool.wait();
    CHECK(high.get() == 2 && normal.get() == 1);
    CHECK(order.size() == 2 && order[0] == 2 && order[1] == 1);
    CHECK(pool.get_tasks_total() == 0);
}

static void failures_and_paused_abandonment() {
    BS::thread_pool pool(2);
    results::future<int> failed = pool.submit_task([]() -> int { throw std::runtime_error("resource failed"); });
    bool caught = false;
    try { failed.get(); } catch (const std::runtime_error& e) { caught = std::string(e.what()) == "resource failed"; }
    CHECK(caught);
    results::shared_future<void> voidFailure = pool.submit_task([]() -> void { throw std::runtime_error("dirty failed"); });
    for (int i = 0; i < 2; ++i) {
        caught = false;
        try { voidFailure.get(); } catch (const std::runtime_error& e) { caught = std::string(e.what()) == "dirty failed"; }
        CHECK(caught);
    }
    CHECK(pool.submit_task([]() -> int { return 19; }).get() == 19);
    results::future<int> abandoned;
    results::future<void> voidAbandoned;
    {
        BS::thread_pool paused(1);
        paused.pause(); paused.wait();
        abandoned = paused.submit_task([]() -> int { return 8; });
        voidAbandoned = paused.submit_task([]() -> void {});
    }
    caught = false;
    try { abandoned.get(); } catch (const results::future_error& e) {
#ifdef TEST_UPSTREAM
        caught = e.code() == std::make_error_code(std::future_errc::broken_promise);
#else
        caught = e.code() == Shipyard::Async::broken_promise;
#endif
    }
    CHECK(caught);
    caught = false;
    try { voidAbandoned.get(); } catch (const results::future_error&) { caught = true; }
    CHECK(caught);
}

struct Shutdown {
    xbox_compat::manual_reset_event entered, release, leaving, returned;
    int completed;
    Shutdown() : completed(0) {}
    static void run(void* arg) {
        Shutdown* self = static_cast<Shutdown*>(arg);
        {
            BS::thread_pool pool(2);
            pool.detach_task([self]() {
                self->entered.set();
                self->release.wait();
                self->completed = 1;
            });
            self->entered.wait();
            self->leaving.set();
        }
        self->returned.set();
    }
};

static void shutdown_joins_running_tasks() {
    Shutdown state;
    xbox_compat::joining_thread owner(&Shutdown::run, &state);
    state.leaving.wait();
    bool early = state.returned.wait_for_ms(30);
    state.release.set();
    CHECK(state.returned.wait_for_ms(5000));
    owner.join();
    CHECK(!early && state.completed == 1);
}

static void repeated_wakeups_and_purge() {
    BS::thread_pool pool(4);
    for (int round = 0; round < 40; ++round) {
        std::vector<results::shared_future<int> > pending;
        for (int i = 0; i < 40; ++i) pending.push_back(pool.submit_task([i]() -> int { return i * 3; }).share());
        pool.wait();
        for (int i = 0; i < 40; ++i) CHECK(pending[i].get() == i * 3);
    }
    pool.pause(); pool.wait();
    results::future<int> purged = pool.submit_task([]() -> int { return 7; });
    pool.purge();
    CHECK(pool.get_tasks_queued() == 0);
    bool caught = false;
    try { purged.get(); } catch (const results::future_error&) { caught = true; }
    CHECK(caught);
    pool.unpause();
}

int main() {
    try {
        resource_shapes_and_actual_workers();
        priorities_pause_and_drain();
        failures_and_paused_abandonment();
        shutdown_joins_running_tasks();
        repeated_wakeups_and_purge();
        std::puts("PASS BS v4.1.0: resource captures/results, native workers, priority, pause/drain, failures, abandoned queue, joined shutdown, 1600 wakeups");
        return 0;
    } catch (const std::exception& e) { std::fprintf(stderr, "FAIL: %s\n", e.what()); return 1; }
}
