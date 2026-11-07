"""Pinned C syntax adaptations that leave declared data representations unchanged."""
import re


def lower_scene_typeof(source):
    if len(re.findall(rb'\bSCBattleState\s+gSCManagerTransferBattleState\s*;', source)) != 1:
        raise ValueError('Expected actual SCBattleState transfer global declaration')
    old = b'__typeof__(gSCManagerTransferBattleState)'
    if source.count(old) != 2:
        raise ValueError('Expected two scene battle-state typeof declarations')
    return source.replace(old, b'SCBattleState'), {'actual_type': 'SCBattleState', 'declarations': 2}


def lower_map_positions(source, parser):
    from typed_generic import parse_view
    tree = parser.parse(parse_view(source))
    enums, targets = {}, []
    def text(node):
        return source[node.start_byte:node.end_byte] if node else b''
    def visit(node):
        if node.type == 'enum_specifier' and text(node.child_by_field_name('name')) == b'GRKind':
            current = -1
            for item in node.child_by_field_name('body').named_children:
                if item.type != 'enumerator':
                    continue
                value = item.child_by_field_name('value')
                if value:
                    raw = text(value)
                    current = enums[raw] if raw in enums else int(raw, 0)
                else:
                    current += 1
                enums[text(item.child_by_field_name('name'))] = current
        if node.type == 'declaration' and text(node.child_by_field_name('type')) == b'Vec3f':
            for init in node.named_children:
                if init.type != 'init_declarator':
                    continue
                decl = init.child_by_field_name('declarator')
                value = init.child_by_field_name('value')
                if decl.type == 'array_declarator' and text(decl.child_by_field_name('declarator')) == b'positions' and value:
                    pairs = [child for child in value.named_children if child.type == 'initializer_pair']
                    if pairs:
                        targets.append((value, pairs))
        for child in node.named_children:
            visit(child)
    visit(tree.root_node)
    if len(targets) != 1:
        raise ValueError('Expected exactly one designated Vec3f positions array')
    value, pairs = targets[0]
    rows = [child for child in value.named_children if child.type in ('initializer_list', 'initializer_pair')]
    if len(rows) != 12 or len(pairs) != 3 or any(child.type != 'initializer_list' for child in rows[:9]):
        raise ValueError('Unexpected starter-stage position rows')
    edits = []
    previous = 8
    expected = [(b'nGRKindMetal', 13), (b'nGRKindZako', 14), (b'nGRKindLast', 16)]
    for pair, (name, index) in zip(pairs, expected):
        designator = pair.child_by_field_name('designator')
        if text(designator).replace(b' ', b'') != b'[' + name + b']' or enums.get(name) != index:
            raise ValueError('Stage enum/designator changed')
        row = pair.child_by_field_name('value')
        if row.type != 'initializer_list' or len(row.named_children) != 3:
            raise ValueError('Expected three Vec3f scalar components')
        prefix = source[pair.start_byte:row.start_byte]
        replacement = b'{0.0F, 0.0F, 0.0F}, ' * (index - previous - 1)
        replacement += b'\n' * prefix.count(b'\n')
        edits.append((pair.start_byte, row.start_byte, replacement))
        previous = index
    for start, end, replacement in reversed(edits):
        source = source[:start] + replacement + source[end:]
    return source, {'rows': 17, 'explicit_zero_indices': [9, 10, 11, 12, 15], 'designators': [name.decode() for name, _ in expected]}
