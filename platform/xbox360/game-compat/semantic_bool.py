"""Lower C _Bool for the pinned BattleShip C sources.

Every supported store, return and cast is normalized before byte storage is used.
Pointers, arrays, parameters, compound stores and unknown aggregate layouts stop
the pass. It handles only this source set: it is not a general C compiler or a bool typedef.
"""
import re
from typed_generic import parse_view


def lower_booleans(source, parser):
    # tree-sitter-c does not classify _Bool as a builtin in ambiguous casts.
    # Parse an equal-width builtin spelling, retaining original byte locations.
    view = parse_view(source)
    bool_positions = set()
    def builtin(match):
        if match[0] == b'_Bool':
            bool_positions.add(match.start())
            return b'bool '
        return match[0]
    view = re.sub(rb'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|/\*.*?\*/|//[^\n]*|\b_Bool\b', builtin, view, flags=re.S)
    tree = parser.parse(view)
    scopes, bool_functions, bool_fields, all_fields, aggregates = {}, set(), set(), {}, {'IEvent': True}
    type_edits, wraps, declarations = [], set(), []
    scope_types = {'translation_unit', 'compound_statement', 'function_definition', 'for_statement'}
    stats = {'types': 0, 'initializers': 0, 'assignments': 0, 'returns': 0, 'casts': 0, 'aggregate_fields': 0}

    def text(node):
        if node and node.start_byte in bool_positions and node.type in ('primitive_type', 'type_identifier'):
            return b'_Bool'
        return source[node.start_byte:node.end_byte] if node else b''

    def scope(node):
        while node and node.type not in scope_types:
            node = node.parent
        return node

    def kind(node):
        return text(node.child_by_field_name('type')) if node else b''

    def declarators(node):
        return [child for index, child in enumerate(node.children) if node.field_name_for_child(index) == 'declarator']

    def declaration_shape(node):
        flags = set()
        while node and node.type not in ('identifier', 'field_identifier', 'type_identifier'):
            flags.add(node.type)
            node = node.child_by_field_name('declarator')
        return text(node).decode(), flags

    def normalize(node, category):
        while node and node.type == 'initializer_list':
            children = [child for child in node.named_children if child.type not in ('comment', 'preproc_call')]
            if len(children) != 1:
                raise ValueError('Unsupported boolean scalar aggregate initializer')
            node = children[0]
        if not node:
            raise ValueError('Missing boolean value')
        wraps.add((node.start_byte, node.end_byte))
        stats[category] += 1

    def collect(node):
        is_bool = kind(node) == b'_Bool'
        if node.type == 'field_declaration':
            names = [declaration_shape(decl)[0] for decl in declarators(node)]
            for name in names:
                all_fields.setdefault(name, set()).add(is_bool)
            if is_bool:
                if any(declaration_shape(decl)[1] & {'pointer_declarator', 'array_declarator'} for decl in declarators(node)):
                    raise ValueError('Boolean field pointers/arrays are not audited')
                typedef = node.parent.parent.parent
                fields = [child for child in node.parent.named_children if child.type == 'field_declaration']
                parent_name = text(typedef.child_by_field_name('declarator'))
                recognized = (parent_name == b'IEvent' and names == ['Cancelled'] and len(fields) == 1)
                recognized |= (parent_name == b'WindowFocusEvent' and names == ['Focused'] and
                               len(fields) == 2 and kind(fields[0]) == b'IEvent' and
                               [declaration_shape(decl)[0] for decl in declarators(fields[0])] == ['Event'])
                if (not recognized or typedef.type != 'type_definition' or
                        any(child.type == 'bitfield_clause' for child in node.named_children)):
                    raise ValueError('Unrecognized boolean field/aggregate; expected actual IEvent.Cancelled: ' + repr(text(typedef)[:200]))
                bool_fields.update(names)
        if node.type == 'type_definition' and is_bool:
            raise ValueError('Boolean typedef aliases are outside the audited surface')
        if node.type == 'parameter_declaration' and is_bool:
            raise ValueError('Boolean parameters/pointers require call-site conversion auditing')
        if node.type == 'type_definition':
            struct = node.child_by_field_name('type')
            body = struct.child_by_field_name('body') if struct else None
            if body and body.named_children:
                first = body.named_children[0]
                if first.type == 'field_declaration' and kind(first) == b'IEvent':
                    names = [declaration_shape(decl)[0] for decl in declarators(first)]
                    if names != ['Event']:
                        raise ValueError('Unrecognized embedded IEvent member')
                    aggregates[text(node.child_by_field_name('declarator')).decode()] = False
        if node.type in ('declaration', 'function_definition', 'parameter_declaration'):
            owner = scope(node.parent)
            if node.type == 'parameter_declaration':
                parent = node.parent
                while parent and parent.type not in ('function_definition', 'declaration'):
                    parent = parent.parent
                owner = parent if parent and parent.type == 'function_definition' else None
            for decl in declarators(node):
                name, shape = declaration_shape(decl)
                function = 'function_declarator' in shape
                if is_bool:
                    if shape & {'pointer_declarator', 'array_declarator', 'abstract_pointer_declarator', 'abstract_array_declarator'}:
                        raise ValueError('Boolean pointers/arrays are not audited: ' + name)
                    if function:
                        bool_functions.add(name)
                    elif node.type != 'parameter_declaration':
                        declarations.append({'name': name, 'preprocessed_line': node.start_point.row + 1})
                        if decl.type == 'init_declarator':
                            normalize(decl.child_by_field_name('value'), 'initializers')
                if owner and name:
                    scopes.setdefault(owner.id, {}).setdefault(name, []).append((node.start_byte, is_bool and not function))
        if node.type in ('primitive_type', 'type_identifier') and text(node) == b'_Bool':
            parent = node.parent
            if parent.type == 'type_descriptor':
                if parent.child_by_field_name('declarator'):
                    raise ValueError('Boolean pointer/array cast is not audited')
                expression = parent.parent
                if expression.type == 'cast_expression':
                    normalize(expression.child_by_field_name('value'), 'casts')
                elif expression.type != 'sizeof_expression':
                    raise ValueError('Unrecognized _Bool type context: ' + expression.type)
            type_edits.append((node.start_byte, node.start_byte + 5, b'unsigned char'))
            stats['types'] += 1
        for child in node.named_children:
            collect(child)

    collect(tree.root_node)
    if {edit[0] for edit in type_edits} != bool_positions:
        raise ValueError('Unresolved _Bool token/context')

    def is_bool_lvalue(node):
        if not node:
            return False
        if node.type == 'parenthesized_expression':
            return is_bool_lvalue(node.named_children[0])
        if node.type == 'identifier':
            owner = scope(node.parent)
            while owner:
                candidates = [entry for entry in scopes.get(owner.id, {}).get(text(node).decode(), [])
                              if entry[0] <= node.start_byte]
                if candidates:
                    return candidates[-1][1]
                owner = scope(owner.parent)
        if node.type == 'field_expression':
            field = text(node.child_by_field_name('field')).decode()
            if field in bool_fields:
                if all_fields[field] != {True}:
                    raise ValueError('Ambiguous boolean field type: ' + field)
                return True
        return False

    def check(node):
        if node.type == 'assignment_expression' and is_bool_lvalue(node.child_by_field_name('left')):
            if text(node.child_by_field_name('operator')) != b'=':
                raise ValueError('Compound boolean stores are not audited')
            normalize(node.child_by_field_name('right'), 'assignments')
        if node.type == 'update_expression' and is_bool_lvalue(node.child_by_field_name('argument')):
            raise ValueError('Increment/decrement of boolean storage is not audited')
        if node.type == 'pointer_expression' and text(node.child_by_field_name('operator')) == b'&':
            if is_bool_lvalue(node.child_by_field_name('argument')):
                raise ValueError('Escaping boolean storage pointer is not audited')
        if node.type == 'return_statement':
            parent = node.parent
            while parent and parent.type != 'function_definition':
                parent = parent.parent
            if parent and kind(parent) == b'_Bool':
                values = [child for child in node.named_children if child.type != 'comment']
                if len(values) != 1:
                    raise ValueError('Boolean return without one scalar value')
                normalize(values[0], 'returns')
        if node.type == 'declaration' and kind(node).decode() in aggregates:
            direct = aggregates[kind(node).decode()]
            for decl in declarators(node):
                _, shape = declaration_shape(decl)
                if 'array_declarator' in shape:
                    raise ValueError('Arrays containing boolean event storage are not audited')
                if decl.type != 'init_declarator':
                    continue
                value = decl.child_by_field_name('value')
                if not value or value.type != 'initializer_list':
                    raise ValueError('Unknown boolean event aggregate initializer')
                children = [child for child in value.named_children if child.type not in ('comment', 'preproc_call')]
                if not children:
                    raise ValueError('Empty boolean event initializer')
                if direct:
                    if len(children) != 1:
                        raise ValueError('IEvent shape changed')
                    normalize(children[0], 'aggregate_fields')
                else:
                    normalize(children[0], 'aggregate_fields')
                    if kind(node) == b'WindowFocusEvent' and len(children) > 1:
                        if len(children) != 2:
                            raise ValueError('WindowFocusEvent initializer shape changed')
                        normalize(children[1], 'aggregate_fields')
        for child in node.named_children:
            check(child)

    check(tree.root_node)
    inserts = {}
    for start, end in wraps:
        inserts[start] = inserts.get(start, b'') + b'!!('
        inserts[end] = b')' + inserts.get(end, b'')
    edits = type_edits + [(position, position, value) for position, value in inserts.items()]
    for start, end, replacement in sorted(edits, reverse=True):
        source = source[:start] + replacement + source[end:]
    return source, dict(stats, declarations=declarations, boolean_functions=sorted(bool_functions),
                        boolean_fields=sorted(bool_fields), scope='audited scalar and IEvent surface only')
