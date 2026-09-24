"""Stage actual Config/CVar classes for XDK; no substituted application classes."""
from pathlib import Path
import hashlib,json,runpy,re,difflib
ROOT=Path(__file__).resolve().parents[1]
LUS=ROOT/'upstream/BattleShip/libultraship'
OUT=ROOT/'scratch/config-xdk'
BASE=ROOT/'platform/xbox360/cpp-compat/config'
LOCKS={'include/ship/config/Config.h': '36e187fe87aeee9f9e2c981c19f2a3ce30dd39787cb98324c2ad3c2b8f7505bb', 'src/ship/config/Config.cpp': '46cb055dd668c0629e30fdef187f3b8b22cc403e9ec61276ab9c04a46c6407da', 'include/ship/config/ConsoleVariable.h': 'bde2827a62726e488f53343f605155b28fc908ce209cb3385332ab815756fb95', 'src/ship/config/ConsoleVariable.cpp': '7274d237da2cc62a649e5ed274ed17cf6c33a070d95a196060d1a2670a9de76d', 'include/ship/Context.h': 'b37f3c4f9cf938d9f612d1dee89fdc876d8ea12559a0df7ea25075c9e172597c', 'include/ship/window/Window.h': '6cfc2876cc9fa17cabffa82cbf7741abcaee2a8b0ee57cbc1ebcb4b222d98f69', 'src/ship/window/Window.cpp': 'de5031138c0a8d0d6116917d4466b58e4e3e6bfdea0c09a3cf06abe5ce4f4598', 'include/ship/audio/Audio.h': '9e5ed13cadfb1992aa1e9ce3cd6611f3852daac0337905e7ac7e4763a3af5450', 'include/ship/utils/StringHelper.h': '9082dd8682021b2e9b01005da53714d1810391ec171247a70d394fba965cf8f5', 'src/ship/utils/StringHelper.cpp': '4aa58597047642106571828ceb41886c51d914dcb315a573eab992f8f568391c', 'include/ship/utils/filesystemtools/DiskFile.h': '9383b3591e97034cd4beb6f569cda9fc5795887e738ae81d556d17ecf498123b', 'include/ship/utils/filesystemtools/Path.h': '226d2b64395888b88e9b7a1a1689e7bcd2c768f06176b5426347b2f30d556392', 'include/ship/utils/filesystemtools/Directory.h': 'ade3cdd25fb79d9a9dbd0421fdc91997624a3d4267bb0114bbd8911808ae26d8'}
LOWER=runpy.run_path(str(BASE/'lowering.py'))
PRISM=runpy.run_path(str(ROOT/'tools/prepare_prism_xdk.py'))
AUDIO=runpy.run_path(str(BASE/'audio_integration.py'))
LOCKS['src/ship/audio/Audio.cpp']='5f7f3b5d4b6ead668b0eb6e95b4858e863fe6dcc6e68b4d37deea85ceea7a97b'
def once(text,a,b,count=1):
    if text.count(a)!=count:raise ValueError('Config anchor changed: '+a[:100])
    return text.replace(a,b)
def enum_type(name,values):
    return ('struct '+name+' : Shipyard::Binary::ScopedEnum<'+name+'> { enum Value { '+values+' }; '
        +name+'() {} '+name+'(Value v) : Shipyard::Binary::ScopedEnum<'+name+'>(static_cast<int>(v)) {} '
        +'explicit '+name+'(int v) : Shipyard::Binary::ScopedEnum<'+name+'>(v) {} };')
def transform(relative,text):
    text=AUDIO['apply'](relative,text)
    text='#include "config/compiler.h"\n'+text
    if relative.endswith('/Config.cpp'):
        text=once(text,'#include <any>','// <any> was unused in this translation unit.')
        text=once(text,'namespace fs = std::filesystem;','namespace fs = xbox_compat::filesystem;')
        text=once(text,'    if (nlohmann::json tmp = Nested(key); tmp.is_array()) {','    nlohmann::json tmp = Nested(key);\n    if (tmp.is_array()) {')
        text=once(text,'    auto [_, emplaced] = mVersionUpdaters.emplace(versionUpdater->GetVersion(), versionUpdater);','    const auto insertion = mVersionUpdaters.insert(std::make_pair(versionUpdater->GetVersion(), versionUpdater));\n    const bool emplaced = insertion.second;')
        text=once(text,'    for (auto [_, versionUpdater] : mVersionUpdaters) {','    for (auto entry : mVersionUpdaters) {\n        auto versionUpdater = entry.second;')
        text=once(text,'switch (backend) {','switch (backend.GetValue()) {',2)
        text=once(text,'static_cast<int>(backend)','backend.GetValue()')
        text=text.replace('AudioChannelsSetting::','')
        text=once(text,'std::ifstream ifs(mPath);','std::ifstream ifs(fs::absolute(mPath).string().c_str());')
        text=once(text,'std::ofstream file(mPath);','std::ofstream file(fs::absolute(mPath).string().c_str());')
        text=once(text,'#ifdef _WIN32\n    return AudioBackend::WASAPI;', '#ifdef _XBOX\n    return AudioBackend::XAUDIO2;\n#elif defined(_WIN32)\n    return AudioBackend::WASAPI;')
        text=once(text,'#ifdef ENABLE_DX11\n    return WindowBackend::FAST3D_DXGI_DX11;', '#ifdef _XBOX\n    return WindowBackend::FAST3D_XENOS;\n#elif defined(ENABLE_DX11)\n    return WindowBackend::FAST3D_DXGI_DX11;')
        text=once(text,'        case WindowBackend::FAST3D_DXGI_DX11:', '        case WindowBackend::FAST3D_XENOS:\n            SetString("Window.Backend.Name", "Xenos");\n            break;\n        case WindowBackend::FAST3D_DXGI_DX11:')
    elif relative.endswith('/ConsoleVariable.h'):
        text=once(text,'typedef enum class ConsoleVariableType { Integer, Float, String, Color, Color24 } ConsoleVariableType;',enum_type('ConsoleVariableType','Integer, Float, String, Color, Color24'))
        text=once(text,'typedef struct CVar {','typedef struct CVar {\n    CVar() : Type(ConsoleVariableType::Integer), String(nullptr) {}')
        text=once(text,'char* String = nullptr;','char* String;')
        text=once(text,'using is_transparent = void;','typedef void is_transparent;',2)
        text=once(text,'return std::hash<std::string_view>{}(sv);','return xbox_compat::hash_string_view(sv);')
        text=text.replace(' const noexcept',' const')
    elif relative.endswith('/ConsoleVariable.cpp'):
        text=once(text,'switch (variableTo->Type) {','switch (variableTo->Type.GetValue()) {')
    elif relative.endswith('/Audio.h'):
        text=once(text,'enum class AudioBackend { WASAPI, SDL, COREAUDIO, NUL, XAUDIO2 };',enum_type('AudioBackend','WASAPI, SDL, COREAUDIO, NUL, XAUDIO2'))
    elif relative.endswith('/Audio.cpp'):
        text=once(text,'#include "ship/controller/controldeck/ControlDeck.h"','#include "ship/config/Config.h"\n#include <spdlog/spdlog.h> // Direct includes for the Config methods and trace macro used below.')
        text=once(text,'switch (GetCurrentAudioBackend()) {','switch (GetCurrentAudioBackend().GetValue()) {')
    elif relative.endswith('/Window.h'):
        text=once(text,'#include "ship/window/gui/Gui.h"','namespace Ship { class Gui; class GuiWindow; }')
        text=once(text,'#include "ship/window/MouseStateManager.h"','namespace Ship { class MouseStateManager; }')
        text=once(text,'enum class WindowBackend { FAST3D_DXGI_DX11, FAST3D_SDL_OPENGL, FAST3D_SDL_METAL, WINDOW_BACKEND_COUNT };',enum_type('WindowBackend','FAST3D_DXGI_DX11, FAST3D_SDL_OPENGL, FAST3D_SDL_METAL, FAST3D_XENOS = 3, WINDOW_BACKEND_COUNT = 4'))
        text=once(text,'int32_t mLastScancode = -1;','int32_t mLastScancode; // Relocated to real Window.cpp primary constructor.')
    elif relative.endswith('/Window.cpp'):
        # This paired source relocation must accompany the staged Window header.
        # It is not a claim that all Window implementation dependencies compile.
        text=once(text,'Window::Window(std::shared_ptr<Gui> gui, std::shared_ptr<MouseStateManager> mouseStateManager) {','Window::Window(std::shared_ptr<Gui> gui, std::shared_ptr<MouseStateManager> mouseStateManager) : mLastScancode(-1) {')
    elif relative.endswith('/Context.h'):
        text=once(text,'Context() = default;','Context() {}')
        text=text.replace('archivePaths = {}','archivePaths = std::vector<std::string>()')
        text=text.replace('validHashes = {}','validHashes = std::unordered_set<uint32_t>()')
        text=once(text,'AudioSettings audioSettings = {}','AudioSettings audioSettings = AudioSettings()')
        # Disabled scripting is excluded by the authoritative runtime target.
    elif relative.endswith('/StringHelper.cpp'):
        text=once(text,'std::begin(elements), std::end(elements)','elements.begin(), elements.end()')
        text=once(text,'std::strtoull(str.c_str(), nullptr, base)','::_strtoui64(str.c_str(), nullptr, base)')
        text=once(text,'return std::equal(a.begin(), a.end(), b.begin(), b.end(),','return a.size() == b.size() && std::equal(a.begin(), a.end(), b.begin(),')
    elif relative.endswith('/Directory.h') or relative.endswith('/Path.h'):
        a=text.index('#if __has_include(<filesystem>)');b=text.index('#endif',a)+len('#endif')
        text=text[:a]+'#include "filesystem/filesystem.h"\nnamespace fs = xbox_compat::filesystem;'+text[b:]
    if relative.endswith('/DiskFile.h'):
        text=text.replace('file(filePath,','file(fs::absolute(filePath).string().c_str(),')
    text=text.replace('#include <string_view>','#include "config/string_view.h"')
    text=text.replace('std::string_view','xbox_compat::string_view')
    text=text.replace('#include <filesystem>','#include "filesystem/filesystem.h"')
    if not relative.endswith('/Window.cpp'):
        text=LOWER['lower_ranges'](text.encode()).decode()
    return text

def prepare():
    changed={}
    for relative,digest in LOCKS.items():
        raw=(LUS/relative).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('Config source SHA drift: '+relative)
        changed[relative]=transform(relative,raw.decode('utf-8-sig').replace('\r\n','\n'))
    results={}
    for relative,text in changed.items():
        target=OUT/'generated'/relative
        PRISM['mapped']('upstream/BattleShip/libultraship/'+relative,text,target)
        results[relative]=hashlib.sha256(target.read_bytes()).hexdigest()
    manifest={'input_hashes':LOCKS,'output_hashes':results,'audio_integration_patch_sha256':AUDIO['SHA'],'source_mapping':'Prism centralized mapped function; range lowering derived from donor and Prism cached-end fix','real_application_classes_retained':True,'window_initializer_relocation':'generated/src/ship/window/Window.cpp primary ctor; full Window compile not included','dependencies':['scratch/audio-xdk/generated/include','Shipyard:sources/json/include','cpp-compat/filesystem','scratch/logging-xdk/core-include','scratch/logging-xdk/include'],'verification_report':'scratch/config-xdk/native-verification.json'}
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest
if __name__=='__main__':prepare();print('Staged real Config/CVar/Audio source; verification is recorded separately.')
