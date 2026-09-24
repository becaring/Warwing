// Native platform shader service through the actual current LUS resource path.
// Contract follows pinned DX11 dx_include_fs: final f3d.o2r resources, exact
// lookup, Binary Shader factory, native-order text; no direct-file fallback.
#include "ship/Context.h"
#include "ship/resource/ResourceManager.h"
#include "ship/resource/type/Shader.h"
#include "ship/resource/ResourceType.h"
#include <string>

bool Smash360_LoadShaderResource(const std::string& path, std::string& source) {
    std::shared_ptr<Ship::ResourceInitData> init = std::make_shared<Ship::ResourceInitData>();
    init->Type = static_cast<uint32_t>(Ship::ResourceType::Shader);
    init->ByteOrder = Ship::Endianness::Native;
    init->Format = RESOURCE_FORMAT_BINARY;
    std::shared_ptr<Ship::Shader> shader = std::static_pointer_cast<Ship::Shader>(
        Ship::Context::GetInstance()->GetResourceManager()->LoadResource(path, true, init));
    if (!shader) return false;
    source = *static_cast<std::string*>(shader->GetRawPointer());
    return true;
}
