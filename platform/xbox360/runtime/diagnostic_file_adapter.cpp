#include "runtime.h"
#include "storage/atomic_file.h"
#include "async/native.h"
#include <stdexcept>

bool Smash360_WriteFile(const char* relative,const void* data,size_t size) {
    try {
        Shipyard::Storage::WriteAtomicRelativeFile("game:\\",relative,data,size);
        return true;
    } catch(const Shipyard::Async::native_error& error) {
        Smash360_Log("diagnostic %s error=%lu",error.what(),error.native_code());
    } catch(const std::exception&) {
    }
    return false;
}
