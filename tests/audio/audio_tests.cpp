#include "ship/audio/AudioPlayer.h"
#include "PcmBufferPool.h"
#include "PcmLayout.h"
#include <cstdio>
#include <stdexcept>
#include <vector>
#include <cstring>

static void check(bool condition, const char* message) { if (!condition) throw std::runtime_error(message); }
#define CHECK(x) check(!!(x), #x)
void Smash360_Log(const char*, ...) {}

class CapturePlayer : public Ship::AudioPlayer {
public:
    explicit CapturePlayer(Ship::AudioSettings settings) : AudioPlayer(settings), opened(0), closed(0) {}
    int opened, closed;
    std::vector<uint8_t> bytes;
    int32_t Buffered() { return static_cast<int32_t>(bytes.size() / (GetNumOutputChannels() * sizeof(int16_t))); }
protected:
    bool DoInit() { ++opened; return true; }
    void DoClose() { ++closed; }
    void DoPlay(const uint8_t* buffer, size_t length) { bytes.assign(buffer, buffer + length); }
};

// Exercise the real AudioPlayer + SoundMatrixDecoder without a synthetic native voice.
static void player_and_decoder_contract(const char* outputPath) {
    Ship::AudioSettings settings;
    settings.SampleRate = 32000;
    settings.SampleLength = 1024;
    settings.DesiredBuffered = 2480;
    CapturePlayer player(settings);
    CHECK(player.Init());
    CHECK(player.GetSampleRate() == 32000 && player.GetNumOutputChannels() == 2);
    std::vector<int16_t> stereo(2048);
    for (size_t i = 0; i < stereo.size(); ++i) stereo[i] = static_cast<int16_t>(static_cast<int>((i * 97) % 30001) - 15000);
    player.Play(reinterpret_cast<const uint8_t*>(&stereo[0]), stereo.size() * sizeof(int16_t));
    CHECK(player.Buffered() == 1024);
    CHECK(std::memcmp(&player.bytes[0], &stereo[0], player.bytes.size()) == 0);
    CHECK(player.SetAudioChannels(audioMatrix51));
    CHECK(player.GetNumOutputChannels() == 6 && player.closed == 1 && player.opened == 2);
    player.Play(reinterpret_cast<const uint8_t*>(&stereo[0]), stereo.size() * sizeof(int16_t));
    CHECK(player.bytes.size() == 1024 * 6 * sizeof(int16_t));
    const int16_t* decoded = reinterpret_cast<const int16_t*>(&player.bytes[0]);
    CHECK(decoded[0] == stereo[0] / 2 && decoded[1] == stereo[1] / 2);
    bool nonzero = false;
    for (size_t i = 0; i < player.bytes.size(); ++i) if (player.bytes[i]) nonzero = true;
    CHECK(nonzero);
    FILE* snapshot = NULL;
    CHECK(fopen_s(&snapshot, outputPath, "wb") == 0 && snapshot);
    CHECK(std::fwrite(&player.bytes[0], 1, player.bytes.size(), snapshot) == player.bytes.size());
    std::fclose(snapshot);
    std::vector<uint8_t> firstDecode = player.bytes;
    CHECK(player.SetAudioChannels(audioStereo));
    CHECK(player.GetNumOutputChannels() == 2);
    CHECK(player.SetAudioChannels(audioMatrix51));
    player.Play(reinterpret_cast<const uint8_t*>(&stereo[0]), stereo.size() * sizeof(int16_t));
    CHECK(player.bytes == firstDecode); // Switching releases the old decoder state.
    CHECK(player.SetAudioChannels(audioRaw51));
    player.Play(&firstDecode[0], firstDecode.size());
    CHECK(player.bytes == firstDecode && player.Buffered() == 1024);
}

struct ReleaseOnWorker {
    Smash360::PcmBufferPool* pool;
    Smash360::PcmBufferPool::Block* block;
    HANDLE allow;
    static DWORD WINAPI Run(void* argument) {
        ReleaseOnWorker* self = static_cast<ReleaseOnWorker*>(argument);
        if (WaitForSingleObject(self->allow, 5000) != WAIT_OBJECT_0) return 1;
        self->pool->Release(self->block);
        return 0;
    }
};

static void persistent_buffer_ownership() {
    Smash360::PcmBufferPool pool;
    CHECK(pool.Initialize(4096));
    Smash360::PcmBufferPool::Block* blocks[Smash360::PcmBufferPool::BlockCount];
    for (unsigned i = 0; i < Smash360::PcmBufferPool::BlockCount; ++i) {
        blocks[i] = pool.TryAcquire();
        CHECK(blocks[i] != NULL);
        CHECK((reinterpret_cast<size_t>(blocks[i]->samples) & 15) == 0);
        std::memset(blocks[i]->samples, static_cast<int>(i + 1), 4096);
    }
    CHECK(pool.TryAcquire() == NULL);
    CHECK(!pool.WaitAvailable(20));
    for (unsigned i = 0; i < Smash360::PcmBufferPool::BlockCount; ++i) {
        CHECK(blocks[i]->samples[0] == i + 1 && blocks[i]->samples[4095] == i + 1);
    }
    ReleaseOnWorker release = { &pool, blocks[3], CreateEvent(NULL, TRUE, FALSE, NULL) };
    CHECK(release.allow != NULL);
    HANDLE callback = CreateThread(NULL, 0, &ReleaseOnWorker::Run, &release, 0, NULL);
    CHECK(callback != NULL);
    CHECK(SetEvent(release.allow) != FALSE);
    CHECK(pool.WaitAvailable(5000));
    CHECK(WaitForSingleObject(callback, 5000) == WAIT_OBJECT_0);
    DWORD status = 1;
    CHECK(GetExitCodeThread(callback, &status) != FALSE && status == 0);
    CloseHandle(callback); CloseHandle(release.allow);
    CHECK(pool.TryAcquire() == blocks[3]);
    for (unsigned i = 0; i < Smash360::PcmBufferPool::BlockCount; ++i) pool.Release(blocks[i]);
    pool.Close();
    CHECK(pool.Initialize(12288));
    CHECK(pool.CapacityBytes() == 12288);
    pool.Close();
}

static void native_settings_contract() {
    Smash360::PcmLayout layout;
    CHECK(Smash360::ComputePcmLayout(32000, 2, audioStereo, 1024, 2480, layout));
    CHECK(layout.sampleRate == 32000 && layout.frameBytes == 4 && layout.blockFrames == 1024 && layout.capacityFrames == 8192);
    CHECK(Smash360::ComputePcmLayout(32000, 6, audioMatrix51, 1024, 2480, layout));
    CHECK(layout.frameBytes == 12 && layout.channels == 6);
    CHECK(Smash360::ComputePcmLayout(48000, 6, audioMatrix51, 1024, 50000, layout));
    CHECK(layout.sampleRate == 48000 && layout.blockFrames == 6250 && layout.capacityFrames == 50000);
    CHECK(!Smash360::ComputePcmLayout(32000, 6, audioRaw51, 1024, 2480, layout));
    CHECK(ShipyardAudio::ComputePcmLayout(32000, 6, audioRaw51, 1024, 2480, layout));
    CHECK(!Smash360::ComputePcmLayout(32000, 2, audioMatrix51, 1024, 2480, layout));
    CHECK(!Smash360::ComputePcmLayout(32000, 2, audioStereo, 0, 2480, layout));
    CHECK(!Smash360::ComputePcmLayout(32000, 2, audioStereo, 1024, -1, layout));
    CHECK(!Smash360::ComputePcmLayout(32000, 2, audioStereo, 1024, 131073, layout));
    CHECK(!Smash360::ComputePcmLayout(0, 2, audioStereo, 1024, 2480, layout));
}

int main(int argc, char** argv) {
    try {
        CHECK(argc == 2);
        player_and_decoder_contract(argv[1]);
        persistent_buffer_ownership();
        native_settings_contract();
        std::puts("PASS current AudioPlayer/decoder contract and persistent native PCM block ownership");
        return 0;
    } catch (const std::exception& e) { std::fprintf(stderr, "FAIL: %s\n", e.what()); return 1; }
}
