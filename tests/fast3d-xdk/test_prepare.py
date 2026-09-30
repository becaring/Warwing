import importlib.util
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
import runpy as _shipyard_runpy

SHIPYARD_BASE = _shipyard_runpy.run_path(str(ROOT / "tools/platform_base.py"))["resolve"](ROOT)
sys.path.insert(0,str(ROOT/'tools'))
import prepare_fast3d_xdk as prepare

class SourceContracts(unittest.TestCase):
    def test_triangle_certificate_resolves_only_from_shipyard(self):
        shared=SHIPYARD_BASE / 'sources/fast3d/triangle_pipeline.h'
        self.assertTrue(shared.is_file())
        self.assertFalse((ROOT/'platform/xbox360/cpp-compat/fast3d/triangle_pipeline.h').exists())
        self.assertFalse((ROOT/'scratch/application-xdk/native/source/platform/xbox360/cpp-compat/fast3d/triangle_pipeline.h').exists())
        projected=prepare.lower((ROOT/'upstream/BattleShip/libultraship/include/fast/interpreter.h').read_text(encoding='utf-8-sig'),'interpreter.h')
        self.assertIn('#include "fast3d/triangle_traits.h"',projected)

    def test_triangle_split_depends_on_shipyard(self):
        import triangle_split_projection
        from xbox360_platform import fast3d_triangle_split
        source=(ROOT/'upstream/BattleShip/libultraship/src/fast/interpreter.cpp').read_text(encoding='utf-8-sig')
        with patch.object(fast3d_triangle_split,'transform',side_effect=RuntimeError('shared triangle split reached')):
            with self.assertRaisesRegex(RuntimeError,'shared triangle split reached'):
                triangle_split_projection.transform(source)

    def test_current_interpreter_depends_on_shipyard_opcode_lowerer(self):
        from xbox360_platform import fast3d_opcode
        source=(ROOT/'upstream/BattleShip/libultraship/src/fast/interpreter.cpp').read_text(encoding='utf-8-sig')
        with patch.object(fast3d_opcode,'lower',side_effect=RuntimeError('shared opcode lowerer reached')):
            with self.assertRaisesRegex(RuntimeError,'shared opcode lowerer reached'):
                prepare.opcode_tables(source)

    def test_opcode_tables_keep_every_entry_in_order(self):
        source=(ROOT/'upstream/BattleShip/libultraship/src/fast/interpreter.cpp').read_text(encoding='utf-8-sig')
        original=re.findall(r'static constexpr UcodeHandler (\w+) = \{(.*?)\n\};',source,re.S)
        lowered=prepare.opcode_tables(source)
        self.assertEqual(len(original),6)
        for name,body in original:
            entries=re.findall(r'\{\s*(\w+)\s*,\s*\{\s*("[^"\n]*")\s*,\s*(\w+)\s*\}\s*\}',body)
            new_body=re.search(r'static const UcodeEntry '+name+r'Entries\[\] = \{(.*?)\n\};',lowered,re.S)[1]
            new_entries=re.findall(r'\{\s*(\w+)\s*,\s*("[^"\n]*")\s*,\s*(\w+)\s*\}',new_body)
            self.assertEqual(entries,new_entries,name)
            self.assertIn('UcodeHandler '+name+'('+name+'Entries, sizeof('+name+'Entries)/sizeof('+name+'Entries[0]))',lowered)
    def test_if_initializer_keeps_else_in_declared_scope(self):
        from xbox360_platform.cpp_syntax import lower_if_initializers
        result=lower_if_initializers('if (auto it = find(); it != end()) { yes(it); } else { no(it); }',prepare.PARSER,prepare.walk)
        self.assertEqual(result,'{ auto it = find(); if (it != end()) { yes(it); } else { no(it); } }')
    def test_shared_member_default_extraction_preserves_declaration_order(self):
        from xbox360_platform.cpp_syntax import collect_member_defaults
        source='struct State { int count = 4; float scales[2] = {1.0f, 2.0f}; bool enabled = true; };'
        result,fields=collect_member_defaults(source,'State',prepare.PARSER,prepare.walk)
        self.assertEqual(result,'struct State { int count; float scales[2]; bool enabled; };')
        self.assertEqual([(field.type,field.name,field.value,field.is_array) for field in fields],
                         [('int','count','4',False),('float','scales','{1.0f, 2.0f}',True),('bool','enabled','true',False)])
    def test_member_defaults_depend_on_shared_collector(self):
        with patch.object(prepare,'collect_member_defaults',side_effect=RuntimeError('shared member collector reached')):
            with self.assertRaisesRegex(RuntimeError,'shared member collector reached'):
                prepare.remove_class_defaults('struct State { int count = 4; };','State')
    def test_record_defaults_and_partial_aggregate_arguments(self):
        result=prepare.data_struct_constructors('struct State { std::string name; float scale = 1.0f; int count = 0; };')
        self.assertIn('const float& scale_ = 1.0f',result)
        self.assertIn('const int& count_ = 0',result)
        self.assertIn('scale(scale_)',result)
        self.assertNotIn('float scale = ',result)
    def test_unknown_aggregate_assignment_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'Unaudited aggregate assignment'):
            prepare.lower_aggregate_expressions('unknown = {1,2};')

    def test_disabled_draw_diagnostics_skip_argument_preparation(self):
        source=(ROOT/'upstream/BattleShip/libultraship/src/fast/interpreter.cpp').read_text(encoding='utf-8-sig')
        result=prepare.lower(source,'interpreter.cpp')
        # This distinct loop computes only diagnostic UV bounds, unlike the
        # later real vertex packing loop. Its body must remain intact when on.
        guard='if (!Ssb64RenderDiagEnabled() || !usedTextures[t] || tex_width[t] == 0 || tex_height[t] == 0)'
        self.assertTrue(guard in result,'disabled diagnostic preparation still executes')
        self.assertEqual(result.count('Ssb64RenderDiagLogDraw(metadata, addr, t, uv_tile'),1)

if __name__=='__main__':unittest.main()
