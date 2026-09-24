#include "runtime.h"
#include "io/shader_worker.h"

namespace {
const Shipyard::IO::ShaderWorkerConfig workerConfig={
    "shader-cache",3,Smash360_WriteShaderCacheRecord,Smash360_Log,Smash360_Fatal
};
void ConfigureWorker() {
    if(!Shipyard::IO::ConfigureShaderWorker(&workerConfig))
        Smash360_Fatal("shader worker configuration",E_UNEXPECTED);
}
}
bool Smash360_QueueShaderCacheWrite(const std::string& record,bool truncate,void (*complete)(bool)) {
    ConfigureWorker();
    return Shipyard::IO::QueueShaderRecord(record,truncate,complete);
}
void Smash360_WaitShaderWrites() { ConfigureWorker();Shipyard::IO::WaitShaderWrites(); }
void Smash360_PollShaderWrites() { ConfigureWorker();Shipyard::IO::PollShaderWrites(); }
void Smash360_ShutdownShaderWrites() { ConfigureWorker();Shipyard::IO::ShutdownShaderWrites(); }
