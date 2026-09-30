"""Stage actual manifest-selected controller sources over native input contract."""
from pathlib import Path
import hashlib,json,runpy,re
ROOT=Path(__file__).resolve().parents[1]
UP=ROOT/'upstream/BattleShip/libultraship'
BASE=ROOT/'platform/xbox360/cpp-compat/controllers'
OUT=ROOT/'scratch/controllers-xdk'
INPUT=ROOT/'scratch/input-xdk/source/libultraship'
MAP=runpy.run_path(str(ROOT/'tools/prepare_prism_xdk.py'))['mapped']
LOWER=runpy.run_path(str(BASE/'lowering.py'))
INITIALIZERS=runpy.run_path(str(BASE/'initializers.py'))
CONSTRUCTORS=runpy.run_path(str(BASE/'constructors.py'))
def once(text,a,b,count=1):
    if text.count(a)!=count:raise ValueError('Controller anchor drift: '+a[:90])
    return text.replace(a,b)
def guard(text,body):return once(text,body,'#if !defined(_XBOX)\n'+body+'\n#endif\n')
def unsupported_functions(text,names):
    data=text.encode();edits=[]
    for node in LOWER['walk'](LOWER['PARSER'].parse(data).root_node):
        if node.type!='function_definition':continue
        declarator=node.child_by_field_name('declarator')
        if declarator is None:continue
        name=declarator.child_by_field_name('declarator')
        if name and name.text.decode() in names:
            edits.append((node.start_byte,node.end_byte,b'#if !defined(_XBOX)\n'+node.text+b'\n#endif'))
    if len(edits)!=len(names):raise ValueError('Raphnet function selection drift')
    return LOWER['apply'](data,edits).decode()
def platform(relative,text):
    from xbox360_platform.controller_routes import project as project_routes
    text=project_routes(relative,text)
    if relative=='src/ship/controller/physicaldevice/ConnectedPhysicalDeviceManager.cpp':
        # XDK 21256 xhash move construction swaps uninitialized bucket metadata
        # into the source. BattleShip reuses that source immediately. Start from
        # a valid empty map and swap: same node ownership, valid empty source.
        text=once(text,'    auto previouslyConnected = std::move(mConnectedSDLGamepads);',
                  '    std::unordered_map<int32_t, SDL_GameController*> previouslyConnected;\n'
                  '    previouslyConnected.swap(mConnectedSDLGamepads);')
    if relative=='include/ship/controller/physicaldevice/SDLAddRemoveDeviceEventHandler.h':
        signatures=[('',''),('const std::string& c, bool v, const std::string& n, ImVec2 s, uint32_t f','c,v,n,s,f'),('const std::string& c, bool v, const std::string& n, ImVec2 s','c,v,n,s'),('const std::string& c, bool v, const std::string& n','c,v,n'),('const std::string& c, const std::string& n, ImVec2 s, uint32_t f','c,n,s,f'),('const std::string& c, const std::string& n, ImVec2 s','c,n,s'),('const std::string& c, const std::string& n','c,n')]
        text=once(text,'    using GuiWindow::GuiWindow;','\n'.join('    SDLAddRemoveDeviceEventHandler('+params+') : GuiWindow('+args+') {}' for params,args in signatures))
    # Actual desktop USB implementation remains outside this target capability.
    if relative.endswith('.cpp'):
        for line in text.splitlines():
            if line.startswith('#include ') and '/raphnet/' in line:text=guard(text,line)
    if relative=='include/ship/controller/controldevice/controller/Controller.h':
        text=guard(text,'    virtual void SetRaphnetBinding(std::weak_ptr<RaphnetTransport> /*transport*/,\n                                   uint8_t /*channel*/) {}')
    if relative=='include/libultraship/controller/controldevice/controller/Controller.h':
        text=guard(text,'    void SetRaphnetBinding(std::weak_ptr<Ship::RaphnetTransport> transport, uint8_t channel) override;')
        start=text.index('    std::weak_ptr<Ship::RaphnetTransport> mRaphnetTransport;')
        end=text.index('    uint32_t mRaphnetConsecutivePollFailures = 0;',start)+len('    uint32_t mRaphnetConsecutivePollFailures = 0;')
        text=guard(text,text[start:end])
    if relative=='src/libultraship/controller/controldevice/controller/Controller.cpp':
        start=text.index('static void RaphnetDropPortBinding(');end=text.index('void Controller::ReadToOSContPad',start)
        text=guard(text,text[start:end])
        start=text.index('    if (mRaphnetBindingActive && pad != nullptr)');end=text.index('    OSContPad padToBuffer',start)
        text=guard(text,text[start:end])
    if relative=='src/ship/controller/controldeck/ControlDeck.cpp':
        text=unsupported_functions(text,{'ControlDeck::PreInitRaphnet','ControlDeck::ShutdownRaphnet','ControlDeck::GetRaphnetPhysicalDeviceManager'})
        start=text.index('    // Install Raphnet rumble mappings');end=text.index('\n}\n\nbool ControlDeck::ProcessKeyboardEvent',start)
        text=guard(text,text[start:end])
        text=once(text,'    mConnectedPhysicalDeviceManager = std::make_shared<ConnectedPhysicalDeviceManager>();','    mConnectedPhysicalDeviceManager = std::make_shared<ConnectedPhysicalDeviceManager>();\n#ifdef _XBOX\n    SPDLOG_WARN("Raphnet USB transport is unavailable on Xbox; saved adapter settings are retained");\n#endif')
    if relative=='src/ship/controller/controldevice/controller/mapping/factories/RumbleMappingFactory.cpp':
        text=once(text,'    int32_t lowFrequencyIntensityPercentage =', '#ifdef _XBOX\n    if (mappingClass == "RaphnetRumbleMapping") {\n        SPDLOG_WARN("Saved Raphnet rumble mapping {} is unavailable on Xbox; configuration retained", id);\n        return nullptr;\n    }\n#endif\n    int32_t lowFrequencyIntensityPercentage =')
    for expression,element in [('{ GetLeftStick(), GetRightStick() }','std::shared_ptr<ControllerStick>'),('{ LEFT, RIGHT, UP, DOWN }','Direction')]:
        data=text.encode();edits=[]
        for node in LOWER['walk'](LOWER['PARSER'].parse(data).root_node):
            if node.type!='for_range_loop':continue
            right=node.child_by_field_name('right')
            if right.text.decode()!=expression:continue
            prefix=data[node.start_byte:right.start_byte].decode();suffix=data[right.end_byte:node.end_byte].decode()
            value='{ const '+element+' _controllerValues[] = '+expression+'; '+prefix+'_controllerValues'+suffix+' }'
            edits.append((node.start_byte,node.end_byte,value.encode()))
        text=LOWER['apply'](data,edits).decode()
    if relative=='include/ship/controller/controldeck/ControlDeck.h':
        for line in ('    void PreInitRaphnet();','    void ShutdownRaphnet();','    std::shared_ptr<RaphnetPhysicalDeviceManager> GetRaphnetPhysicalDeviceManager();','    std::shared_ptr<RaphnetPhysicalDeviceManager> mRaphnetPhysicalDeviceManager;'):text=guard(text,line)
        text=once(text,'mPorts = {};','mPorts;')
        text=once(text,'mControllerBits = nullptr;','mControllerBits;')
    elif relative=='src/ship/controller/controldeck/ControlDeck.cpp':
        text=once(text,'std::unordered_map<CONTROLLERBUTTONS_T, std::string> buttonNames) {','std::unordered_map<CONTROLLERBUTTONS_T, std::string> buttonNames) : mControllerBits(nullptr) {')
    if relative.endswith('.cpp') and '->GetGui()->' in text:
        text='#include "ship/window/gui/Gui.h"\n'+text
    for name,member in [('Button','mButtonMappings'),('LED','mLEDMappings'),('Rumble','mRumbleMappings')]:
        if relative.endswith('/Controller'+name+'.cpp'):
            text=once(text,'[physicalDeviceType](const auto& mapping)','[physicalDeviceType](const std::unordered_map<std::string, std::shared_ptr<Controller'+name+'Mapping>>::value_type& mapping) -> bool')
    if relative.endswith('/ControllerStick.cpp'):
        text=once(text,'[physicalDeviceType](const auto& directionMappings)', '[physicalDeviceType](const std::unordered_map<Direction,std::unordered_map<std::string,std::shared_ptr<ControllerAxisDirectionMapping>>>::value_type& directionMappings) -> bool')
        text=once(text,'[physicalDeviceType](const auto& mappingPair)', '[nestedPhysicalDeviceType](const std::unordered_map<std::string, std::shared_ptr<ControllerAxisDirectionMapping>>::value_type& mappingPair) -> bool')
        text=once(text,'                           return std::any_of(directionMappings.second.begin()', '                           const PhysicalDeviceType nestedPhysicalDeviceType = physicalDeviceType;\n                           return std::any_of(directionMappings.second.begin()')
        text=once(text,'                                                         physicalDeviceType;', '                                                         nestedPhysicalDeviceType;')
        text=once(text,'constexpr auto octagonAngle = M_TAU / 8;', 'const double octagonAngle = M_TAU / 8;')
        text=once(text,'std::round(angle / octagonAngle)', 'Smash360Controllers::Round(angle / octagonAngle)')
        text=text.replace('copysign(', '_copysign(')
    if relative.endswith('/WheelHandler.cpp'):
        text=once(text,'mDirections = { LUS_WHEEL_NONE, LUS_WHEEL_NONE };','mDirections.x = mDirections.y = LUS_WHEEL_NONE;')
        text=once(text,'mBufferedCoords = { 0.0f, 0.0f };','mBufferedCoords.x = mBufferedCoords.y = 0.0f;')
        text=text.replace('copysignf(', 'static_cast<float>(_copysign(').replace('_copysign(LIMIT, *buf);','_copysign(LIMIT, *buf));').replace('_copysign(REDUCE_STEP, *buf);','_copysign(REDUCE_STEP, *buf));')
    if relative.endswith(('/ControllerLEDMapping.cpp','/LEDMappingFactory.cpp')):
        text=text.replace('Color_RGB8({ 0, 0, 0 })','Color_RGB8()').replace('c_str(), { 0, 0, 0 });','c_str(), Color_RGB8());')
    if relative.endswith('/SDLLEDMapping.cpp'):
        text=once(text,'color = { 0, 0, 0 };','color = Color_RGB8();')
    text=INITIALIZERS['lower'](text,relative,LOWER)
    text=CONSTRUCTORS['lower'](relative,text,LOWER)
    return text
def prepare():
    locks=json.loads((BASE/'source-lock.json').read_text())
    selection=json.loads((ROOT/'scratch/application-xdk/source-manifest.json').read_text())
    selected={e['path'].removeprefix('libultraship/') for e in selection['sources'] if e['selected'] and e['path'].startswith('libultraship/') and '/controller/' in e['path'] and '/raphnet/' not in e['path']}
    if selected!={r for r in locks if r.endswith('.cpp')}:raise ValueError('Controller manifest source set changed')
    input_manifest=json.loads((INPUT.parent/'input-manifest.json').read_text())
    input_locks={e['path'].removeprefix('libultraship/'):e for e in input_manifest['sources']}
    originals={}
    for relative,expected in locks.items():
        raw=(UP/relative).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('Controller source SHA drift: '+relative)
        originals[relative]=raw.decode('utf-8-sig').replace('\r\n','\n')
    enums=set()
    for text in originals.values():
        for node in LOWER['walk'](LOWER['PARSER'].parse(text.encode()).root_node):
            if node.type=='enum_specifier':
                if b'enum class' in node.text[:20]:raise ValueError('Scoped enum needs explicit wrapper')
                name=node.child_by_field_name('name')
                if name:enums.add(name.text.decode())
    results={};platform_sources={};pending={}
    for relative,original in originals.items():
        source=INPUT/relative
        text=source.read_text(encoding='utf-8-sig') if source.is_file() else original
        if source.is_file():
            digest=hashlib.sha256(source.read_bytes()).hexdigest();record=input_locks.get(relative)
            if not record or digest!=record['output_sha256'] or record['source_sha256']!=locks[relative]:raise ValueError('Native input overlay provenance mismatch: '+relative)
            platform_sources[relative]=digest
        text=platform(relative,text)
        text=LOWER['syntax'](text,enums)
        text='#include "controllers/compiler.h"\n'+text
        pending[relative]=text
    for relative,text in pending.items():
        target=OUT/'generated'/relative
        MAP('upstream/BattleShip/libultraship/'+relative,text,target)
        results[relative]=hashlib.sha256(target.read_bytes()).hexdigest()
    OUT.mkdir(parents=True,exist_ok=True)
    report={'originals':locks,'native_input_overlay':platform_sources,'generated':results,'enum_qualification_lowered':sorted(enums),'status':'source staging; compile report separate'}
    (OUT/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    return report
if __name__=='__main__':prepare()
