#include <nlohmann/json.hpp>
#include <iostream>
#include <vector>
#include <map>
using nlohmann::json;
template <class T> void Facts(const char *name) {
    std::cout << name << ':' << nlohmann::detail::has_from_json<json, T>::value
              << nlohmann::detail::has_non_default_from_json<json, T>::value
              << nlohmann::detail::has_to_json<json, T>::value << nlohmann::detail::is_getable<json, T>::value << '\n';
}
enum TestEnum { First, Second };
int main() {
#define FACT(Type) Facts<Type>(#Type)
    FACT(bool);
    FACT(char);
    FACT(signed char);
    FACT(unsigned char);
    FACT(short);
    FACT(unsigned short);
    FACT(int);
    FACT(unsigned int);
    FACT(long);
    FACT(unsigned long);
    FACT(long long);
    FACT(unsigned long long);
    FACT(float);
    FACT(double);
    FACT(long double);
    FACT(std::string);
    FACT(std::nullptr_t);
    FACT(json);
    FACT(TestEnum);
    FACT(const char *);
    FACT(char *);
    FACT(char[5]);
    FACT(const char[5]);
    FACT(std::vector<int>);
    FACT(std::vector<std::string>);
    FACT(std::vector<json>);
    Facts<std::map<std::string, json>>("map<string,json>");
    FACT(nlohmann::detail::iteration_proxy<json::iterator>);
    FACT(nlohmann::detail::iteration_proxy<json::const_iterator>);
    FACT(json::iterator);
    FACT(json::const_iterator);
    FACT(json::json_pointer);
    FACT(nlohmann::detail::json_ref<json>);
    FACT(nlohmann::detail::iteration_proxy_value<json::iterator>);
}
