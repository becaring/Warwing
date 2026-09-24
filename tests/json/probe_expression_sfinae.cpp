#include <type_traits>
#include <utility>

// One fixed-arity immediate-expression requirement underlying
// detail/meta/type_traits.hpp:103-110, with packs/aliases already removed.
struct Present { static int to_json(int); };
struct Absent {};
template<class T> decltype(T::to_json(0), std::true_type()) Detect(int);
template<class T> std::false_type Detect(...);
typedef decltype(Detect<Present>(0)) PresentResult;
typedef decltype(Detect<Absent>(0)) AbsentResult;
typedef char PresentIsDetected[PresentResult::value ? 1 : -1];
typedef char MissingIsSubstitutionFailure[!AbsentResult::value ? 1 : -1];
