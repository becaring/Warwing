#include "smash360_input_sdl.h"
#include "ship/controller/physicaldevice/ConnectedPhysicalDeviceManager.h"
#include <cassert>
#include <cstdio>
#include <cstring>
#include <algorithm>
#include <vector>
#include <cmath>
#include <libultraship/libultra/controller.h>

namespace {
struct TestDeck {
    Ship::ConnectedPhysicalDeviceManager *manager;
    bool blocked;
    OSContPad pads[4];
    Ship::ConnectedPhysicalDeviceManager *GetConnectedPhysicalDeviceManager() { return manager; }
    bool GamepadGameInputBlocked() { return blocked; }
    void WriteToPad(void *out) { std::memcpy(out, pads, sizeof(pads)); }
} testDeck = {};
}
namespace Ship {
struct Context {
    static Context *GetInstance() {
        static Context context;
        return &context;
    }
    TestDeck *GetControlDeck() { return &testDeck; }
};
}
using Ship::Context;
#define MAX_AXIS_RANGE 85.0f
#define MAX_SDL_RANGE 32767.0f
enum { POSITIVE = 1, NEGATIVE = -1 };
static int __osMaxControllers = 4;
#include "mapping_methods.h"

static bool connected[4] = {}, rumble[4] = {true, true, true, true};
static ShipyardInputRawPad raw[4] = {};
static uint16_t motors[4][2] = {};
static uint32_t ticks = 0;
static unsigned reads[4] = {};
bool ShipyardInput_ReadPhysicalPad(unsigned slot, ShipyardInputRawPad *state) {
    ++reads[slot];
    *state = raw[slot];
    return connected[slot];
}
bool ShipyardInput_PhysicalPadHasRumble(unsigned slot) { return rumble[slot]; }
bool ShipyardInput_WritePhysicalRumble(unsigned slot, uint16_t low, uint16_t high) {
    motors[slot][0] = low;
    motors[slot][1] = high;
    return connected[slot];
}
uint32_t ShipyardInput_InputMilliseconds() { return ticks; }
static void presentationSnapshotCases(Ship::ConnectedPhysicalDeviceManager &manager) {
    ShipyardInputRawPad cached = {};
    cached.buttons = 0xffff;
    assert(!ShipyardInput_ReadCachedGamepad(3, &cached) && cached.buttons == 0);
    // The actual generated GUI handler must poll when no presentation began.
    connected[3] = true;
    raw[3].buttons = 0x1000;
    raw[3].leftX = 1234;
    RefreshGuiDevices();
    for (unsigned i = 0; i < 4; ++i)
        assert(reads[i] == 1);
    assert(ShipyardInput_ReadCachedGamepad(3, &cached) && cached.buttons == 0x1000 && cached.leftX == 1234);
    assert(manager.GetConnectedSDLGamepadsForPort(0).size() == 1);

    connected[1] = true;
    raw[1].buttons = 0x2000;
    ShipyardInput_BeginGamepadPresentation();
    // Hardware changes after sampling cannot change the GUI's shared snapshot.
    raw[1].buttons = 0x4000;
    connected[3] = false;
    assert(ShipyardInput_ReadCachedGamepad(1, &cached) && cached.buttons == 0x2000);
    RefreshGuiDevices();
    for (unsigned i = 0; i < 4; ++i)
        assert(reads[i] == 2);
    assert(SDL_NumJoysticks() == 2);
    assert(manager.GetConnectedSDLGamepadsForPort(1).size() == 1);
    assert(ShipyardInput_ReadCachedGamepad(3, &cached) && cached.leftX == 1234);

    // Reuse is one-shot, so a missing next-frame sample cannot go stale.
    RefreshGuiDevices();
    for (unsigned i = 0; i < 4; ++i)
        assert(reads[i] == 3);
    assert(SDL_NumJoysticks() == 1 && manager.GetConnectedSDLGamepadsForPort(0).empty());
    assert(ShipyardInput_ReadCachedGamepad(1, &cached) && cached.buttons == 0x4000);
    assert(!ShipyardInput_ReadCachedGamepad(3, &cached) && cached.buttons == 0 && cached.leftX == 0);
    assert(!ShipyardInput_ReadCachedGamepad(4, &cached));
    assert(!ShipyardInput_ReadCachedGamepad(1, 0));

    // A normal game-read pump stays fresh and invalidates pending GUI reuse.
    ShipyardInput_BeginGamepadPresentation();
    raw[1].buttons = 0x8000;
    manager.RefreshNativeGamepads();
    for (unsigned i = 0; i < 4; ++i)
        assert(reads[i] == 5);
    assert(ShipyardInput_ReadCachedGamepad(1, &cached) && cached.buttons == 0x8000);
    raw[1].buttons = 0x1000;
    RefreshGuiDevices();
    for (unsigned i = 0; i < 4; ++i)
        assert(reads[i] == 6);
    assert(ShipyardInput_ReadCachedGamepad(1, &cached) && cached.buttons == 0x1000);

    // A second presentation at the same clock tick still samples all slots.
    connected[0] = true;
    ShipyardInput_BeginGamepadPresentation();
    RefreshGuiDevices();
    for (unsigned i = 0; i < 4; ++i)
        assert(reads[i] == 7);
    assert(SDL_NumJoysticks() == 2 && manager.GetConnectedSDLGamepadsForPort(0).size() == 1);
    assert(SDL_GameControllerRumble(SDL_GameControllerOpen(0), 10, 20, 1) == 0);
    ticks = 1;
    ShipyardInput_BeginGamepadPresentation();
    RefreshGuiDevices();
    for (unsigned i = 0; i < 4; ++i)
        assert(reads[i] == 8);
    assert(motors[0][0] == 0 && motors[0][1] == 0);
    for (unsigned i = 0; i < 4; ++i)
        connected[i] = false;
    std::memset(raw, 0, sizeof(raw));
    manager.RefreshNativeGamepads();
    puts("PASS presentation snapshot: four-slot freshness, one-shot GUI reuse, topology, independent polls, no clock "
         "cache");
}
int main() {
    Ship::ConnectedPhysicalDeviceManager manager;
    testDeck.manager = &manager;
    presentationSnapshotCases(manager);
    manager.RefreshNativeGamepads();
    assert(SDL_NumJoysticks() == 0);
    for (unsigned i = 0; i < 4; ++i)
        connected[i] = true;
    manager.RefreshNativeGamepads();
    assert(SDL_NumJoysticks() == 4);
    for (unsigned i = 0; i < 4; ++i)
        assert(manager.GetConnectedSDLGamepadsForPort(i).size() == 1);
    SDL_GameController *pad = SDL_GameControllerOpen(0);
    int32_t instance = SDL_JoystickInstanceID(pad);
    raw[0].buttons = 0xf3ff;
    raw[0].leftX = -32768;
    raw[0].leftY = -32768;
    raw[0].rightX = 32767;
    raw[0].rightY = 32767;
    raw[0].leftTrigger = 255;
    raw[0].rightTrigger = 128;
    manager.RefreshNativeGamepads();
    for (int i = 0; i < 15; ++i)
        assert(SDL_GameControllerGetButton(pad, static_cast<SDL_GameControllerButton>(i)) == (i != 5));
    for (int i = 15; i < SDL_CONTROLLER_BUTTON_MAX; ++i)
        assert(!SDL_GameControllerGetButton(pad, static_cast<SDL_GameControllerButton>(i)));
    assert(SDL_GameControllerGetAxis(pad, SDL_CONTROLLER_AXIS_LEFTX) == -32768);
    assert(SDL_GameControllerGetAxis(pad, SDL_CONTROLLER_AXIS_LEFTY) == 32767);
    assert(SDL_GameControllerGetAxis(pad, SDL_CONTROLLER_AXIS_RIGHTX) == 32767);
    assert(SDL_GameControllerGetAxis(pad, SDL_CONTROLLER_AXIS_RIGHTY) == -32767);
    assert(SDL_GameControllerGetAxis(pad, SDL_CONTROLLER_AXIS_TRIGGERLEFT) == 32767);
    assert(SDL_GameControllerGetAxis(pad, SDL_CONTROLLER_AXIS_TRIGGERRIGHT) == 16447);
    uint16_t mapped = 0;
    UpdateMappedButton(mapped, 0, 0x8000, SDL_CONTROLLER_BUTTON_A);
    assert(mapped == 0x8000);
    UpdateMappedButton(mapped, 0, 0x0040, SDL_CONTROLLER_BUTTON_B);
    assert(mapped == 0x8040); // remapped bitmask
    assert(MappedAxis(0, SDL_CONTROLLER_AXIS_LEFTY, POSITIVE) == 85.0f);
    assert(MappedAxis(0, SDL_CONTROLLER_AXIS_LEFTY, NEGATIVE) == 0.0f);
    testDeck.blocked = true;
    mapped = 0;
    UpdateMappedButton(mapped, 0, 0x8000, SDL_CONTROLLER_BUTTON_A);
    assert(mapped == 0);
    assert(MappedAxis(0, SDL_CONTROLLER_AXIS_LEFTY, POSITIVE) == 0.0f);
    testDeck.blocked = false;
    raw[0].leftX = 1;
    raw[0].leftY = 1;
    manager.RefreshNativeGamepads();
    assert(SDL_GameControllerGetAxis(pad, SDL_CONTROLLER_AXIS_LEFTX) == 1); // no second deadzone
    assert(SDL_GameControllerGetAxis(pad, SDL_CONTROLLER_AXIS_LEFTY) == -1);
    manager.IgnoreInstanceIdForPort(0, instance);
    manager.UnignoreInstanceIdForPort(2, instance);
    raw[1].buttons = 0;
    manager.RefreshNativeGamepads();
    assert(manager.GetConnectedSDLGamepadsForPort(0).empty());
    assert(manager.GetConnectedSDLGamepadsForPort(2).count(instance) == 1);
    assert(SDL_GameControllerRumble(pad, 65535, 1234, 0) == 0);
    ticks = 100000;
    manager.RefreshNativeGamepads();
    assert(motors[0][0] == 65535 && motors[0][1] == 1234);
    ticks = 0xfffffff0;
    assert(SDL_GameControllerRumble(pad, 10, 20, 32) == 0);
    ticks = 0;
    manager.RefreshNativeGamepads();
    assert(motors[0][0] == 10);
    ticks = 16;
    manager.RefreshNativeGamepads();
    assert(motors[0][0] == 0 && motors[0][1] == 0);
    float sensor[3] = {1, 2, 3};
    assert(!SDL_GameControllerHasSensor(pad, SDL_SENSOR_GYRO));
    assert(SDL_GameControllerGetSensorData(pad, SDL_SENSOR_GYRO, sensor, 3) == -1 && sensor[0] == 1);
    assert(!SDL_GameControllerHasLED(pad));
    assert(SDL_JoystickSetLED(pad, 1, 2, 3) == -1);
    connected[0] = false;
    manager.RefreshNativeGamepads();
    assert(SDL_NumJoysticks() == 3);
    assert(!SDL_GameControllerGetButton(pad, SDL_CONTROLLER_BUTTON_A));
    assert(SDL_GameControllerGetAxis(pad, SDL_CONTROLLER_AXIS_LEFTX) == 0);
    assert(manager.GetConnectedSDLGamepadsForPort(2).count(instance) == 0);
    connected[0] = true;
    manager.RefreshNativeGamepads();
    assert(SDL_JoystickInstanceID(pad) != instance);
    assert(manager.GetConnectedSDLGamepadsForPort(0).size() == 1);
    SDL_JoystickGUID guid = SDL_JoystickGetDeviceGUID(0);
    char guidText[33];
    SDL_JoystickGetGUIDString(guid, guidText, 33);
    assert(strlen(guidText) == 32);
    // A tap seen only by a display pump between two game reads reaches the next game read once.
    raw[0].buttons = 0;
    manager.RefreshNativeGamepads();
    assert(!SDL_GameControllerGetButton(pad, SDL_CONTROLLER_BUTTON_START));
    raw[0].buttons = 0x0010;
    ShipyardInput_PumpGamepads();
    raw[0].buttons = 0;
    ShipyardInput_PumpGamepads();
    manager.RefreshNativeGamepads();
    assert(SDL_GameControllerGetButton(pad, SDL_CONTROLLER_BUTTON_START));
    manager.RefreshNativeGamepads();
    assert(!SDL_GameControllerGetButton(pad, SDL_CONTROLLER_BUTTON_START));
    ShipyardInput_StopPhysicalRumble();
    for (int i = 0; i < 4; ++i)
        assert(motors[i][0] == 0 && motors[i][1] == 0);
    // Exact current osContGetReadData writes only the game's six-byte records,
    // including error fields; guards and each record's padding remain intact.
    uint16_t guardedWords[14];
    std::memset(guardedWords, 0xa5, sizeof(guardedWords));
    for (int i = 0; i < 4; ++i) {
        testDeck.pads[i].button = uint16_t(0x8123 + i);
        testDeck.pads[i].stick_x = int8_t(10 + i);
        testDeck.pads[i].stick_y = int8_t(-20 - i);
        testDeck.pads[i].err_no = uint8_t(i);
    }
    osContGetReadData(reinterpret_cast<OSContPad *>(guardedWords + 1));
    uint8_t *bytes = reinterpret_cast<uint8_t *>(guardedWords);
    assert(guardedWords[0] == 0xa5a5 && guardedWords[13] == 0xa5a5);
    for (int i = 0; i < 4; ++i) {
        uint16_t button;
        std::memcpy(&button, bytes + 2 + i * 6, 2);
        assert(button == 0x8123 + i);
        assert(int8_t(bytes[4 + i * 6]) == 10 + i);
        assert(int8_t(bytes[5 + i * 6]) == -20 - i);
        assert(bytes[6 + i * 6] == i);
        assert(bytes[7 + i * 6] == 0xa5);
    }
    puts("PASS native polling with actual current manager: four-slot routing, remapping, disconnect/reconnect, raw "
         "axes, rumble, absent capabilities");
    puts("PASS exact pinned mapping methods: button remap, axes, blocked gamepad; exact osContGetReadData six-byte "
         "stride with guards");
}
