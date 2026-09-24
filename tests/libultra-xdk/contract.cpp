#include "AudioDmaRegistry.h"
#include "libultraship/libultra.h"
#include "libultra/clock.h"
#include <chrono>
#include <cassert>
#include <cstring>
#include <iostream>

int main() {
    unsigned char blobs[10][32];
    for (int i=0;i<10;i++) for (int j=0;j<32;j++) blobs[i][j]=static_cast<unsigned char>(i*32+j);
    AudioDma_Clear();
    assert(AudioDma_Clamp(reinterpret_cast<uintptr_t>(blobs[0])+24,16)==16);
    for (int i=0;i<8;i++) AudioDma_Register(blobs[i],32);
    AudioDma_Register(blobs[8],4); // Registry capacity is exactly eight.
    assert(AudioDma_Clamp(reinterpret_cast<uintptr_t>(blobs[8])+2,16)==16);
    for (int i=0;i<8;i++) {
        assert(AudioDma_Clamp(reinterpret_cast<uintptr_t>(blobs[i])+24,16)==8);
        unsigned char out[18];memset(out,0xA5,sizeof(out));
        assert(osPiStartDma(0,0,0,reinterpret_cast<uintptr_t>(blobs[i])+24,out+1,16,0)==0);
        assert(out[0]==0xA5&&out[17]==0xA5);
        assert(memcmp(out+1,blobs[i]+24,8)==0);
        for(int j=9;j<17;j++) assert(out[j]==0);
    }
    AudioDma_Clear();
    assert(AudioDma_Clamp(reinterpret_cast<uintptr_t>(blobs[0])+24,16)==16);
    typedef std::ratio_divide<std::micro,std::ratio<3000,64> > OriginalPeriod;
    typedef std::chrono::duration<long long,OriginalPeriod> OriginalCycles;
    static_assert(OriginalPeriod::num==1&&OriginalPeriod::den==46875000,"exact N64 cycle ratio");
    for(long long i=-1000000000000LL;i<=1000000000000LL;i+=1234567) {
        assert(std::chrono::duration_cast<OriginalCycles>(std::chrono::nanoseconds(i)).count()==
            Shipyard::Libultra::NanosecondsToCycles(i));
    }
    std::cout << "actual audio DMA registry/copy bounds, eight-slot capacity and N64 clock ratio PASS\n";
}
