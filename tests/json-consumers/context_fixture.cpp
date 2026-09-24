// TEST-ONLY dependency fixture. Config and ConsoleVariable implementations are
// the real production files. Context lifecycle/window initialization are not
// under test here; this fixture must never enter an application source manifest.
#include "ship/Context.h"
#include "ship/config/Config.h"
#include "ship/window/Window.h"
#include <filesystem>
#include <stdexcept>

namespace {
std::shared_ptr<Ship::Config> config;
std::string directory;
struct TestContext : Ship::Context {};
}

void InstallConfigFixture(const std::string& path) {
    directory = std::filesystem::path(path).parent_path().string();
    config = std::make_shared<Ship::Config>(path);
}
std::shared_ptr<Ship::Context> Ship::Context::GetInstance() {
    static std::shared_ptr<Ship::Context> context = std::make_shared<TestContext>();
    return context;
}
Ship::Context::~Context() {}
std::shared_ptr<Ship::Config> Ship::Context::GetConfig() { return config; }
std::string Ship::Context::GetPathRelativeToAppDirectory(const std::string path, std::string) {
    return (std::filesystem::path(directory) / path).string();
}
std::shared_ptr<Ship::Window> Ship::Context::GetWindow() {
    throw std::logic_error("JSON consumer test unexpectedly requested Window");
}
bool Ship::Window::IsAvailableWindowBackend(int32_t) {
    throw std::logic_error("JSON consumer test unexpectedly requested backend availability");
}
