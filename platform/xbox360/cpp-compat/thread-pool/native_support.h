#ifndef SMASH360_BS_NATIVE_SUPPORT_H
#define SMASH360_BS_NATIVE_SUPPORT_H

#include "future.h"
#include "sources/thread-pool/native_support.h"

namespace xbox_compat {
using Shipyard::Async::invoke_result;
using Shipyard::Async::complete_promise;
using Shipyard::Async::make_thread;
using Shipyard::Async::hardware_concurrency;
}

#endif
