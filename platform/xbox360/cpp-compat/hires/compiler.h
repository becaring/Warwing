#ifndef SMASH360_HIRES_COMPILER_H
#define SMASH360_HIRES_COMPILER_H
#include "controllers/compiler.h"
#include "atomic/atomic.h"
#include "thread-pool/native_support.h"
#include "xbox_compat/optional.h"
#include <cstdio>
namespace Smash360HiRes {
template<class Header> void EncodeDumpHeader(unsigned char* bytes,const Header& hdr) {
    const uint32_t fields[7]={hdr.magic,hdr.version,hdr.width,hdr.height,hdr.bpl,hdr.texelBytes,hdr.paletteBytes};
    for(unsigned i=0;i<7;++i)for(unsigned j=0;j<4;++j)bytes[i*4+j]=static_cast<unsigned char>(fields[i]>>(j*8));
    bytes[28]=hdr.fmt;bytes[29]=hdr.siz;
    for(unsigned i=0;i<6;++i)bytes[30+i]=hdr.pad[i];
}
template<class Header> size_t WriteDumpHeader(FILE* file,const Header& hdr) {
    unsigned char bytes[36];EncodeDumpHeader(bytes,hdr);return std::fwrite(bytes,sizeof(bytes),1,file);
}
}
#endif
