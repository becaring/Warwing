#include "services.h"
#include <cstdarg>
#include <cstdio>

void Shipyard_Log(const char* format,...) {
    char buffer[2048];
    va_list args;va_start(args,format);
    _vsnprintf_s(buffer,sizeof(buffer),_TRUNCATE,format,args);
    va_end(args);
    Smash360_Log("%s",buffer);
}
void Shipyard_Fatal(const char* operation,HRESULT result){Smash360_Fatal(operation,result);}
bool Shipyard_WriteFile(const char* relative,const void* bytes,size_t size){
    return Smash360_WriteFile(relative,bytes,size);
}
bool Shipyard_VerifyFast3DReuse(){
    static const char* verify=XboxEnv_Get("SMASH360_VERIFY_NATIVE_REUSE");
    return verify && verify[0]=='1';
}
