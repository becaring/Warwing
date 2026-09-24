#define BS_THREAD_POOL_ENABLE_PRIORITY
#define BS_THREAD_POOL_ENABLE_PAUSE
#include "BS_thread_pool.hpp"

// This file must fail compilation: omitted APIs cannot pretend to succeed.
void unsupported_api(BS::thread_pool& pool) { pool.reset(2); }
