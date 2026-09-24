#include "json/generated/lexer.hpp"
#include "json/generated/to_chars.hpp"
struct LexerTypes { typedef long long number_integer_t; typedef unsigned long long number_unsigned_t; typedef double number_float_t; typedef std::string string_t; };
void Test(const std::string& text) {
 Smash360JsonAlgorithm::detail::StringInput input(text);
 Smash360JsonAlgorithm::detail::lexer<LexerTypes, Smash360JsonAlgorithm::detail::StringInput> lexer(std::move(input));
 lexer.scan(); char out[64]; Smash360JsonAlgorithm::detail::to_chars(out,out+64,lexer.get_number_float());
}
