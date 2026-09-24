// Exercises the extracted production functions with a bounded reloc registry.
// BE host-policy execution validates data/side effects, not PPC machine speed.
static void runtimeFixupCases() {
    uint32_t words[32], before[32];
    for (unsigned i=0;i<32;++i) words[i]=0x10203040u+i;
    memcpy(before,words,sizeof(words));
    testRelocBase=(uintptr_t)words; testRelocSize=sizeof(words);
    portResetStructFixups(); testRangeQueries=0;
    portRelocFixupTextureAtRuntime(words,6); // Rounded palette extent.
    portRelocFixupTextureAtRuntime(words+1,12); // Overlapping load.
    portRelocFixupTextureAtRuntime(words,16); // Repeated load.
    if(POLICY_BE) {
        portRelocFixupVertexAtRuntime(words,2);
        check(!memcmp(words,before,sizeof(words)),"BE runtime fixups preserve all bytes");
        check(testRangeQueries==0,"BE native resources require no runtime endian range scan");
        check(sTexFixupWords.empty() && sTexFixupExtent.empty() && sStructU16Fixups.empty(),
              "BE runtime identity repair must not allocate conversion bookkeeping");
        // Each explicit diagnostics mode retains the original path.
        for(unsigned mode=0;mode<3;++mode) {
            portResetStructFixups(); testRangeQueries=0;
            testAudit=mode==0; testTexLog=mode==1; testTexDump=mode==2;
            sChainSlotAddrs.insert((uintptr_t)(words+3)); words[3]=123;
            testBuffer=words+20; // Live token clamps diagnostic conversion.
            portRelocFixupTextureAtRuntime(words,32);
            check(testRangeQueries>0 && sTexFixupWords.size()==3,
                  "diagnostic path retains live-chain clamping and tracking");
            check(words[3]==123,"live token preserved");
            portRelocFixupVertexAtRuntime(words+8,2);
            check(sStructU16Fixups.count((uintptr_t)(words+8))==1,
                  "diagnostic vertex tracking remains available");
            words[3]=before[3];
            check(!memcmp(words,before,sizeof(words)),"BE diagnostics preserve asset bytes");
        }
        testAudit=testTexLog=testTexDump=false;
    } else {
        for(unsigned i=0;i<32;++i)
            check(words[i]==(i<4?smash360UndoLEWordSwap(before[i]):before[i]),
                  "LE overlapping runtime repairs convert each word exactly once");
        portResetStructFixups(); memcpy(words,before,sizeof(words));
        portRelocFixupVertexAtRuntime(words,2);
        portRelocFixupVertexAtRuntime(words+4,1);
        for(unsigned i=0;i<32;++i)
            check(words[i]==(i>=8?before[i]:(i%4==3?smash360UndoLEWordSwap(before[i]):smash360UndoLEHalfSwap(before[i]))),
                  "LE vertex overlapping loads keep native fields and color byte order");
    }
    portResetStructFixups(); testRelocBase=0; testRelocSize=0; testBuffer=NULL;
}
