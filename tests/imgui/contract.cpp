#include "imgui.h"
#include "imgui_internal.h"
#include <stdint.h>
#include <stdio.h>
#include <stddef.h>
static uint64_t hash = UINT64_C(14695981039346656037);
static void bytes(const void* address, size_t size) {
    const unsigned char* p = static_cast<const unsigned char*>(address);
    for (size_t i = 0; i < size; ++i) { hash ^= p[i]; hash *= UINT64_C(1099511628211); }
}
template <class T> static void value(const T& item) { bytes(&item, sizeof(item)); }
int main(int argc, char** argv) {
    FILE* output = fopen(argv[1], "wb");
    if (!output) return 2;
    ImGui::CreateContext();
    ImGuiIO& io = ImGui::GetIO(); io.IniFilename = NULL; io.LogFilename = NULL;
    io.DisplaySize = ImVec2(1280, 720); io.DeltaTime = 1.0f / 60.0f;
    unsigned char* atlas; int width, height;
    io.Fonts->GetTexDataAsRGBA32(&atlas, &width, &height);
    bytes(atlas, (size_t)width * height * 4); value(width); value(height);
    io.Fonts->SetTexID(reinterpret_cast<ImTextureID>(0x2000));
    ImGuiMetricsConfig metrics; value(metrics.ShowDrawCmdMesh); value(metrics.ShowDrawCmdBoundingBoxes);
    value(metrics.ShowWindowsRectsType); value(metrics.HighlightMonitorIdx);
    ImGuiTextIndex lines; value(lines.EndOffset);
    value(sizeof(ImGuiSortDirection)); value(sizeof(ImGuiDir)); value(sizeof(ImGuiKey));
    value(sizeof(ImGuiMouseSource)); value(sizeof(ImDrawVert)); value(offsetof(ImDrawVert, col));
    bool checked = true; float slider = 0.25f;
    for (int frame = 0; frame < 3; ++frame) {
        ImGui::NewFrame();
        ImGui::SetNextWindowPos(ImVec2(10, 10), ImGuiCond_Always);
        ImGui::SetNextWindowSize(ImVec2(440, 360), ImGuiCond_Always);
        ImGui::Begin("Contract window");
        ImGui::TextUnformatted("Native GUI path: text, controls, table and image");
        ImGui::Checkbox("Check", &checked); ImGui::SliderFloat("Value", &slider, 0, 1);
        ImGui::Button("Action");
        if (ImGui::BeginTable("Table", 2)) {
            ImGui::TableNextRow(); ImGui::TableNextColumn(); ImGui::TextUnformatted("Left");
            ImGui::TableNextColumn(); ImGui::TextUnformatted("Right"); ImGui::EndTable();
        }
        ImGui::Image(reinterpret_cast<ImTextureID>(0x3000), ImVec2(160, 120));
        ImGui::End();
        ImGui::Render();
        const ImDrawData* data = ImGui::GetDrawData();
        value(data->TotalVtxCount); value(data->TotalIdxCount); value(data->CmdListsCount);
        for (int li = 0; li < data->CmdListsCount; ++li) {
            const ImDrawList* list = data->CmdLists[li];
            for (int vi = 0; vi < list->VtxBuffer.Size; ++vi) {
                const ImDrawVert& v = list->VtxBuffer[vi]; value(v.pos.x); value(v.pos.y); value(v.uv.x); value(v.uv.y); value(v.col);
            }
            bytes(list->IdxBuffer.Data, list->IdxBuffer.Size * sizeof(ImDrawIdx));
            for (int ci = 0; ci < list->CmdBuffer.Size; ++ci) {
                const ImDrawCmd& c = list->CmdBuffer[ci]; value(c.ClipRect); value(c.ElemCount); value(c.VtxOffset); value(c.IdxOffset); value(c.TextureId);
            }
        }
    }
    fprintf(output, "%016llx\n", (unsigned long long)hash);
    fclose(output); ImGui::DestroyContext(); return 0;
}
