#include <type_traits>

// A deliberately rejected, naive fixed-arity lowering of detected.hpp and
// type_traits.hpp's mapped_type_t. Instantiating Op<Absent> moves the failure
// out of the alias's immediate substitution context. It must not be shipped.
template<class T> struct MakeVoid { typedef void type; };
template<class T> struct MappedType { typedef typename T::mapped_type type; };
template<class T, class = void> struct HasMapped : std::false_type {};
template<class T> struct HasMapped<T, typename MakeVoid<typename MappedType<T>::type>::type> : std::true_type {};
struct Present { typedef int mapped_type; };
struct Absent {};
typedef char PresentIsDetected[HasMapped<Present>::value ? 1 : -1];
typedef char MissingMustNotBeHardError[!HasMapped<Absent>::value ? 1 : -1];
