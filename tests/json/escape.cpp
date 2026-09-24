#include <cassert>
#include <string>
#ifndef JSON_ASSERT
#define JSON_ASSERT(x) assert(x)
#endif
#include <nlohmann/detail/string_escape.hpp>

// This uses the actual library's leaf implementation, not a replacement parser.
int EscapeContract() {
    const char* cases[] = {"", "plain", "a/b", "~", "~1", "~/~0/", "///~~~", "\xc3\xa9/\xe2\x82\xac"};
    for (size_t i = 0; i < sizeof(cases) / sizeof(cases[0]); ++i) {
        std::string original(cases[i]);
        std::string escaped = nlohmann::detail::escape(original);
        nlohmann::detail::unescape(escaped);
        if (escaped != original) return 1;
    }
    if (nlohmann::detail::escape(std::string("~1/")) != "~01~1") return 2;
    std::string input("~01");
    nlohmann::detail::unescape(input);
    if (input != "~1") return 3;
    std::string embedded("a\0/~", 5);
    std::string escaped = nlohmann::detail::escape(embedded);
    nlohmann::detail::unescape(escaped);
    return escaped == embedded ? 0 : 4;
}
#ifndef JSON_XDK_COMPILE_ONLY
int main() { return EscapeContract(); }
#endif
