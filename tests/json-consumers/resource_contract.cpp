#include "ship/resource/ResourceLoader.h"
#include "ship/resource/type/Json.h"
#include "ship/resource/type/Shader.h"
#include <fstream>
#include <iostream>
#include <stdexcept>
void InstallResourceFixture(std::shared_ptr<Ship::ResourceLoader>);
struct Loader : Ship::ResourceLoader { using ResourceLoader::ReadResourceInitData; };
static void require(bool condition) { if (!condition) throw std::runtime_error("resource contract mismatch"); }
static std::shared_ptr<Ship::File> file(const std::string& text) {
    auto result = std::make_shared<Ship::File>();
    result->Buffer = std::make_shared<std::vector<char>>(text.begin(), text.end());
    result->Buffer->push_back(0); result->IsLoaded = true; return result;
}
int main(int argc, char** argv) {
    auto loader = std::make_shared<Loader>(); InstallResourceFixture(loader);
    auto meta = loader->ReadResourceInitData("fallback", file(R"({"path":"data/test.json","format":"BINARY","type":"Json","version":0})"));
    require(meta->Path == "data/test.json" && meta->Format == RESOURCE_FORMAT_BINARY && meta->ResourceVersion == 0);
    require(meta->Type == static_cast<uint32_t>(Ship::ResourceType::Json));
    auto payload = file(R"({/*actual factory accepts comments*/"float":1.0,"unsigned":18446744073709551615,"unicode":"\uD83D\uDE00","nested":[null,true,-9]})");
    auto result = std::dynamic_pointer_cast<Ship::Json>(loader->LoadResource(meta->Path, payload, meta));
    require(result && result->Data["float"].is_number_float());
    require(result->Data["unsigned"].get<uint64_t>() == UINT64_MAX && result->DataSize == payload->Buffer->size());
    require(result->GetInitData() == meta && result->Data["nested"][2].get<int>() == -9);
    std::ofstream out(argv[1], std::ios::binary); out << result->Data.dump(2); out.close();
    auto fallback = loader->ReadResourceInitData("fallback", file(R"({"format":"XML","type":"Shader","version":7})"));
    require(fallback->Path == "fallback" && fallback->Format == RESOURCE_FORMAT_XML && fallback->ResourceVersion == 7);
    bool failed = false;
    try { loader->ReadResourceInitData("bad", file(R"({"format":"BINARY","type":"Json","version":"bad"})")); }
    catch (const nlohmann::json::type_error&) { failed = true; }
    require(failed);
    failed = false;
    try { loader->LoadResource(meta->Path, file("{ broken"), meta); }
    catch (const nlohmann::json::parse_error&) { failed = true; }
    require(failed);
    std::cout << "PASS real ResourceLoader metadata + JsonFactory parsing, numeric types, errors, ownership\n";
}
