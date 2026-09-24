// Real Config methods and files. Not a mock Config or application boot harness.
#include "ship/config/Config.h"
#include <fstream>
#include <iostream>
#include <sstream>
#include <cmath>
#include <stdexcept>

static void check(bool test, const char* message) {
    if (!test) throw std::runtime_error(message);
}
static std::string bytes(const std::string& path) {
    std::ifstream stream(path, std::ios::binary);
    return std::string(std::istreambuf_iterator<char>(stream), std::istreambuf_iterator<char>());
}

int main(int argc, char** argv) {
    if (argc != 2) return 2;
    try {
        const std::string path = argv[1];
        std::ofstream seed(path);
        seed << "{\"CVars\":{\"f\":1.0,\"i\":-7,\"u\":42,\"b\":true,\"s\":\"hello\"},\"arr\":[1,2]}";
        seed.close();
        Ship::Config config(path);
        check(config.GetFloat("CVars.f", 9) == 1, "float typing");
        check(config.GetFloat("CVars.i", 9) == 9, "integer must not become float config");
        check(config.GetInt("CVars.i") == -7, "signed int");
        check(config.GetUInt("CVars.u") == 42, "unsigned int");
        check(config.GetBool("CVars.b"), "bool");
        check(config.GetString("CVars.s") == "hello", "string");
        // Pinned Nested skips a missing dotted segment and returns its parent.
        // Preserve this inherited behavior; don't fix Config in a JSON port.
        check(config.Contains("CVars.missing"), "inherited dotted missing-key behavior");
        check(config.GetString("CVars.missing", "fallback") == "fallback", "missing scalar default");
        config.SetFloat("CVars.f", 1.0f);
        config.SetFloat("CVars.zero", -0.0f);
        config.SetInt("CVars.i", -21);
        config.SetUInt("CVars.u", 0xffffffffu);
        config.SetString("CVars.s", "tab\tline\n\xC3\xA9");
        config.Copy("CVars.s", "CVars.copy");
        config.SetBool("CVars.b", false);
        config.Save();
        const std::string saved = bytes(path);
        config.Reload();
        check(config.GetFloat("CVars.f", 9) == 1, "1.0 must retain floating type across save");
        check(std::signbit(config.GetFloat("CVars.zero", 9)), "negative zero roundtrip");
        check(config.GetUInt("CVars.u") == 0xffffffffu, "unsigned range");
        check(config.GetString("CVars.copy") == config.GetString("CVars.s"), "copy");
        check(!config.GetBool("CVars.b", true), "false");
        config.SetInt("collision", 1);
        config.SetInt("collision.child", 2);
        config.Save();
        check(bytes(path) == saved, "failed unflatten must not truncate actual config");
        config.Reload();
        config.Erase("CVars.copy");
        config.Save();
        check(config.GetString("CVars.copy", "absent") == "absent", "erase");
        std::cout << bytes(path) << "\nPASS actual Ship::Config persistence/type/error contract\n";
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "FAIL " << e.what() << '\n';
        return 1;
    }
}
