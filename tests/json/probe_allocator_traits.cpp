#include <memory>
// json.hpp's allocation/deallocation path uses this directly.
typedef std::allocator_traits<std::allocator<int> > Traits;
int* AllocateJsonStorage() { std::allocator<int> allocator; return Traits::allocate(allocator, 1); }
