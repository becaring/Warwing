#include "future.h"
#include <cstdio>
#include <stdexcept>
#include <string>
#include <vector>

using namespace xbox_compat;
static void check(bool condition, const char *message) {
    if (!condition)
        throw std::runtime_error(message);
}
#define CHECK(x) check(!!(x), "CHECK failed: " #x)

struct Reader {
    shared_future<int> result;
    manual_reset_event entered, done;
    int value;
    Reader() : value(0) {}
    static void run(void *arg) {
        Reader *self = static_cast<Reader *>(arg);
        self->entered.set();
        self->result.wait();
        self->value = self->result.get();
        self->done.set();
    }
};

// Catches early/fabricated completion, a single-consumer event, and lost publication.
static void multiple_readers_block_and_share() {
    promise<int> producer;
    shared_future<int> result = producer.get_future().share();
    Reader readers[8];
    joining_thread workers[8];
    for (int i = 0; i < 8; ++i) {
        readers[i].result = result;
        workers[i] = joining_thread(&Reader::run, &readers[i]);
    }
    for (int i = 0; i < 8; ++i)
        readers[i].entered.wait();
    bool returnedEarly = readers[0].done.wait_for_ms(30);
    producer.set_value(73);
    for (int i = 0; i < 8; ++i) {
        CHECK(readers[i].done.wait_for_ms(5000));
        workers[i].join();
        CHECK(readers[i].value == 73);
        CHECK(&readers[i].result.get() == &result.get());
    }
    CHECK(!returnedEarly);
    CHECK(result.get() == 73);
}

struct ExpectedFailure : std::runtime_error {
    int tag;
    ExpectedFailure() : std::runtime_error("resource failure"), tag(91) {}
};
static std::exception_ptr failure() {
    try {
        throw ExpectedFailure();
    } catch (...) {
        return std::current_exception();
    }
}

// Catches swallowed/sliced exceptions and get() consuming a shared reader's result.
static void exceptions_and_invalid_states() {
    promise<int> producer;
    shared_future<int> a = producer.get_future().share(), b = a;
    producer.set_exception(failure());
    for (int i = 0; i < 2; ++i) {
        bool caught = false;
        try {
            (i ? a : b).get();
        } catch (const ExpectedFailure &e) {
            caught = e.tag == 91;
        }
        CHECK(caught);
    }
    bool caught = false;
    try {
        producer.set_value(4);
    } catch (const future_error &e) {
        caught = e.code() == promise_already_satisfied;
    }
    CHECK(caught);
    caught = false;
    try {
        producer.get_future();
    } catch (const future_error &e) {
        caught = e.code() == future_already_retrieved;
    }
    CHECK(caught);
    future<int> empty;
    caught = false;
    try {
        empty.get();
    } catch (const future_error &e) {
        caught = e.code() == no_state;
    }
    CHECK(caught);
    promise<int> exceptional;
    future<int> consumed = exceptional.get_future();
    exceptional.set_exception(failure());
    try {
        consumed.get();
    } catch (const ExpectedFailure &) {
    }
    CHECK(!consumed.valid());
    promise<int> nullException;
    caught = false;
    try {
        nullException.set_exception(std::exception_ptr());
    } catch (const std::invalid_argument &) {
        caught = true;
    }
    CHECK(caught);
    nullException.set_value(6);
    CHECK(nullException.get_future().get() == 6);
}

struct BrokenReader {
    shared_future<int> result;
    manual_reset_event entered, done;
    bool caught;
    BrokenReader() : caught(false) {}
    static void run(void *arg) {
        BrokenReader *self = static_cast<BrokenReader *>(arg);
        self->entered.set();
        try {
            self->result.get();
        } catch (const future_error &e) {
            self->caught = e.code() == broken_promise;
        }
        self->done.set();
    }
};

// Catches abandonment that fails to wake blocked readers and move assignment leaks.
static void abandonment_and_move_ownership() {
    BrokenReader reader;
    joining_thread worker;
    {
        promise<int> producer;
        reader.result = producer.get_future().share();
        worker = joining_thread(&BrokenReader::run, &reader);
        reader.entered.wait();
    }
    CHECK(reader.done.wait_for_ms(5000));
    worker.join();
    CHECK(reader.caught);
    promise<int> first, second;
    future<int> abandoned = first.get_future();
    future<int> delivered = second.get_future();
    first = std::move(second);
    first.set_value(28);
    CHECK(delivered.get() == 28);
    CHECK(!delivered.valid());
    bool caught = false;
    try {
        abandoned.get();
    } catch (const future_error &e) {
        caught = e.code() == broken_promise;
    }
    CHECK(caught);
    caught = false;
    try {
        second.set_value(2);
    } catch (const future_error &e) {
        caught = e.code() == no_state;
    }
    CHECK(caught);
    promise<int> original;
    future<int> old = original.get_future();
    future<int> moved(std::move(old));
    CHECK(!old.valid());
    shared_future<int> shared(std::move(moved));
    CHECK(!moved.valid());
    shared_future<int> transferred(std::move(shared));
    CHECK(!shared.valid());
    promise<int> owner(std::move(original));
    owner.set_value(39);
    CHECK(transferred.get() == 39);
}

struct Tracked {
    int *destroyed;
    explicit Tracked(int *count) : destroyed(count) {}
    ~Tracked() { ++*destroyed; }
};

// Catches early value destruction and shared state reference leaks.
static void value_lifetime_and_move_only_result() {
    int destroyed = 0;
    shared_future<std::shared_ptr<Tracked>> survivor;
    {
        promise<std::shared_ptr<Tracked>> producer;
        survivor = producer.get_future().share();
        producer.set_value(std::shared_ptr<Tracked>(new Tracked(&destroyed)));
    }
    {
        shared_future<std::shared_ptr<Tracked>> copy = survivor;
        survivor = shared_future<std::shared_ptr<Tracked>>();
        CHECK(destroyed == 0);
        CHECK(copy.get()->destroyed == &destroyed);
    }
    CHECK(destroyed == 1);
    promise<std::unique_ptr<int>> producer;
    future<std::unique_ptr<int>> result = producer.get_future();
    producer.set_value(std::unique_ptr<int>(new int(18)));
    std::unique_ptr<int> value = result.get();
    CHECK(*value == 18 && !result.valid());
}

struct Incrementer {
    mutex *gate;
    int *count;
    static void run(void *arg) {
        Incrementer *self = static_cast<Incrementer *>(arg);
        for (int i = 0; i < 20000; ++i) {
            lock_guard<mutex> lock(*self->gate);
            ++*self->count;
        }
    }
};

// Catches ineffective mutual exclusion and a destructor that detaches its worker.
static void mutual_exclusion_and_joining_shutdown() {
    mutex gate;
    int count = 0;
    Incrementer work = {&gate, &count};
    {
        joining_thread a(&Incrementer::run, &work);
        joining_thread b(&Incrementer::run, &work);
        joining_thread c(std::move(b));
        CHECK(!b.joinable() && c.joinable());
    }
    CHECK(count == 40000);
    CHECK(gate.try_lock());
    gate.unlock();
    manual_reset_event event;
    CHECK(!event.wait_for_ms(0));
    event.set();
    CHECK(event.wait_for_ms(0));
    CHECK(event.wait_for_ms(0));
    event.reset();
    CHECK(!event.wait_for_ms(0));
}

struct ShutdownOwner {
    manual_reset_event workerEntered, releaseWorker, leavingScope, returned;
    static void blocked(void *arg) {
        ShutdownOwner *self = static_cast<ShutdownOwner *>(arg);
        self->workerEntered.set();
        self->releaseWorker.wait();
    }
    static void run(void *arg) {
        ShutdownOwner *self = static_cast<ShutdownOwner *>(arg);
        {
            joining_thread worker(&ShutdownOwner::blocked, self);
            self->workerEntered.wait();
            self->leavingScope.set();
        }
        self->returned.set();
    }
};

// Catches detach-on-destruction even when an uncontended worker would finish quickly.
static void destructor_waits_for_blocked_worker() {
    ShutdownOwner owner;
    joining_thread controller(&ShutdownOwner::run, &owner);
    owner.leavingScope.wait();
    bool returnedEarly = owner.returned.wait_for_ms(30);
    owner.releaseWorker.set();
    CHECK(owner.returned.wait_for_ms(5000));
    controller.join();
    CHECK(!returnedEarly);
}

struct RacingProducer {
    promise<int> *producer;
    manual_reset_event *start;
    bool won;
    RacingProducer() : producer(0), start(0), won(false) {}
    static void run(void *arg) {
        RacingProducer *self = static_cast<RacingProducer *>(arg);
        self->start->wait();
        try {
            self->producer->set_value(55);
            self->won = true;
        } catch (const future_error &e) {
            if (e.code() != promise_already_satisfied)
                throw;
        }
    }
};

// Catches non-atomic ready transitions and get_future racing with completion.
static void competing_producers() {
    for (int i = 0; i < 100; ++i) {
        promise<int> producer;
        manual_reset_event start;
        RacingProducer a, b;
        a.producer = b.producer = &producer;
        a.start = b.start = &start;
        joining_thread ta(&RacingProducer::run, &a), tb(&RacingProducer::run, &b);
        start.set();
        future<int> result = producer.get_future();
        CHECK(result.get() == 55);
        ta.join();
        tb.join();
        CHECK(a.won != b.won);
    }
}

struct ExceptionalProducer {
    promise<int> *producer;
    static void run(void *arg) {
        ExceptionalProducer *self = static_cast<ExceptionalProducer *>(arg);
        try {
            throw ExpectedFailure();
        } catch (...) {
            self->producer->set_exception(std::current_exception());
        }
    }
};

// Catches transport tied to the producer's stack or thread lifetime.
static void exception_survives_worker_exit() {
    shared_future<int> result;
    {
        promise<int> producer;
        result = producer.get_future().share();
        ExceptionalProducer work = {&producer};
        joining_thread worker(&ExceptionalProducer::run, &work);
        worker.join();
    }
    for (int i = 0; i < 2; ++i) {
        bool caught = false;
        try {
            result.get();
        } catch (const ExpectedFailure &e) {
            caught = e.tag == 91;
        }
        CHECK(caught);
    }
}

struct ThrowingValue {
    bool fail;
    explicit ThrowingValue(bool shouldFail) : fail(shouldFail) {}
    ThrowingValue(const ThrowingValue &other) : fail(other.fail) {
        if (fail)
            throw ExpectedFailure();
    }
};

// Catches publishing ready before construction succeeds or making failure permanent.
static void failed_construction_can_be_retried() {
    promise<ThrowingValue> producer;
    shared_future<ThrowingValue> result = producer.get_future().share();
    ThrowingValue bad(true), good(false);
    bool caught = false;
    try {
        producer.set_value(bad);
    } catch (const ExpectedFailure &) {
        caught = true;
    }
    CHECK(caught);
    producer.set_value(good);
    CHECK(!result.get().fail);
    promise<std::shared_ptr<std::vector<std::shared_ptr<Tracked>>>> directory;
    std::shared_ptr<std::vector<std::shared_ptr<Tracked>>> resources(new std::vector<std::shared_ptr<Tracked>>());
    directory.set_value(resources);
    CHECK(directory.get_future().share().get() == resources);
}

struct ConditionReaders {
    mutex gate;
    condition_variable changed;
    manual_reset_event allEntered;
    int entered, completed;
    bool ready;
    ConditionReaders() : entered(0), completed(0), ready(false) {}
    static void run(void *arg) {
        ConditionReaders *self = static_cast<ConditionReaders *>(arg);
        unique_lock<mutex> lock(self->gate);
        if (++self->entered == 4)
            self->allEntered.set();
        self->changed.wait(lock, [self]() -> bool { return self->ready; });
        ++self->completed;
    }
};

// Catches dropped registrations, incorrect broadcast, and ignored predicates.
static void condition_variable_broadcast() {
    ConditionReaders state;
    joining_thread readers[4];
    for (int i = 0; i < 4; ++i)
        readers[i] = joining_thread(&ConditionReaders::run, &state);
    state.allEntered.wait();
    {
        unique_lock<mutex> lock(state.gate);
        state.changed.notify_all(); // Predicate remains false; nobody may complete.
    }
    {
        unique_lock<mutex> lock(state.gate);
        CHECK(state.completed == 0);
        state.ready = true;
        state.changed.notify_all();
    }
    for (int i = 0; i < 4; ++i)
        readers[i].join();
    CHECK(state.completed == 4);
}

// Catches void completion consuming shared readers and missing move abandonment.
static void void_result_ownership() {
    promise<void> original;
    future<void> source = original.get_future();
    shared_future<void> first = source.share();
    CHECK(!source.valid());
    shared_future<void> second = first;
    promise<void> moved(std::move(original));
    moved.set_value();
    first.get();
    second.get();
    first.get();
    promise<void> discarded;
    future<void> broken = discarded.get_future();
    discarded = std::move(moved);
    bool caught = false;
    try {
        broken.get();
    } catch (const future_error &e) {
        caught = e.code() == broken_promise;
    }
    CHECK(caught && !broken.valid());
    caught = false;
    try {
        moved.set_value();
    } catch (const future_error &e) {
        caught = e.code() == no_state;
    }
    CHECK(caught);
}

int main() {
    try {
        multiple_readers_block_and_share();
        exceptions_and_invalid_states();
        abandonment_and_move_ownership();
        value_lifetime_and_move_only_result();
        mutual_exclusion_and_joining_shutdown();
        destructor_waits_for_blocked_worker();
        competing_producers();
        exception_survives_worker_exit();
        failed_construction_can_be_retried();
        condition_variable_broadcast();
        void_result_ownership();
        std::puts("PASS async compatibility: blocking, publication, multi-reader lifetime, exceptions, broken promise, "
                  "move ownership, mutex, joining shutdown, races");
        return 0;
    } catch (const std::exception &e) {
        std::fprintf(stderr, "FAIL: %s\n", e.what());
        return 1;
    }
}
