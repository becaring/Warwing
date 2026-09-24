// TEST ONLY: dependency injection for the real ResourceLoader and factories.
// This fixture does not test Context lifecycle, queues, archives, or caching.
#include "ship/Context.h"
#include "ship/resource/ResourceManager.h"
#include <stdexcept>
namespace { std::shared_ptr<Ship::ResourceLoader> loader; struct TestContext : Ship::Context {}; }
void InstallResourceFixture(std::shared_ptr<Ship::ResourceLoader> value) { loader = value; }
std::shared_ptr<Ship::Context> Ship::Context::GetInstance() {
    static auto value = std::make_shared<TestContext>(); return value;
}
Ship::Context::~Context() {}
std::shared_ptr<Ship::ResourceManager> Ship::Context::GetResourceManager() {
    static auto value = std::make_shared<Ship::ResourceManager>(); return value;
}
Ship::ResourceManager::ResourceManager() {}
Ship::ResourceManager::~ResourceManager() {}
std::shared_ptr<Ship::ResourceLoader> Ship::ResourceManager::GetResourceLoader() { return loader; }
std::shared_ptr<Ship::File> Ship::ResourceManager::LoadFileProcess(const std::string&) {
    throw std::logic_error("Resource consumer fixture unexpectedly requested archive I/O");
}
