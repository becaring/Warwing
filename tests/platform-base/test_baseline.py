"""The generated Smash project must consume the pinned shared Xbox base."""

from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
import prepare_application_xdk as app
import vertex_packing_projection as vertices


class PlatformBaseTests(unittest.TestCase):
    def test_project_stage_contains_literal_include_dependencies(self):
        for name in ('platform/xbox360/cpp-compat/prism/prism_shader_builder.h',
                     'scratch/json-xdk/backend-generated/json/generated/ordered_json.cpp'):
            with self.subTest(name=name):
                self.assertTrue((ROOT/'scratch/application-xdk/native/source'/name).is_file())
        xml = ET.parse(ROOT/'platform/xbox360/Smash360.vcxproj').getroot()
        ns = '{' + app.XML + '}'
        includes = xml.findtext('.//' + ns + 'ItemDefinitionGroup/' + ns +
                                'ClCompile/' + ns + 'AdditionalIncludeDirectories')
        self.assertIn('$(SmashSourceRoot)platform\\xbox360\\cpp-compat\\prism', includes)

    def test_shared_base_and_cpp_policy(self):
        self.assertEqual(vertices.BASE, app.PLATFORM_BASE)
        xml = ET.parse(ROOT / 'platform/xbox360/Smash360.vcxproj').getroot()
        ns = '{' + app.XML + '}'
        definition = xml.find('.//' + ns + 'ItemDefinitionGroup/' + ns + 'ClCompile')
        self.assertEqual(definition.findtext(ns + 'FunctionLevelLinking'), 'true')
        self.assertEqual(definition.findtext(ns + 'FloatingPointModel'), 'Precise')

    def test_direct_graphics_and_gamepad_inputs(self):
        xml = ET.parse(ROOT / 'platform/xbox360/Smash360.vcxproj').getroot()
        ns = '{' + app.XML + '}'
        includes = {item.attrib['Include'] for item in xml.findall('.//' + ns + 'ClCompile[@Include]')}
        self.assertIn('$(ShipyardRoot)\\sources\\async\\native.cpp', includes)
        self.assertNotIn('$(SmashSourceRoot)platform\\xbox360\\cpp-compat\\async\\native.cpp', includes)
        self.assertFalse((ROOT / 'platform/xbox360/cpp-compat/async/native.cpp').exists())
        self.assertFalse((ROOT / 'scratch/application-xdk/native/source/platform/xbox360/cpp-compat/async/native.cpp').exists())
        self.assertIn('$(ShipyardRoot)\\sources\\audio\\PcmBufferPool.cpp', includes)
        self.assertNotIn('$(SmashSourceRoot)platform\\xbox360\\audio\\PcmBufferPool.cpp', includes)
        self.assertFalse((ROOT / 'platform/xbox360/audio/PcmBufferPool.cpp').exists())
        self.assertFalse((ROOT / 'scratch/application-xdk/native/source/platform/xbox360/audio/PcmBufferPool.cpp').exists())
        self.assertIn('$(ShipyardRoot)\\sources\\audio\\XAudio2AudioPlayer.cpp', includes)
        self.assertNotIn('$(SmashSourceRoot)platform\\xbox360\\audio\\XAudio2AudioPlayer.cpp', includes)
        self.assertFalse((ROOT / 'platform/xbox360/audio/XAudio2AudioPlayer.cpp').exists())
        self.assertFalse((ROOT / 'platform/xbox360/audio/XAudio2AudioPlayer.h').exists())
        self.assertIn('$(ShipyardRoot)\\sources\\clock\\chrono.cpp', includes)
        self.assertNotIn('$(SmashSourceRoot)platform\\xbox360\\cpp-compat\\chrono\\chrono.cpp', includes)
        self.assertFalse((ROOT / 'platform/xbox360/cpp-compat/chrono/chrono.cpp').exists())
        self.assertIn('$(ShipyardRoot)\\sources\\crt\\format.cpp', includes)
        self.assertNotIn('$(SmashSourceRoot)platform\\xbox360\\cpp-compat\\crt\\snprintf.cpp', includes)
        self.assertFalse((ROOT / 'platform/xbox360/cpp-compat/crt/snprintf.cpp').exists())
        self.assertFalse((ROOT / 'scratch/application-xdk/native/source/platform/xbox360/cpp-compat/crt/snprintf.cpp').exists())
        self.assertFalse((ROOT / 'scratch/crt-xdk/include/smash360_snprintf.h').exists())
        self.assertIn('$(ShipyardRoot)\\sources\\graphics\\shader_lower.cpp', includes)
        self.assertIn('$(ShipyardRoot)\\sources\\graphics\\shader_provider.cpp', includes)
        self.assertIn('$(ShipyardRoot)\\sources\\imgui\\imgui_xenos.cpp', includes)
        self.assertIn('$(ShipyardRoot)\\sources\\imgui\\platform_frame.cpp', includes)
        self.assertIn('$(SmashSourceRoot)platform\\xbox360\\imgui\\platform_adapter.cpp', includes)
        self.assertNotIn('$(SmashSourceRoot)platform\\xbox360\\imgui\\platform_frame.cpp', includes)
        self.assertFalse((ROOT / 'platform/xbox360/imgui/platform_frame.cpp').exists())
        self.assertFalse((ROOT / 'scratch/application-xdk/native/source/platform/xbox360/imgui/platform_frame.cpp').exists())
        for name in ('physical.cpp', 'xinput.cpp'):
            self.assertIn('$(ShipyardRoot)\\sources\\input\\'+name, includes)
            self.assertNotIn('$(SmashSourceRoot)platform\\xbox360\\input\\'+name, includes)
            self.assertFalse((ROOT / 'platform/xbox360/input' / name).exists())
            self.assertFalse((ROOT / 'scratch/application-xdk/native/source/platform/xbox360/input' / name).exists())
        self.assertFalse((ROOT / 'platform/xbox360/input/physical.h').exists())
        self.assertNotIn('$(SmashSourceRoot)scratch\\imgui-xdk\\imgui_xenos.cpp', includes)
        self.assertFalse((ROOT / 'scratch/application-xdk/native/source/platform/xbox360/graphics/shader_lower.cpp').exists())
        self.assertFalse((ROOT / 'scratch/application-xdk/native/source/platform/xbox360/graphics/shader_lower.h').exists())
        self.assertFalse((ROOT / 'scratch/application-xdk/native/source/scratch/imgui-xdk/gamepad_bindings.inc').exists())
        self.assertFalse((ROOT / 'scratch/application-xdk/native/source/scratch/imgui-xdk/imgui_xenos.cpp').exists())
        self.assertFalse((ROOT / 'scratch/imgui-xdk/imgui_xenos.cpp').exists())
        definitions = xml.find('.//' + ns + 'ItemDefinitionGroup/' + ns + 'ClCompile')
        paths = definitions.findtext(ns + 'AdditionalIncludeDirectories')
        self.assertIn('$(ShipyardRoot);', paths)
        self.assertIn('$(ShipyardRoot)\\sources\\graphics', paths)
        self.assertIn('$(ShipyardRoot)\\sources\\imgui', paths)
        self.assertIn('$(ShipyardRoot)\\sources', paths)


if __name__ == '__main__':
    unittest.main()
