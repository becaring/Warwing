#include "ship/config/ConsoleVariable.h"
#include <fstream>
#include <iostream>
#include <stdexcept>

void InstallConfigFixture(const std::string& path);
static void check(bool test, const char* message) {
    if (!test) throw std::runtime_error(message);
}
int main(int argc, char** argv) {
    if (argc != 2) return 2;
    try {
        const std::string path = argv[1];
        std::ofstream seed(path);
        seed << "{\"CVars\":{\"integer\":-9,\"float\":1.0,\"truth\":true,\"string\":\"text\","
                "\"group\":{\"nested\":27},\"rgba\":{\"Type\":\"RGBA\",\"R\":255,\"G\":7,\"B\":128,\"A\":9},"
                "\"rgb\":{\"Type\":\"RGB\",\"R\":4,\"G\":5,\"B\":6}}}";
        seed.close();
        InstallConfigFixture(path);
        Ship::ConsoleVariable vars;
        check(vars.GetInteger("integer", 0) == -9, "integer CVar");
        check(vars.GetInteger("truth", 0) == 1, "boolean CVar coerces to integer");
        check(vars.GetFloat("float", 2) == 1, "floating CVar remains float");
        check(vars.GetInteger("group.nested", 0) == 27, "nested CVar traversal");
        check(std::string(vars.GetString("string", "")) == "text", "string CVar");
        Color_RGBA8 empty = {};
        Color_RGBA8 rgba = vars.GetColor("rgba", empty);
        check(rgba.r == 255 && rgba.g == 7 && rgba.b == 128 && rgba.a == 9, "RGBA CVar");
        Color_RGB8 empty24 = {};
        Color_RGB8 rgb = vars.GetColor24("rgb", empty24);
        check(rgb.r == 4 && rgb.g == 5 && rgb.b == 6, "RGB CVar");
        vars.SetInteger("integer", 123);
        vars.SetFloat("float", 1.0f);
        vars.SetString("string", "persisted");
        rgba.a = 255;
        vars.SetColor("rgba", rgba);
        vars.Save();
        vars.Load();
        check(vars.GetFloat("float", 2) == 1, "floating CVar save/reload");
        check(vars.GetInteger("integer", 0) == 123, "integer CVar save/reload");
        check(std::string(vars.GetString("string", "")) == "persisted", "string CVar save/reload");
        check(vars.GetColor("rgba", empty).a == 255, "RGBA save/reload");
        vars.ClearVariable("string");
        vars.Save();
        vars.Load();
        check(std::string(vars.GetString("string", "absent")) == "absent", "string CVar removal");
        std::ifstream result(path, std::ios::binary);
        std::cout << result.rdbuf() << "\nPASS actual ConsoleVariable/Config JSON contract\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAIL " << error.what() << '\n';
        return 1;
    }
}
