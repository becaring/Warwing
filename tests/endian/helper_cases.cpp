static void dimensions(unsigned char *sprite,unsigned char *bitmap,int width,int height,int siz) {
    memset(sprite,0,68); memset(bitmap,0,16);
    int16_t n=1,w=(int16_t)width,h=(int16_t)height; uint32_t token=123;
    memcpy(sprite+0x28,&n,2); sprite[0x31]=(unsigned char)siz;
    memcpy(bitmap+2,&w,2); memcpy(bitmap+8,&token,4); memcpy(bitmap+12,&h,2);
}
int main() { try {
    check(SMASH360_HOST_BIG_ENDIAN==POLICY_BE,"host policy selection");
    runtimeFixupCases();
    for(unsigned sequence=0;sequence<47;++sequence) {
        u32 words[18];
        for(unsigned j=0;j<17;++j) {
            const u32 v=sequenceHeaders[sequence][j];
            // Model the native scalar load from the archive's unchanged BE bytes.
            words[j]=POLICY_BE?v:((v>>24)|((v>>8)&0xff00)|((v<<8)&0xff0000)|(v<<24));
        }
        words[17]=0x12345678;
        sequenceHeader(words);
        for(unsigned j=0;j<17;++j)check(words[j]==sequenceHeaders[sequence][j],"all real SBK track offsets/division must be native values");
        check(words[17]==0x12345678,"sequence event byte stream must remain untouched");
    }
    check(BITFIELD_SEXT8(-1)==-1 && BITFIELD_SEXT8(255)==-1,"signed and unsigned 8-bit fields extend identically");
    check(BITFIELD_SEXT10(-512)==-512 && BITFIELD_SEXT10(512)==-512,"signed and unsigned 10-bit fields extend identically");
    check(BITFIELD_SEXT(-1,31)==-1,"31-bit negative field");
    unsigned char envelope[16]; audioEnvelope(fgm+4,envelope);
    const unsigned char envelopeBE[]={7,12,0,0,0x42,0xc8,0,0,0x43,0x3e,0,0,0xc3,0x48,0,0};
    const unsigned char envelopeLE[]={7,12,0,0,0,0,0xc8,0x42,0,0,0x3e,0x43,0,0,0x48,0xc3};
    check(!memcmp(envelope,POLICY_BE?envelopeBE:envelopeLE,16),"actual audio envelope loop preserves fields and three float representations");
    for(unsigned force=0;force<2;force++) for(unsigned id=0;id<2;id++)
        check(figatree(force!=0,id)==(!POLICY_BE && (force || id)),"figatree range must never be halfswapped/registered on BE");
    unsigned char floatbytes[4];
    smash360CopyBEFloatBytes(floatbytes,fgm+8);
    const unsigned char wantBE[]={0x42,0xc8,0,0},wantLE[]={0,0,0xc8,0x42};
    check(!memcmp(floatbytes,POLICY_BE?wantBE:wantLE,4),"actual fgm float 100.0 bytes");
    f32 particleFloat; u8 *end=lbParticleReadFloatBigEnd(fgm+8,&particleFloat);
    check(end==fgm+12 && !memcmp(&particleFloat,POLICY_BE?wantBE:wantLE,4),"particle bytecode float bytes and cursor");
    unsigned char count[4]; memcpy(count,particle,4); bswap32At(count,0);
    const unsigned char countBE[]={0,0,0,119},countLE[]={119,0,0,0};
    check(!memcmp(count,POLICY_BE?countBE:countLE,4),"actual common particle count bytes");
    unsigned char pair[]={0x12,0x34}; bswap16At(pair,0);
    check(pair[0]==(POLICY_BE?0x12:0x34),"particle halfword conversion");
    uint32_t word=0x11223344;
    check(smash360UndoLEWordSwap(word)==(POLICY_BE?0x11223344u:0x44332211u),"pass-one repair policy");
    check(rotate16(word)==(POLICY_BE?0x11223344u:0x33441122u),"halfword repair policy");
    unsigned char container[]={1,2,3,4,5,6,7,8}; const unsigned char fixedLE[]={4,3,2,1,8,7};
    check(!memcmp(portFixupFTTexturePartContainer(container),POLICY_BE?container:fixedLE,6),"container non-destructive snapshot");
    check(container[0]==1 && container[7]==8,"container source/token bytes unchanged");
    if(POLICY_BE) {
        uint32_t vertices[]={0x01020304,0x05060708,0x09101112,0x13141516}, before[4]; memcpy(before,vertices,16);
        apply_fixup_vertex(vertices,4); apply_fixup_tex_u16(vertices,4);
        portFixupStructU16(vertices,0,4); portResetStructFixups(); portFixupStructU32(vertices,0,4);
        fixup_u16_u8u8(vertices); check(!memcmp(before,vertices,16),"BE vertex/struct/palette data preserved");
        unsigned char sprite[68],bitmap[16],pixels[128],linear[128]; testBuffer=pixels;
        for(int siz=0;siz<=3;siz++) {
            portResetStructFixups(); int bpp=4<<siz, rowBytes=16*bpp/8, total=2*rowBytes;
            dimensions(sprite,bitmap,16,2,siz); for(int i=0;i<total;i++) pixels[i]=(unsigned char)i;
            memcpy(linear,pixels,total);
            testRelocBase=(uintptr_t)pixels; testRelocSize=total;
            portRelocFixupTextureAtRuntime(pixels,total);
            portRelocFixupVertexAtRuntime(pixels,1);
            portFixupSpriteBitmapData(sprite,bitmap);
            int half=(siz==3)?8:4;
            check(!memcmp(pixels,linear,rowBytes),"even texture row untouched");
            for(int i=0;i<rowBytes;i++) check(pixels[rowBytes+i]==linear[rowBytes+(i^half)],"odd row deswizzle including RGBA32");
            unsigned char once[128]; memcpy(once,pixels,total); portFixupSpriteBitmapData(sprite,bitmap);
            check(!memcmp(once,pixels,total),"deswizzle idempotence");
            portEvictStructFixupsInRange(pixels,total); memcpy(pixels,linear,total); portFixupSpriteBitmapData(sprite,bitmap);
            check(!memcmp(once,pixels,total),"heap reuse re-enables deswizzle");
            portResetStructFixups(); memcpy(pixels,linear,total); void *buffers[]={pixels};
            portMarkSyntheticSprite(sprite,bitmap,1,buffers); portFixupSpriteBitmapData(sprite,bitmap);
            check(!memcmp(linear,pixels,total),"synthetic linear sprites remain linear");
        }
        portResetStructFixups(); dimensions(sprite,bitmap,16,2,4);
        for(int i=0;i<16;i++) pixels[i]=(unsigned char)i;
        portFixupSpriteBitmapData(sprite,bitmap); for(int i=0;i<16;i++) check(pixels[i]==i,"4c waits for decode");
        portDeswizzleDecodedSprite4c(sprite,bitmap);
        const unsigned char decoded[]={0,1,2,3,4,5,6,7,12,13,14,15,8,9,10,11};
        check(!memcmp(pixels,decoded,16),"decoded 4c odd-row layout");
        portDeswizzleDecodedSprite4c(sprite,bitmap); check(!memcmp(pixels,decoded,16),"decoded 4c idempotence");
        testRelocBase=0; testRelocSize=0;
    }
    printf("PASS actual overlay helpers: %s; host byte/layout policy test only\n",POLICY_BE?"BE":"LE"); return 0;
} catch(const std::exception& e) { fprintf(stderr,"FAIL: %s\n",e.what()); return 1; } }
