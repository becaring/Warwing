#ifndef SMASH360_ASYNC_NATIVE_H
#define SMASH360_ASYNC_NATIVE_H

#include "sources/async/native.h"

namespace xbox_compat {
using Shipyard::Async::native_error;
using Shipyard::Async::mutex;
using Shipyard::Async::lock_guard;
using Shipyard::Async::unique_lock;
using Shipyard::Async::manual_reset_event;
using Shipyard::Async::condition_variable;
using Shipyard::Async::joining_thread;
}

#endif
