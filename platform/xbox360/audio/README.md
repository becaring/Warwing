# Current AudioPlayer over native XAudio2

`XAudio2AudioPlayer` derives from the pinned `Ship::AudioPlayer`. Its actual base
class still owns and calls the actual `SoundMatrixDecoder`. The game mixer,
BattleShip's output filter, its 32000 Hz setting in `port.cpp`, and all PCM
generation remain upstream-owned and unchanged.

## Native contract

The backend implements `DoInit`, `DoClose`, `DoPlay`, and `Buffered`. It reads
`GetSampleRate`, `GetNumOutputChannels`, `GetSampleLength`, and
`GetDesiredBuffered`. Source data is native-endian signed 16-bit PCM. It is copied
without swapping or resampling by this adapter; XAudio2 performs any device-rate
conversion. `Buffered` counts sample frames, dividing submitted bytes by the
actual channel count times two, then subtracting XAudio2's `SamplesPlayed`.

Stereo uses a two-channel source format. Matrix 5.1 uses the **current upstream
decoder** and a six-channel `WAVEFORMATEXTENSIBLE` source mask in the decoder's
order: FL, FR, C, LFE, SL, SR. Output creation failure returns false and is logged;
it never silently changes the channel count.

Raw 5.1 is explicitly rejected by this BattleShip backend: the game supplies
stereo PCM, whereas upstream's raw mode requires already-interleaved six-channel
input. Treating the game stream as raw 5.1 would misinterpret its samples. The
base class's raw pass-through remains unchanged and is tested separately; this
backend accepts stereo and decoded matrix 5.1 only.

`PcmLayout` validates sample rate against the XAudio2 1000–200000 Hz range,
channel/mode consistency, positive sample length no greater than 16384 frames,
and a desired reserve of 0–131072 frames. The native compile asserts those rate
bounds match the installed SDK. The real default BattleShip request is 32000 Hz,
1024 sample length, 2480 desired frames; no donor 44100 Hz policy is used by the
sink. Upstream's `AudioSettings` default of 44100 remains unchanged, and BattleShip
continues to override it normally.

## Buffer and callback ownership

Eight persistent 16-byte-aligned blocks follow the donor's interlocked busy flag,
`OnBufferEnd` release and auto-reset availability event protocol. Block capacity
comes from the larger of configured sample length and the per-block desired
reserve. Larger submissions split into frame-aligned chunks; every submitted
sample is copied. No pointer into a game stack or decoder scratch buffer is
retained by XAudio2.

When storage is full, submission waits on the availability event with the donor's
two-second device-stall deadline. Completion and voice-error callbacks wake that
wait. There is no sample drop or polling loop pretending that playback finished.
Playback starts after the desired frame reserve is queued; when the queue drains,
the donor's stop/re-prime behavior is retained. If tiny submissions fill all eight
slots before reaching the reserve, playback starts under storage pressure so the
queue can make progress without losing those samples.

The owner serializes initialization, submission, queries and closing. Voice
callbacks may release blocks concurrently. Close follows the donor's order:
stop/destroy source voice, destroy mastering voice, release engine, then free
PCM blocks and close the event. No callback may outlive voice destruction.
`DoClose` is idempotent and cleans up partial initialization. A voice callback
error, failed submit/start/stop, malformed frame length, changed open rate/channel
settings, or stalled device produces a real `Smash360_Fatal`, never silent audio.
Desired-buffer changes must fit the allocated capacity; sample-rate/channel
changes require reopening. The first 600 submitted blocks report real copied
PCM nonzero counts and peak values through `Smash360_Log`.

Periodic queue reports follow the current SoH donor's deferred formatting path:
the submission caller copies a bounded scalar snapshot into the existing native
diagnostic queue, and the worker computes milliseconds and formats the line.
The report contains no voice, player, or PCM pointers. Reporting retains Smash's
five-second cadence and actual configured sample rate.

The base destructor is currently nonvirtual. Construct this backend through
`make_shared<XAudio2AudioPlayer>` and then convert the shared pointer, preserving
the derived deleter. Never delete it through a raw `AudioPlayer*`. The integration
proposal uses that existing ownership pattern. Another inherited base behavior,
`SetAudioChannels` not updating `mInitialized` after reinitialization, is left
unchanged; the proposed Xbox integration makes any reopening failure explicit.

## Provenance and generation

The historical SoH360 `platform/xbox360/audio_xaudio2.cpp` donor had SHA-256
`eb94c94c4656d41e8ad8f0f1fe56cbc54c901af16fbab278ba22ac5486e4bd48`.
Its silence driver, synthetic `SoH_TestAudio`, mixer worker and SoH game policy
are not part of this backend. The active XAudio2 sink compiles from Shipyard.

`tools/prepare_audio_xdk.py` hash-checks five actual upstream files and three
integration-proposal inputs. It writes mapped source copies to
`scratch/audio-xdk`. Unchanged source spans retain their original `#line`
positions; replacement spans map to their original starting line, with detailed
changed ranges and output hashes in `provenance.json`.

Lowering is limited to explicit member/default constructors, initialized arrays,
constexpr spelling, `make_unique`, structured binding, tuple construction,
unscoped enum qualification, `stdint.h`, and explicit generated include guards
for the old XDK preprocessor. Desktop backend fanout includes are omitted from
the base header. Diagnostic calls route to the real `runtime/runtime.h` services,
with their two channel-name format substitutions expressed as `%s`. The decoder's
coefficients, filter arithmetic, delays, channel order, clipping, state reset,
buffer growth and ownership are unchanged.

## Integration proposal and evidence

`integration-proposal.patch` is generated, reviewable, and **not applied**. It
adds the XAUDIO2 backend enum value after existing values, selects the native
derived class on Xbox, excludes desktop backend selection there, records the
`xaudio2` configuration name, and validates stereo/matrix channel selection.
Xbox device failures stay visible instead of using upstream's Null fallback.
The patch passes `git apply --check`; the full Context/Config integration has not
been compiled, linked or installed. Consume it through the project's generated
compatibility integration, leaving upstream source authoritative.

The eventual application build needs this directory and the generated include
root on its include path, the two generated AudioPlayer/decoder sources plus
the two native backend/buffer-pool sources, the actual runtime diagnostics, and
XDK `xaudio2.lib`. The donor's project uses that native import library; the
object-only runner does not establish application link completeness.

Run `tests/audio/run.ps1`. It executes host tests of real AudioPlayer and decoder
dispatch against both original and lowered sources, compares nonzero 32000 Hz
decoded PCM byte-for-byte, tests decoder recreation and stereo/raw pass-through,
validates native settings, and checks real block memory/alignment/backpressure
with a concurrent native-thread release. Original host source adaptations are
limited to desktop include fanout and diagnostics. Host builds use `/W4 /WX` with
only inherited decoder `size_t`-to-`int` warning C4267 suppressed on 64-bit Windows.

The runner then compiles the actual lowered AudioPlayer, actual lowered
SoundMatrixDecoder, PcmBufferPool and XAudio2AudioPlayer to XDK objects. Current
host PCM comparison SHA-256:
`44ac399181b6788458b765e4d17ab8ffed52e826e60b747b943e1005835daa0c`.
This proves preserved host decoder output and compilation, not native XAudio2
execution, callback timing on Xbox, audible game audio, or surround routing on
hardware. No Xenia run, standalone audio XEX, substitute game mixer, or silence
success test is created.
