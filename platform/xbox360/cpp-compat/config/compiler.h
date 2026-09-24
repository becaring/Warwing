#ifndef SMASH360_CONFIG_COMPILER_H
#define SMASH360_CONFIG_COMPILER_H
#include <iterator>
#include "binary/compat.h"
#include "config/string_view.h"
#include "filesystem/filesystem.h"
namespace Smash360Config {
// Member begin/end preserve mutable/const/ref-qualified binding for reached containers.
template<class Range> auto Begin(Range& value)->decltype(value.begin()){return value.begin();}
template<class Range> auto End(Range& value)->decltype(value.end()){return value.end();}
template<class T,size_t N>T* Begin(T(&value)[N]){return value;}
template<class T,size_t N>T* End(T(&value)[N]){return value+N;}
inline xbox_compat::filesystem::recursive_directory_iterator Begin(xbox_compat::filesystem::recursive_directory_iterator& value){return xbox_compat::filesystem::begin(value);}
inline xbox_compat::filesystem::recursive_directory_iterator End(xbox_compat::filesystem::recursive_directory_iterator& value){return xbox_compat::filesystem::end(value);}
}
#endif
