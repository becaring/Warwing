"""Hash-locked lowering of current LUS AudioPlayer and SoundMatrixDecoder.

No game mixer, channel algorithm, source samples, or upstream file is replaced.
"""
from pathlib import Path
import hashlib
import json
import difflib

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / "upstream/BattleShip/libultraship"
OUTPUT = ROOT / "scratch/audio-xdk"
LOCKS = {
    "include/ship/audio/AudioPlayer.h": "061f44f4cd64280a1e9b5abd55d2c37ebc4fc676fadc75556b88bfcad40d8345",
    "src/ship/audio/AudioPlayer.cpp": "9ae20bc09e60fd405f5571aed991d36631cdfd87602501aabccdc721722bd8da",
    "include/ship/audio/SoundMatrixDecoder.h": "bf666366f9d8ced7e4fe3292e64bab8b9551a47839337dbe64db31b7f9bb3874",
    "src/ship/audio/SoundMatrixDecoder.cpp": "c554720ec327248204357fb6dd030f3e0e8654d340853e4f5c863eeeeeac6deb",
    "include/ship/audio/AudioChannelsSetting.h": "18a233ed93c039ce2dd04419fb7ab7325ba88b8319a695f0c1bff6394514b29c",
}
PROPOSAL_LOCKS = {
    "include/ship/audio/Audio.h": "9e5ed13cadfb1992aa1e9ce3cd6611f3852daac0337905e7ac7e4763a3af5450",
    "src/ship/audio/Audio.cpp": "5f7f3b5d4b6ead668b0eb6e95b4858e863fe6dcc6e68b4d37deea85ceea7a97b",
    "src/ship/config/Config.cpp": "46cb055dd668c0629e30fdef187f3b8b22cc403e9ec61276ab9c04a46c6407da",
}


def replace(text, old, new):
    if text.count(old) != 1:
        raise ValueError("Audio transformation no longer uniquely matches: " + old[:100])
    return text.replace(old, new)


def common(path, text):
    if path.endswith("AudioPlayer.h"):
        # Backend fanout is not part of the base class and pulls in desktop SDKs.
        text = text[:text.index("#ifdef _WIN32")]
    if path.endswith("AudioPlayer.cpp"):
        text = replace(text, '#include "spdlog/spdlog.h"', '#include "audio_log.h"')
        text = text.replace("SPDLOG_TRACE", "Smash360_Log").replace("SPDLOG_INFO", "Smash360_Log").replace("SPDLOG_ERROR", "Smash360_Log")
        text = replace(text, '"Changing audio channels from {} to {}"', '"Changing audio channels from %s to %s"')
    return text


def lower(path, text):
    if path.endswith("AudioPlayer.h"):
        text = replace(text, "    int32_t SampleRate = 44100;", "    AudioSettings() : SampleRate(44100), SampleLength(1024), DesiredBuffered(2480), ChannelSetting(audioStereo) {}\n    int32_t SampleRate;")
        text = replace(text, "    int32_t SampleLength = 1024;", "    int32_t SampleLength;")
        text = replace(text, "    int32_t DesiredBuffered = 2480;", "    int32_t DesiredBuffered;")
        text = replace(text, "    AudioChannelsSetting ChannelSetting = AudioChannelsSetting::audioStereo;", "    AudioChannelsSetting ChannelSetting;")
        text = replace(text, "mAudioSettings(settings) {", "mAudioSettings(settings), mInitialized(false) {")
        text = replace(text, "    bool mInitialized = false;", "    bool mInitialized;")
    elif path.endswith("AudioPlayer.cpp"):
        text = text.replace("std::make_unique<SoundMatrixDecoder>(mAudioSettings.SampleRate)", "std::unique_ptr<SoundMatrixDecoder>(new SoundMatrixDecoder(mAudioSettings.SampleRate))")
        text = replace(text, "    const auto [surroundOut, surroundLen] = mSoundMatrixDecoder->Process(buf, len);",
                       "    const std::tuple<const uint8_t*, int> surround = mSoundMatrixDecoder->Process(buf, len);\n    const uint8_t* surroundOut = std::get<0>(surround);\n    const int surroundLen = std::get<1>(surround);")
        text = text.replace("AudioChannelsSetting::", "")
    elif path.endswith("SoundMatrixDecoder.h"):
        text = replace(text, "#include <cstdint>", "#include <stdint.h>")
        text = replace(text, "~SoundMatrixDecoder() = default;", "~SoundMatrixDecoder() {}")
        text = replace(text, "    struct BiquadCascade {", "    struct BiquadCascade {\n        BiquadCascade() { for (int i = 0; i < 4; ++i) { X[i] = 0; Y[i] = 0; } }")
        text = text.replace("double X[4] = {};", "double X[4];").replace("double Y[4] = {};", "double Y[4];")
        text = replace(text, "    struct AllPassChain {", "    struct AllPassChain {\n        AllPassChain() : Freq(0), FreqMin(0), FreqMax(0), SweepRate(0), Ready(false) { for (int i = 0; i < 4; ++i) { XHist[i] = 0; YHist[i] = 0; } }")
        for name in ("Freq", "FreqMin", "FreqMax", "SweepRate"):
            text = replace(text, f"double {name} = 0;", f"double {name};")
        text = replace(text, "double XHist[4] = {};", "double XHist[4];")
        text = replace(text, "double YHist[4] = {};", "double YHist[4];")
        text = replace(text, "bool Ready = false;", "bool Ready;")
        text = replace(text, "    struct CircularDelay {", "    struct CircularDelay {\n        CircularDelay() : Head(0), Length(0) { for (int i = 0; i < gMaxDelay; ++i) Data[i] = 0; }")
        text = replace(text, "std::array<float, gMaxDelay> Data = {};", "std::array<float, gMaxDelay> Data;")
        text = replace(text, "int Head = 0;", "int Head;")
        text = replace(text, "int Length = 0;", "int Length;")
        text = replace(text, "int32_t mDelayLength = 0;", "int32_t mDelayLength;")
        text = replace(text, "double mAllPassBaseRate = 1.0;", "double mAllPassBaseRate;")
        text = text.replace("constexpr", "const")
    elif path.endswith("SoundMatrixDecoder.cpp"):
        text = text.replace("constexpr", "const")
        text = replace(text, "SoundMatrixDecoder::SoundMatrixDecoder(int32_t sampleRate) {", "SoundMatrixDecoder::SoundMatrixDecoder(int32_t sampleRate) : mDelayLength(0), mAllPassBaseRate(1.0) {")
        for name in ("mPhaseLeftMain", "mPhaseLeftCross", "mPhaseRightMain", "mPhaseRightCross"):
            text = replace(text, name + " = {};", name + " = AllPassChain();")
        for name in ("mCenterHighPass", "mCenterLowPass", "mSurrLeftMainHP", "mSurrLeftCrossHP", "mSurrRightMainHP", "mSurrRightCrossHP", "mSubLowPass"):
            text = replace(text, name + " = {};", name + " = BiquadCascade();")
        for name in ("mDelaySurrLeft", "mDelaySurrRight"):
            text = replace(text, name + " = {};", name + " = CircularDelay();")
        text = replace(text, "return { reinterpret_cast<const uint8_t*>(mSurroundBuffer.data()), samplePairs * 6 * sizeof(int16_t) };",
                       "return std::make_tuple(reinterpret_cast<const uint8_t*>(mSurroundBuffer.data()), static_cast<int>(samplePairs * 6 * sizeof(int16_t)));")
    return text


def integration_proposal():
    """Write a reviewable patch only. Actual Context/Config integration is separate."""
    patch = []
    for relative, expected in PROPOSAL_LOCKS.items():
        raw = (UPSTREAM / relative).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise SystemExit("Integration proposal source hash mismatch: " + relative)
        original = raw.decode().replace("\r\n", "\n")
        text = original
        if relative.endswith("Audio.h"):
            text = replace(text, "enum class AudioBackend { WASAPI, SDL, COREAUDIO, NUL };", "enum class AudioBackend { WASAPI, SDL, COREAUDIO, NUL, XAUDIO2 };")
        elif relative.endswith("Audio.cpp"):
            text = replace(text, '#include "ship/audio/Audio.h"', '#include "ship/audio/Audio.h"\n#ifdef _XBOX\n#include "sources/audio/XAudio2AudioPlayer.h"\n#include "runtime/runtime.h"\n#endif')
            text = text.replace("#ifdef _WIN32", "#if defined(_WIN32) && !defined(_XBOX)")
            text = replace(text, "        case AudioBackend::SDL:", "#ifdef _XBOX\n        case AudioBackend::XAUDIO2:\n            mAudioPlayer = std::make_shared<XAudio2AudioPlayer>(this->mAudioSettings, false);\n            break;\n        default:\n            Smash360_Fatal(\"unsupported Xbox audio backend\", E_INVALIDARG);\n#else\n        case AudioBackend::SDL:")
            text = replace(text, "            mAudioPlayer = std::make_shared<NullAudioPlayer>(this->mAudioSettings);\n            break;", "            mAudioPlayer = std::make_shared<NullAudioPlayer>(this->mAudioSettings);\n            break;\n#endif")
            text = replace(text, "        SetCurrentAudioBackend(AudioBackend::NUL);", "#ifdef _XBOX\n        Smash360_Fatal(\"Xbox audio initialization failed\", E_FAIL);\n#else\n        SetCurrentAudioBackend(AudioBackend::NUL);\n#endif")
            text = replace(text, "    mAvailableAudioBackends = std::make_shared<std::vector<AudioBackend>>();", "    mAvailableAudioBackends = std::make_shared<std::vector<AudioBackend>>();\n#ifdef _XBOX\n    mAvailableAudioBackends->push_back(AudioBackend::XAUDIO2);\n    SetCurrentAudioBackend(AudioBackend::XAUDIO2);\n#else")
            text = replace(text, "    SetCurrentAudioBackend(Context::GetInstance()->GetConfig()->GetCurrentAudioBackend());", "    SetCurrentAudioBackend(Context::GetInstance()->GetConfig()->GetCurrentAudioBackend());\n#endif")
            text = replace(text, "void Audio::SetAudioChannels(AudioChannelsSetting channels) {", "void Audio::SetAudioChannels(AudioChannelsSetting channels) {\n#ifdef _XBOX\n    if (channels != audioStereo && channels != audioMatrix51) {\n        Smash360_Log(\"BattleShip stereo mixer does not supply raw 5.1 PCM\");\n        return;\n    }\n#endif")
            text = replace(text, "            mAudioPlayer->SetAudioChannels(channels);", "#ifdef _XBOX\n            if (!mAudioPlayer->SetAudioChannels(channels)) Smash360_Fatal(\"Xbox audio channel initialization failed\", E_FAIL);\n#else\n            mAudioPlayer->SetAudioChannels(channels);\n#endif")
        else:
            text = replace(text, '    std::string backendName = GetString("Window.AudioBackend");', '    std::string backendName = GetString("Window.AudioBackend");\n#ifdef _XBOX\n    if (backendName == "xaudio2") return AudioBackend::XAUDIO2;\n#endif')
            text = replace(text, "void Config::SetCurrentAudioBackend(AudioBackend backend) {\n    switch (backend) {", "void Config::SetCurrentAudioBackend(AudioBackend backend) {\n    switch (backend) {\n        case AudioBackend::XAUDIO2:\n            SetString(\"Window.AudioBackend\", \"xaudio2\");\n            break;")
        name = "upstream/BattleShip/libultraship/" + relative
        patch.extend(difflib.unified_diff(original.splitlines(True), text.splitlines(True), fromfile="a/"+name, tofile="b/"+name))
    (ROOT / "platform/xbox360/audio/integration-proposal.patch").write_text("".join(patch), encoding="utf-8", newline="\n")


def main():
    originals = {}
    for relative, expected in LOCKS.items():
        raw = (UPSTREAM / relative).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != expected: raise SystemExit(f"Audio source hash mismatch: {relative}: {digest}")
        originals[relative] = raw.decode().replace("\r\n", "\n")
    manifest = {"source_hashes": LOCKS, "outputs": {}, "source_mappings": {},
                "semantics": "Current AudioPlayer and matrix decoder algorithms unchanged; desktop includes/log transport and unsupported initialization syntax adapted.",
                "verification": "Host original/generated decoder comparison plus native backend XDK object compilation. No native voice execution."}
    for variant in ("original", "generated"):
        for relative, original in originals.items():
            text = common(relative, original)
            if variant == "generated": text = lower(relative, text)
            old_lines, new_lines = original.splitlines(True), text.splitlines(True)
            mapped = []
            changes = []
            for kind, old_start, old_end, new_start, new_end in difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False).get_opcodes():
                if new_start != new_end:
                    mapped.append(f'#line {old_start + 1} "upstream/BattleShip/libultraship/{relative}"\n')
                    mapped.extend(new_lines[new_start:new_end])
                if kind != "equal":
                    changes.append({"kind": kind, "original_first_line": old_start + 1,
                                    "original_line_count": old_end - old_start, "generated_line_count": new_end - new_start})
            text = "".join(mapped)
            if relative.endswith(".h"):
                guard = "SMASH360_GENERATED_AUDIO_" + Path(relative).stem.upper() + "_H"
                text = f"#ifndef {guard}\n#define {guard}\n" + text + "\n#endif\n"
            target = OUTPUT / variant / (relative if relative.startswith("include/") else Path(relative).name)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8", newline="\n")
            manifest["outputs"][target.relative_to(ROOT).as_posix()] = hashlib.sha256(text.encode()).hexdigest()
            manifest["source_mappings"][target.relative_to(ROOT).as_posix()] = changes
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "provenance.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    integration_proposal()
    print("Generated current AudioPlayer and SoundMatrixDecoder with pinned source mappings")


if __name__ == "__main__": main()
