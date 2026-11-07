"""Resolve only BattleShip PORT_TOKEN_VALUE's C11 generic selection.

The caller supplies a tree-sitter C parser. Types come from declarations
and lexical scopes. Unknown, anonymous-member, function-pointer and ambiguous
expressions are left untouched and reported; there is no default cast.
"""
import re


def parse_view(source):
    # #line may legally interrupt an initializer/expression after preprocessing;
    # tree-sitter does not accept directives at every such grammar position.
    # Mask only in its view; byte offsets and emitted mappings stay unchanged.
    return re.sub(rb'^#line[^\r\n]*', lambda match: b' ' * len(match[0]), source, flags=re.M)


def lower_port_generics(source, parser):
    tree = parser.parse(parse_view(source))
    aliases, fields, scopes = {}, {}, {}
    generic_nodes = []
    scope_kinds = {'translation_unit', 'function_definition', 'compound_statement', 'for_statement'}

    def text(node):
        return source[node.start_byte:node.end_byte].decode('utf-8', errors='replace') if node else ''

    def scope(node):
        while node and node.type not in scope_kinds:
            node = node.parent
        return node

    def base_type(node):
        if node is None:
            return None
        if node.type in ('type_identifier', 'primitive_type', 'sized_type_specifier'):
            return (text(node), 0)
        if node.type in ('struct_specifier', 'union_specifier'):
            name = node.child_by_field_name('name')
            return ((node.type.split('_')[0] + ' ' + text(name)) if name else
                    '@anonymous:' + str(node.start_byte), 0)
        if node.type == 'enum_specifier':
            return ('int', 0)
        return None

    def declarator(node, base):
        if node is None or base is None:
            return None, None, False
        depth, is_function = base[1], False
        while node.type not in ('identifier', 'type_identifier', 'field_identifier'):
            if node.type in ('pointer_declarator', 'array_declarator',
                             'abstract_pointer_declarator', 'abstract_array_declarator'):
                depth += 1
            elif node.type == 'function_declarator':
                is_function = True
            elif node.type not in ('init_declarator', 'parenthesized_declarator'):
                return None, None, False
            node = node.child_by_field_name('declarator')
            if node is None:
                return None, (base[0], depth), is_function
        return text(node), (base[0], depth), is_function

    def declarators(node):
        return [child for index, child in enumerate(node.children)
                if node.field_name_for_child(index) == 'declarator']

    def visit(node):
        if node.type == 'generic_expression':
            generic_nodes.append(node)
        if node.type in ('struct_specifier', 'union_specifier'):
            body = node.child_by_field_name('body')
            if body:
                owner = base_type(node)[0]
                members = fields.setdefault(owner, {})
                def collect_members(body):
                  for field in body.named_children:
                    if field.type == 'field_declaration':
                        field_type = field.child_by_field_name('type')
                        base = base_type(field_type)
                        if not declarators(field) and field_type and field_type.type in ('struct_specifier', 'union_specifier'):
                            nested = field_type.child_by_field_name('body')
                            if nested:
                                collect_members(nested)
                        for decl in declarators(field):
                            name, kind, function = declarator(decl, base)
                            if name:
                                members[name] = kind if not function and name not in members else None
                collect_members(body)
        if node.type == 'type_definition':
            base = base_type(node.child_by_field_name('type'))
            for decl in declarators(node):
                name, kind, function = declarator(decl, base)
                if name:
                    # Local typedef shadowing is deliberately unsupported.
                    owner = scope(node.parent)
                    value = kind if not function and owner and owner.type == 'translation_unit' else None
                    if name in aliases and aliases[name] != value:
                        aliases[name] = None
                    else:
                        aliases[name] = value
        if node.type in ('declaration', 'parameter_declaration', 'function_definition'):
            base = base_type(node.child_by_field_name('type'))
            owner = scope(node.parent)
            if node.type == 'parameter_declaration':
                # Ignore parameters in prototypes; collect function definitions.
                parent = node.parent
                while parent and parent.type not in ('function_definition', 'declaration'):
                    parent = parent.parent
                owner = parent if parent and parent.type == 'function_definition' else None
            if owner:
                symbols = scopes.setdefault(owner.id, {})
                for decl in declarators(node):
                    name, kind, function = declarator(decl, base)
                    if name:
                        symbols.setdefault(name, []).append((node.start_byte, kind, function))
        for child in node.named_children:
            visit(child)

    visit(tree.root_node)

    def canonical(kind):
        seen = set()
        while kind and kind[0] in aliases:
            if kind[0] in seen or aliases[kind[0]] is None:
                return None
            seen.add(kind[0])
            base = aliases[kind[0]]
            kind = (base[0], kind[1] + base[1])
        return kind

    def symbol(node, name):
        owner = scope(node.parent)
        while owner:
            candidates = [value for value in scopes.get(owner.id, {}).get(name, [])
                          if value[0] <= node.start_byte]
            if candidates:
                return candidates[-1][1:]
            owner = scope(owner.parent)
        return None, False

    def expression(node):
        if node.type == 'parenthesized_expression':
            return expression(node.named_children[0])
        if node.type == 'identifier':
            kind, function = symbol(node, text(node))
            return None if function else canonical(kind)
        if node.type in ('number_literal', 'char_literal'):
            return ('int', 0)  # Both integer/floating literals select default.
        if node.type == 'cast_expression':
            target = node.child_by_field_name('type')
            base = base_type(target.child_by_field_name('type'))
            decl = target.child_by_field_name('declarator')
            return canonical(declarator(decl, base)[1] if decl else base)
        if node.type == 'conditional_expression':
            left = expression(node.child_by_field_name('consequence'))
            right = expression(node.child_by_field_name('alternative'))
            return left if left and left == right else None
        if node.type == 'pointer_expression':
            kind = expression(node.child_by_field_name('argument'))
            if not kind:
                return None
            operator = text(node.child_by_field_name('operator'))
            depth = kind[1] + (1 if operator == '&' else -1)
            return (kind[0], depth) if depth >= 0 else None
        if node.type == 'subscript_expression':
            kind = expression(node.child_by_field_name('argument'))
            return (kind[0], kind[1] - 1) if kind and kind[1] > 0 else None
        if node.type == 'field_expression':
            kind = expression(node.child_by_field_name('argument'))
            operator = text(node.child_by_field_name('operator'))
            if not kind or kind[1] != (1 if operator == '->' else 0):
                return None
            return canonical(fields.get(kind[0], {}).get(text(node.child_by_field_name('field'))))
        if node.type == 'call_expression':
            function = node.child_by_field_name('function')
            if function.type == 'identifier':
                kind, is_function = symbol(node, text(function))
                return canonical(kind) if is_function else None
        return None

    edits, resolved, unresolved = [], [], []
    expected = ['PortRefGfx', 'portRefGfxToken', 'PortRefDObjDLLink',
                'portRefDObjDLLinkToken', 'default', 'portRefU32Token']
    for node in generic_nodes:
        children = node.named_children
        if [text(child) for child in children[1:]] != expected:
            unresolved.append({'expression': text(node), 'reason': 'unrecognized association list'})
            continue
        kind = expression(children[0])
        helper = None
        if kind == ('struct PortRefGfx', 0):
            helper = 'portRefGfxToken'
        elif kind == ('struct PortRefDObjDLLink', 0):
            helper = 'portRefDObjDLLinkToken'
        elif kind and not (kind[0].startswith(('struct ', 'union ', '@anonymous:')) and kind[1] == 0):
            helper = 'portRefU32Token'
        if not helper:
            unresolved.append({'expression': text(children[0]), 'type': kind, 'reason': 'type not proven'})
            continue
        # Preserve source line counts while selecting the typed helper.
        replacement = helper.encode() + b'\n' * source[node.start_byte:node.end_byte].count(b'\n')
        edits.append((node.start_byte, node.end_byte, replacement))
        resolved.append({'expression': text(children[0]), 'type': kind, 'helper': helper,
                         'preprocessed_line': node.start_point.row + 1})
    # Nested _Generic selectors occur in ftmain. Replacing an outer selector
    # discards its unevaluated controlling expression, including any inner
    # selections there. Applying both overlapping byte edits corrupts offsets.
    independent = []
    for edit in sorted(edits, key=lambda item: (item[0], -item[1])):
        if independent and edit[0] < independent[-1][1]:
            if edit[1] > independent[-1][1]:
                raise ValueError('Partially overlapping generic selections')
            continue
        independent.append(edit)
    for start, end, replacement in reversed(independent):
        source = source[:start] + replacement + source[end:]
    return source, resolved, unresolved


def lower_rumble_initializers(source, parser):
    """Lower only GMRumbleEventDefault's named opcode/param constant rows.

    Read the actual preprocessed declaration order. Refuse missing, duplicate,
    added or reordered unknown fields instead of assuming an endian layout.
    """
    tree = parser.parse(parse_view(source))
    order = None
    rows = []

    def text(node):
        return source[node.start_byte:node.end_byte]

    def visit(node):
        nonlocal order
        if node.type == 'struct_specifier':
            name, body = node.child_by_field_name('name'), node.child_by_field_name('body')
            if name and body and text(name) == b'GMRumbleEventDefault':
                declarations = [child for child in body.named_children if child.type == 'field_declaration']
                actual = []
                for declaration in declarations:
                    fields = [child for child in declaration.named_children if child.type == 'field_identifier']
                    if text(declaration.child_by_field_name('type')) != b'u16' or len(fields) != 1:
                        raise ValueError('Unrecognized rumble bitfield declaration')
                    actual.append(text(fields[0]))
                if sorted(actual) != [b'opcode', b'param']:
                    raise ValueError('Unrecognized rumble field set')
                order = actual
        if node.type == 'declaration' and node.parent.type == 'translation_unit':
            kind = node.child_by_field_name('type')
            if kind and text(kind) == b'GMRumbleEventDefault':
                for init in node.named_children:
                    if init.type != 'init_declarator':
                        continue
                    declaration = init.child_by_field_name('declarator')
                    while declaration and declaration.type != 'pointer_declarator':
                        declaration = declaration.child_by_field_name('declarator')
                    if declaration:  # Table of pointers is not a rumble row table.
                        continue
                    value = init.child_by_field_name('value')
                    if not value or value.type != 'initializer_list':
                        raise ValueError('Unrecognized rumble table initializer')
                    for row in value.named_children:
                        if row.type in ('preproc_call', 'comment'):
                            continue
                        if row.type != 'initializer_list':
                            raise ValueError('Unrecognized rumble row')
                        pairs = {}
                        for pair in row.named_children:
                            if pair.type != 'initializer_pair':
                                raise ValueError('Expected only named rumble fields')
                            name = text(pair.child_by_field_name('designator')).removeprefix(b'.')
                            if name in pairs:
                                raise ValueError('Duplicate rumble initializer field')
                            pairs[name] = text(pair.child_by_field_name('value'))
                        if sorted(pairs) != [b'opcode', b'param']:
                            raise ValueError('Incomplete rumble initializer')
                        rows.append((row, pairs))
        for child in node.named_children:
            visit(child)

    visit(tree.root_node)
    if not order or not rows:
        raise ValueError('Expected actual rumble declaration and initialized tables')
    for row, pairs in reversed(rows):
        replacement = b'{ ' + b', '.join(pairs[field] for field in order) + b' }'
        missing_lines = text(row).count(b'\n') - replacement.count(b'\n')
        if missing_lines < 0:
            raise ValueError('Unexpected rumble source mapping')
        replacement += b'\n' * missing_lines
        source = source[:row.start_byte] + replacement + source[row.end_byte:]
    return source, {'rows': len(rows), 'field_order': [field.decode() for field in order]}
