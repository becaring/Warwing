// Actual ConsoleVariable legacy migration, with test-only Context supplied separately.
#include "ship/config/ConsoleVariable.h"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
void InstallConfigFixture(const std::string &path);
static void Check(bool value, const char *message) {
    if (!value)
        throw std::runtime_error(message);
}
int main(int argc, char **argv) {
    if (argc != 2)
        return 2;
    try {
        const std::string path = argv[1];
        std::ofstream seed(path);
        seed << "{\"CVars\":{}}";
        seed.close();
        const std::filesystem::path legacy = std::filesystem::path(path).parent_path() / "cvars.cfg";
        std::ofstream old(legacy);
        old << "legacyInt = 123\nlegacyFloat = 1.25\nlegacyString = \"migration\"\nlegacyColor = #11223344\n";
        old.close();
        InstallConfigFixture(path);
        Ship::ConsoleVariable vars;
        Check(vars.GetInteger("legacyInt", 0) == 123, "legacy integer");
        Check(vars.GetFloat("legacyFloat", 0) == 1.25f, "legacy float");
        Check(std::string(vars.GetString("legacyString", "")) == "migration\r",
              "inherited legacy CRLF string retention");
        Color_RGBA8 zero = {};
        Color_RGBA8 color = vars.GetColor("legacyColor", zero);
        Check(color.r == 17 && color.g == 34 && color.b == 51 && color.a == 68, "legacy color");
        Check(!std::filesystem::exists(legacy), "legacy migration removed only test fixture");
        vars.Save();
        vars.Load();
        Check(vars.GetInteger("legacyInt", 0) == 123, "legacy save/reload");
        std::ifstream result(path, std::ios::binary);
        std::cout << result.rdbuf() << "\nlegacy migration=ok\n";
        return 0;
    } catch (const std::exception &e) {
        std::cerr << e.what() << '\n';
        return 1;
    }
}
