from pathlib import Path
import sys,unittest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import prepare_gui_widgets_xdk as prepare
from prepare_prism_xdk import PARSER,walk,field,tx

def calls(text,name):
    return [n for n in walk(PARSER.parse(text.encode()).root_node) if n.type=='call_expression' and tx(field(n,'function')).endswith(name)]

class ProjectionContracts(unittest.TestCase):
    def test_every_actual_command_record_keeps_metadata_and_order(self):
        original=(prepare.UP/'src/ship/window/gui/ConsoleWindow.cpp').read_text(encoding='utf-8-sig')
        projected=prepare.lower_source(original,'ConsoleWindow.cpp')
        before=calls(original,'->AddCommand');after=calls(projected,'->AddCommand')
        self.assertEqual(len(before),7);self.assertEqual(len(after),7)
        for old,new in zip(before,after):
            old_args=field(old,'arguments').named_children;new_args=field(new,'arguments').named_children
            self.assertEqual(tx(old_args[0]),tx(new_args[0]))
            fields=old_args[1].named_children
            self.assertIn('handler = '+tx(fields[0]),tx(new_args[1]))
            self.assertIn('description = '+tx(fields[1]),tx(new_args[1]))
            old_records=[tuple(tx(n) for n in record.named_children) for record in fields[2].named_children] if len(fields)==3 else []
            new_records=[tuple(tx(n) for n in field(call,'arguments').named_children) for call in calls(tx(new_args[1]),'CommandArgument')]
            self.assertEqual(old_records,new_records)

    def test_debugger_lambda_every_call_gets_explicit_default(self):
        original=(prepare.UP/'src/libultraship/window/gui/GfxDebuggerWindow.cpp').read_text(encoding='utf-8-sig')
        projected=prepare.lower_source(original,'GfxDebuggerWindow.cpp')
        before=calls(original,'nodeWithText');after=calls(projected,'nodeWithText')
        self.assertEqual(len(before),len(after))
        for old,new in zip(before,after):
            oldargs=[tx(n) for n in field(old,'arguments').named_children]
            newargs=[tx(n) for n in field(new,'arguments').named_children]
            self.assertEqual(oldargs+(['nullptr'] if len(oldargs)==2 else []),newargs)

    def test_const_member_vectors_retain_exact_element_expressions(self):
        original=(prepare.UP/'include/ship/window/gui/ConsoleWindow.h').read_text(encoding='utf-8-sig')
        projected=prepare.lower_header(original,'ConsoleWindow.h')
        old={}
        for n in walk(PARSER.parse(original.encode()).root_node):
            if n.type=='field_declaration' and tx(n).startswith('const std::vector'):
                old[tx(field(n,'declarator'))]=[tx(v) for v in field(n,'default_value').named_children if v.type!='comment']
        self.assertEqual(len(old),3)
        for name,values in old.items():
            fn=next(n for n in walk(PARSER.parse(projected.encode()).root_node) if n.type=='function_definition' and tx(field(n,'declarator')).startswith('Build_'+name+'('))
            arr=next(n for n in walk(fn) if n.type=='initializer_list')
            self.assertEqual(values,[tx(v) for v in arr.named_children if v.type!='comment'])

if __name__=='__main__':unittest.main()
