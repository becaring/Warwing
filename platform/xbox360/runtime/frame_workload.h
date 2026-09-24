#pragma once
// Group measured presented frames by command count, independent of scene or
// character identity. This separates a short busy scene from its transition
// inside the existing five-second report, without adding per-command work.
struct SmashFrameWorkload {
    enum { Count = 32, Width = 1024 };
    struct Band {
        unsigned frames;
        double elapsed, logic, render, present;
    } bands[Count];
    void Add(unsigned commands, double elapsed, double logic, double render, double present) {
        unsigned index=commands/Width;
        if(index>=Count)index=Count-1;
        Band& band=bands[index];
        ++band.frames;band.elapsed+=elapsed;band.logic+=logic;
        band.render+=render;band.present+=present;
    }
    void Reset() {
        for(unsigned i=0;i<Count;++i) {
            bands[i].frames=0;
            bands[i].elapsed=bands[i].logic=bands[i].render=bands[i].present=0;
        }
    }
};
