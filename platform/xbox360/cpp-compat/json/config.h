#pragma once

// Select the same named ABI namespace through upstream's supported macro
// customization points. XDK lacks inline namespace syntax; a using-directive
// makes the configured namespace's members visible at nlohmann:: instead.
// Every TU consuming generated JSON headers must include this first.
#include <nlohmann/detail/abi_macros.hpp>
#undef NLOHMANN_JSON_NAMESPACE_BEGIN
#define NLOHMANN_JSON_NAMESPACE_BEGIN \
    namespace nlohmann { namespace NLOHMANN_JSON_NAMESPACE_CONCAT( \
        NLOHMANN_JSON_ABI_TAGS, NLOHMANN_JSON_NAMESPACE_VERSION) {
#undef NLOHMANN_JSON_NAMESPACE_END
#define NLOHMANN_JSON_NAMESPACE_END \
    } using namespace NLOHMANN_JSON_NAMESPACE_CONCAT( \
        NLOHMANN_JSON_ABI_TAGS, NLOHMANN_JSON_NAMESPACE_VERSION); }
