#pragma once
#include <cstddef>
#include <map>
#include <string>
#include <vector>

// Candidate compiler-boundary facts for the default basic_json configuration.
// The primary template is intentionally incomplete: an unreviewed type cannot
// silently become a valid (or invalid) conversion. This does not implement JSON.
NLOHMANN_JSON_NAMESPACE_BEGIN
namespace detail {
template<class T> class iteration_proxy;
template<class T> class iteration_proxy_value;
template<class T> class iter_impl;
template<class T> class json_ref;
}
template<class T> class json_pointer;
NLOHMANN_JSON_NAMESPACE_END

namespace Smash360Json {
template<bool From, bool NonDefault, bool To, bool Get> struct ConversionFacts {
    enum { from_json = From, non_default_from_json = NonDefault, to_json = To, getable = Get };
};
template<class Json, class T, bool IsEnum = __is_enum(T)> struct RuntimeConversion;
// No custom enum ADL hooks exist in the audited runtime, and the pinned default
// keeps enum serialization enabled. The actual from_json/to_json enum bodies
// still perform the conversion; these are only their compiler-selection facts.
template<class Json, class T> struct RuntimeConversion<Json, T, true> : ConversionFacts<true, false, true, true> {};
#define SMASH360_JSON_SCALAR(Type) \
    template<class Json> struct RuntimeConversion<Json, Type> : ConversionFacts<true, false, true, true> {}
SMASH360_JSON_SCALAR(bool);
SMASH360_JSON_SCALAR(char);
SMASH360_JSON_SCALAR(signed char);
SMASH360_JSON_SCALAR(unsigned char);
SMASH360_JSON_SCALAR(short);
SMASH360_JSON_SCALAR(unsigned short);
SMASH360_JSON_SCALAR(int);
SMASH360_JSON_SCALAR(unsigned int);
SMASH360_JSON_SCALAR(long);
SMASH360_JSON_SCALAR(unsigned long);
SMASH360_JSON_SCALAR(long long);
SMASH360_JSON_SCALAR(unsigned long long);
SMASH360_JSON_SCALAR(float);
SMASH360_JSON_SCALAR(double);
SMASH360_JSON_SCALAR(long double);
SMASH360_JSON_SCALAR(std::string);
SMASH360_JSON_SCALAR(std::nullptr_t);
#undef SMASH360_JSON_SCALAR
template<class Json> struct RuntimeConversion<Json, Json, false> : ConversionFacts<false, false, false, true> {};
template<class Json> struct RuntimeConversion<Json, const char*> : ConversionFacts<false, false, true, false> {};
template<class Json> struct RuntimeConversion<Json, char*> : ConversionFacts<false, false, true, false> {};
template<class Json, size_t N> struct RuntimeConversion<Json, char[N], false> : ConversionFacts<true, false, true, false> {};
template<class Json, size_t N> struct RuntimeConversion<Json, const char[N], false> : ConversionFacts<true, false, true, false> {};
template<class Json, class T, class Allocator> struct RuntimeConversion<Json, std::vector<T, Allocator>, false>
    : ConversionFacts<RuntimeConversion<Json, T>::getable, false,
                      RuntimeConversion<Json, T>::getable, RuntimeConversion<Json, T>::getable> {};
template<class Json, class T, class Compare, class Allocator>
struct RuntimeConversion<Json, std::map<std::string, T, Compare, Allocator>, false>
    : ConversionFacts<RuntimeConversion<Json, T>::getable, false,
                      RuntimeConversion<Json, T>::getable, RuntimeConversion<Json, T>::getable> {};
// Known actual-library candidates. Values are compared with the unmodified
// 3.12.0 type traits in tests/json/trait_facts.cpp, including const distinctions.
template<class Json, class T> struct RuntimeConversion<Json, nlohmann::detail::iter_impl<T>, false> : ConversionFacts<false, false, false, false> {};
template<class Json> struct RuntimeConversion<Json, nlohmann::detail::iteration_proxy<nlohmann::detail::iter_impl<Json> >, false> : ConversionFacts<false, false, true, false> {};
template<class Json> struct RuntimeConversion<Json, nlohmann::detail::iteration_proxy<nlohmann::detail::iter_impl<const Json> >, false> : ConversionFacts<false, false, false, false> {};
template<class Json> struct RuntimeConversion<Json, nlohmann::detail::iteration_proxy_value<nlohmann::detail::iter_impl<Json> >, false> : ConversionFacts<false, false, true, false> {};
template<class Json, class T> struct RuntimeConversion<Json, nlohmann::json_pointer<T>, false> : ConversionFacts<false, false, true, false> {};
template<class Json, class T> struct RuntimeConversion<Json, nlohmann::detail::json_ref<T>, false> : ConversionFacts<false, false, false, false> {};
} // namespace Smash360Json
