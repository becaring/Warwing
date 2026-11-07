#ifndef SMASH360_RUNTIME_H
#define SMASH360_RUNTIME_H
#include <xtl.h>
#include <stdint.h>
#include <string>

typedef void (*Smash360DiagnosticEmit)(const char* format, ...);
typedef void (*Smash360DiagnosticFormat)(const void* snapshot, Smash360DiagnosticEmit emit);
void Smash360_Log(const char* format, ...);
void Smash360_LogLevel(int level, const char* format, ...);
__declspec(noreturn) void Smash360_Fatal(const char* operation, HRESULT result);
void Smash360_FlushLogs();
void Smash360_QueueDiagnostic(Smash360DiagnosticFormat format, const void* snapshot, size_t size, uint32_t captureStart);
void Smash360_ShutdownDiagnostics();
double Smash360_Time();
bool Smash360_PrepareAppStorage();
void Smash360_CloseAppStorage();
bool Smash360_WriteFile(const char* relative, const void* data, size_t size);
bool Smash360_QueueShaderCacheWrite(const std::string& record, bool truncate, void (*complete)(bool));
bool Smash360_WriteShaderCacheRecord(const std::string& record, bool truncate);
void Smash360_WaitShaderWrites();
void Smash360_PollShaderWrites();
void Smash360_ShutdownShaderWrites();
#endif
