// Test-only service injection. The actual ResourceManager/Loader/archive methods
// and classes are linked unchanged or generated; only Context service lookup is
// supplied by this fixture. This does not validate application startup/shutdown.
#include "ship/Context.h"
#include "ship/resource/ResourceManager.h"
namespace {
std::shared_ptr<Ship::ResourceManager> installed;
struct TestContext : Ship::Context {};
}
void InstallManagerFixture(std::shared_ptr<Ship::ResourceManager> value) { installed = value; }
std::shared_ptr<Ship::Context> Ship::Context::GetInstance() {
    static std::shared_ptr<Ship::Context> context(new TestContext()); return context;
}
Ship::Context::~Context() {}
std::shared_ptr<Ship::ResourceManager> Ship::Context::GetResourceManager() { return installed; }
