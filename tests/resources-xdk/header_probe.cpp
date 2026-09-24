#include "ship/resource/ResourceManager.h"
#include "ship/resource/archive/O2rArchive.h"
#include "ship/resource/archive/FolderArchive.h"
#include "ship/resource/factory/JsonFactory.h"
#include "ship/resource/factory/ShaderFactory.h"
#include "ship/utils/filesystemtools/FileHelper.h"
// Actual declarations, no fake Context/ResourceManager/archive classes.
void resource_header_probe(Ship::ResourceManager& manager, const Ship::ResourceIdentifier& id) {
    xbox_compat::shared_future<std::shared_ptr<Ship::IResource>> one = manager.LoadResourceAsync(id);
    xbox_compat::shared_future<std::shared_ptr<std::vector<std::shared_ptr<Ship::IResource>>>> list = manager.LoadResourcesAsync("*");
    Ship::File file;
    Ship::ArchiveManifest manifest;
    if (file.BufferOffset || file.IsLoaded || manifest.CodeVersion || manifest.GameVersion) throw std::logic_error("defaults changed");
    one.wait(); list.wait();
}
