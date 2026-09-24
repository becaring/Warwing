#include <type_traits>

// The constructor/get/from_json overload families use function-template
// default arguments after enable_if substitution (json.hpp:834 and adl_serializer).
template<class T, typename std::enable_if<std::is_integral<T>::value, int>::type = 0>
int IntegralOnly(T) { return 1; }
int UseIntegralDefault() { return IntegralOnly(1); }
