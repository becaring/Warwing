// Link-only external services for the Config unit comparison. None is called
// by the persistence tests. Fail loudly if the tested path ever expands here.
// This file is test-only and must never be linked into Smash360.
#include "ship/Context.h"
#include "ship/window/Window.h"
#include <stdexcept>

std::shared_ptr<Ship::Context> Ship::Context::GetInstance() {
    throw std::logic_error("Config persistence test unexpectedly requested Context");
}
std::shared_ptr<Ship::Window> Ship::Context::GetWindow() {
    throw std::logic_error("Config persistence test unexpectedly requested Window");
}
bool Ship::Window::IsAvailableWindowBackend(int32_t) {
    throw std::logic_error("Config persistence test unexpectedly requested backend availability");
}
