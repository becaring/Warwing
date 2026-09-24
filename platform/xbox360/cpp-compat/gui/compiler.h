#pragma once
#include <memory>
namespace Smash360Gui {
// C++17 reinterpret_pointer_cast's specified aliasing constructor preserves the
// original control block, including alias pointers whose owner is empty.
template<class T, class U>
std::shared_ptr<T> ReinterpretPointerCast(const std::shared_ptr<U>& owner) {
    return std::shared_ptr<T>(owner, reinterpret_cast<T*>(owner.get()));
}
}
