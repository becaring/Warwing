#include "runtime.h"
#include "diagnostics/queue.h"
#include <ppcintrinsics.h>
#include <stdio.h>
#include <stdarg.h>
#include <errno.h>
#include <deque>
#include <new>
#include <stdlib.h>

extern "C" unsigned long __cdecl DbgPrint(const char*, ...);

namespace {
using Shipyard::Diagnostics::Record;
using Shipyard::Diagnostics::Queue;
using Shipyard::Diagnostics::Config;
using Shipyard::Diagnostics::Stats;

const size_t LOG_QUEUE_LIMIT = 1024 * 1024;
const unsigned LOG_LINE_LIMIT = 8192;
struct ConsoleLine { int level; std::string text; };
CRITICAL_SECTION consoleMutex;
volatile LONG consoleState;
std::deque<ConsoleLine>* pendingConsole;
CRITICAL_SECTION fileMutex;
volatile LONG fileState;
FILE* diagnosticLog;
volatile LONG fileErrors;
volatile LONG summaryWritten;

void InitSection(CRITICAL_SECTION& section, volatile LONG& state) {
    if (InterlockedCompareExchange(&state, 1, 0) == 0) {
        InitializeCriticalSection(&section);
        InterlockedExchange(&state, 2);
    } else while (InterlockedCompareExchange(&state, 2, 2) != 2) Sleep(0);
}
void InitConsole() {
    if (InterlockedCompareExchange(&consoleState, 1, 0) == 0) {
        InitializeCriticalSection(&consoleMutex);
        pendingConsole = new std::deque<ConsoleLine>();
        InterlockedExchange(&consoleState, 2);
    } else while (InterlockedCompareExchange(&consoleState, 2, 2) != 2) Sleep(0);
}
void FileError(const char* operation) {
    int error = errno;
    if (InterlockedIncrement(&fileErrors) == 1)
        DbgPrint("SMASH360 diagnostic file %s failed errno=%d; console output retained\n", operation, error);
}
void FlushFile(void*) {
    InitSection(fileMutex, fileState);
    EnterCriticalSection(&fileMutex);
    if (diagnosticLog && fflush(diagnosticLog) != 0) FileError("flush");
    LeaveCriticalSection(&fileMutex);
}
void CloseFile() {
    InitSection(fileMutex, fileState);
    EnterCriticalSection(&fileMutex);
    if (diagnosticLog) {
        if (fclose(diagnosticLog) != 0) FileError("close");
        diagnosticLog = NULL;
    }
    LeaveCriticalSection(&fileMutex);
}
void WriteFileLine(const char* text) {
    InitSection(fileMutex, fileState);
    EnterCriticalSection(&fileMutex);
    if (!diagnosticLog) {
        diagnosticLog = fopen("game:\\smash360.log", "ab");
        if (!diagnosticLog) diagnosticLog = fopen("cache:\\smash360.log", "ab");
    }
    if (!diagnosticLog) FileError("open");
    else if (fprintf(diagnosticLog, "%s\n", text) < 0) FileError("write");
    LeaveCriticalSection(&fileMutex);
}
void EmitLine(int level, const char* text) {
    DbgPrint("SMASH360 %s\n", text);
    WriteFileLine(text);
    ConsoleLine line = {level, text};
    InitConsole();
    EnterCriticalSection(&consoleMutex);
    pendingConsole->push_back(line);
    LeaveCriticalSection(&consoleMutex);
}
void EmitReport(const char* format, ...) {
    char text[2048];
    va_list args; va_start(args, format);
    _vsnprintf_s(text, sizeof(text), _TRUNCATE, format, args);
    va_end(args);
    EmitLine(2, text);
}
void Consume(const Record& record, void*) {
    if (!record.format) { EmitLine(record.level, record.bytes.c_str()); return; }
    LARGE_INTEGER start, end, clock;
    QueryPerformanceFrequency(&clock);
    QueryPerformanceCounter(&start);
    record.format(record.bytes.data(), EmitReport);
    FlushFile(NULL);
    QueryPerformanceCounter(&end);
    const double milliseconds = 1000.0 / clock.QuadPart;
    EmitReport("DIAGNOSTIC report producer_ms=%.3f queue_ms=%.3f worker_ms=%.3f producer_thread=%lu output_thread=%lu",
        record.capture_ticks * milliseconds,
        (start.QuadPart - record.queued_at.QuadPart) * milliseconds,
        (end.QuadPart - start.QuadPart) * milliseconds,
        record.producer, GetCurrentThreadId());
}
void SinkError(void*) {
    DbgPrint("SMASH360 diagnostic sink callback failed; later records retained\n");
}
void BeginRecord(Record& record, void*) {
    if (record.format) {
        record.producer = GetCurrentThreadId();
        QueryPerformanceCounter(&record.queued_at);
    }
}
void Accepted(Record& record, uint32_t captureStart, void*) {
    if (record.format) record.capture_ticks = __mftb32() - captureStart;
}
void WorkerStarted(void*) {
    if (XSetThreadProcessor(GetCurrentThread(), 3) == (DWORD)-1 ||
        !SetThreadPriority(GetCurrentThread(), THREAD_PRIORITY_BELOW_NORMAL))
        DbgPrint("SMASH360 diagnostic worker affinity/priority setup failed\n");
    Smash360_Log("THREAD diagnostics hardware=%lu priority=%d",
        GetCurrentProcessorNumber(), GetThreadPriority(GetCurrentThread()));
}
void WorkerStopped(void*) { CloseFile(); }
Config QueueConfig() {
    Config c = {};
    c.consume = Consume; c.flush = FlushFile; c.sink_error = SinkError;
    c.begin_record = BeginRecord; c.accepted = Accepted;
    c.worker_started = WorkerStarted; c.worker_stopped = WorkerStopped;
    c.byte_limit = LOG_QUEUE_LIMIT; c.line_limit = LOG_LINE_LIMIT;
    c.wake_bytes = 16 * 1024; c.interval_ms = 250;
    return c;
}
Queue* diagnosticQueue;
volatile LONG queueState;
Queue& GetQueue() {
    if (InterlockedCompareExchange(&queueState, 1, 0) == 0) {
        diagnosticQueue = new Queue(QueueConfig());
        InterlockedExchange(&queueState, 2);
    } else while (InterlockedCompareExchange(&queueState, 2, 2) != 2) Sleep(0);
    return *diagnosticQueue;
}
void QueueOrFail(const Record& record, uint32_t captureStart) {
    if (!GetQueue().submit(record, captureStart)) {
        DbgPrint("SMASH360 FAIL diagnostic record enqueue\n");
        exit(1);
    }
}
void LogMessage(int level, const char* format, va_list args) {
    char text[2048];
    _vsnprintf_s(text, sizeof(text), _TRUNCATE, format, args);
    Record record; record.level = level; record.bytes = text;
    QueueOrFail(record, 0);
}
}

void Smash360_QueueDiagnostic(Smash360DiagnosticFormat format,
                              const void* snapshot, size_t size, uint32_t captureStart) {
    if (!format || !snapshot || !size || size >= LOG_QUEUE_LIMIT)
        Smash360_Fatal("invalid diagnostic snapshot", E_INVALIDARG);
    Record record; record.format = format;
    record.bytes.assign(static_cast<const char*>(snapshot), size);
    QueueOrFail(record, captureStart);
}
void Smash360_Log(const char* format, ...) {
    va_list args; va_start(args, format); LogMessage(2, format, args); va_end(args);
}
void Smash360_LogLevel(int level, const char* format, ...) {
    va_list args; va_start(args, format); LogMessage(level, format, args); va_end(args);
}
void Smash360_FlushLogs() { GetQueue().flush(); }
void Smash360_ShutdownDiagnostics() {
    Queue& queue = GetQueue();
    queue.shutdown();
    if (InterlockedCompareExchange(&summaryWritten, 1, 0) == 0) {
        Stats stats = queue.stats();
        char summary[192];
        sprintf_s(summary, "LOG writer stopped accepted=%u processed=%u peak_bytes=%u backpressure=%u file_errors=%u",
            stats.accepted, stats.processed, (unsigned)stats.peak_bytes,
            stats.backpressure, (unsigned)fileErrors);
        WriteFileLine(summary);
        CloseFile();
        DbgPrint("SMASH360 %s\n", summary);
    }
}
void Smash360_DrainConsoleLogs(void (*append)(int, const char*)) {
    std::deque<ConsoleLine> lines;
    InitConsole();
    EnterCriticalSection(&consoleMutex);
    for (unsigned i = 0; i < 8 && !pendingConsole->empty(); ++i) {
        lines.push_back(pendingConsole->front()); pendingConsole->pop_front();
    }
    LeaveCriticalSection(&consoleMutex);
    for (size_t i = 0; i < lines.size(); ++i)
        append(lines[i].level, lines[i].text.c_str());
}
void Smash360_Fatal(const char* operation, HRESULT result) {
    Smash360_LogLevel(5, "FAIL %s hr=%08lx", operation, result);
    Smash360_FlushLogs();
    exit(1);
}
