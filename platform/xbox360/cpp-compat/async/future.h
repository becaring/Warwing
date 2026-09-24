#ifndef SMASH360_ASYNC_FUTURE_H
#define SMASH360_ASYNC_FUTURE_H

#include "native.h"
#include "sources/async/future.h"

namespace xbox_compat {
using Shipyard::Async::future_errc;
using Shipyard::Async::broken_promise;
using Shipyard::Async::future_already_retrieved;
using Shipyard::Async::promise_already_satisfied;
using Shipyard::Async::no_state;
using Shipyard::Async::future_error;
using Shipyard::Async::promise;
using Shipyard::Async::future;
using Shipyard::Async::shared_future;
}

#endif
