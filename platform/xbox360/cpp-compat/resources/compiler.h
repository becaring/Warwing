#ifndef SMASH360_RESOURCES_COMPILER_H
#define SMASH360_RESOURCES_COMPILER_H
#include "binary/compat.h"
#include "../async/future.h"
#include "../thread-pool/native_support.h"
#include "filesystem/filesystem.h"
#include <list>
#include <string>
namespace Smash360Resources {
template<class Range> auto Begin(Range& value)->decltype(value.begin()){return value.begin();}
template<class Range> auto End(Range& value)->decltype(value.end()){return value.end();}
inline xbox_compat::filesystem::directory_iterator Begin(xbox_compat::filesystem::directory_iterator& v){return xbox_compat::filesystem::begin(v);}
inline xbox_compat::filesystem::directory_iterator End(xbox_compat::filesystem::directory_iterator& v){return xbox_compat::filesystem::end(v);}
inline std::list<std::string> OneMask(const std::string& value) {
    std::list<std::string> result; result.push_back(value); return result;
}
}
#endif
