# Used chrono contracts on XDK

`chrono.h` exposes `xbox_compat::chrono`, without adding symbols to `std`.
Compile `chrono.cpp` once. System-clock ticks are signed 100 ns intervals from
1970-01-01 UTC; native GetSystemTimeAsFileTime ticks are converted from the
1601 epoch. `to_time_t` truncates whole seconds toward zero, including negative
fractions, and `from_time_t` reverses the whole-second conversion.

Steady time comes from QueryPerformanceCounter/Frequency and has nanosecond
representation. Quotient/remainder conversion avoids multiplying the full counter
by one billion. A failed native query throws native_error; frequencies exceeding
the safe remainder multiplication range throw rather than wrap. As with signed
standard chrono arithmetic, durations and intermediate arithmetic must remain
representable. The QPC origin is unspecified and is not a UTC timestamp.

The invariant QPC frequency is cached after successful validation, following
SoH360's `platform.cpp` timing service. This compatibility clock may first run on
any worker, so its cache uses native TLS rather than the XDK compiler's unsafe
shared local-static initialization. Each thread queries frequency once; failed
initialization is retried, and every timestamp still reads the actual counter.
Integer quotient/remainder conversion and error reporting stay intact.

The bounded surface includes duration with integral/floating representation and
positive rational period, duration_cast, exact implicit period conversions,
explicit count construction, mixed-period addition/subtraction/comparison,
zero/min/max, signed count arithmetic, time_point construction and conversion,
time_point/duration arithmetic and comparisons, system/steady clocks, and
nanoseconds through hours aliases. Common representations use the actual SDK
common_type. Integral casts truncate toward zero. Implicit fractional-unit loss
and floating-to-integral duration conversions are rejected.

This does not implement C++20 calendar/timezone clocks, formatting, clock_cast,
chrono literals, floor/ceil/round, general duration scalar multiplication or
division, modulo, or timed synchronization primitives. It is the set consumed by
the current spdlog timestamp/pattern algorithms, plus their stopwatch floating
duration conversion. No clock accuracy or hardware-runtime claim follows from
object compilation.

Run `python tests/logging/run_chrono.py`: identical output against host
std::chrono for signed boundary casts, thirds/fifths, timestamp fractions,
float-duration truncation, and UTC epoch round trips. It also checks monotonic
elapsed time and current UTC against CRT time, then compiles both tests and native
clock implementation to actual XDK objects. Output is confined to
scratch/logging-xdk/chrono-tests.

The same runner also executes the production clock with test-only OS query
substitution on eight concurrent threads: 8000 exact timestamps, one successful
frequency query per thread, invalid frequency retries, and counter failures.
