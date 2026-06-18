import sys, os
sys.path.insert(0, 'backend')
from app.parsers.def_lexer import DefLexer, DefToken
from app.parsers.def_parser import DefParser
from app.demo import generate_demo_lef_def

lef_path, def_path = generate_demo_lef_def(num_macros=3, num_instances=20, num_nets=50, chip_w=1000, chip_h=1000, seed=123)

parser = DefParser()
lexer = DefLexer.from_file(def_path)
parser._tokens = lexer.tokenize()
parser._pos = 0

print('Searching for section markers...')
for i, t in enumerate(parser._tokens):
    if t.type in (DefToken.ROWS, DefToken.COMPONENTS, DefToken.PINS, DefToken.NETS, DefToken.SPECIALNETS, DefToken.VIAS, DefToken.TRACKS, DefToken.GCELLGRID):
        print(f'  Token[{i}]: {t.type} "{t.value}" at line {t.line}')
    if t.type == DefToken.END and i < len(parser._tokens) - 1:
        nxt = parser._tokens[i + 1]
        if nxt.value.upper() in ('ROWS', 'TRACKS', 'GCELLGRID', 'PINS', 'COMPONENTS', 'VIAS', 'NETS', 'SPECIALNETS', 'DESIGN'):
            print(f'  Token[{i}]: END + "{nxt.value.upper()}" at line {t.line}')
    if t.value.upper() == 'DESIGN' and t.type == DefToken.END and i > 100:
        break

print()
print('Testing ROWS parser logic...')
parser2 = DefParser()
parser2._tokens = lexer.tokenize()
parser2._pos = 0

while parser2._pos < len(parser2._tokens):
    t = parser2._current()
    if t.type == DefToken.DIEAREA:
        parser2._consume()
        parser2._parse_point()
        parser2._parse_point()
        parser2._skip_to_semicolon()
        break
    parser2._consume()

print(f'After DIEAREA: pos={parser2._pos}, token={parser2._current()}')
t = parser2._current()
print(f'Next token: {t.type} line={t.line}')
if t.type == DefToken.ROWS:
    parser2._consume()
    cnt = int(parser2._parse_number()) if parser2._check(DefToken.NUMBER) else 0
    print(f'ROWS count: {cnt}')
    parser2._skip_to_semicolon()
    print(f'After skip_to_semicolon, pos={parser2._pos}, token={parser2._current()} at line {parser2._current().line}')

    loop_count = 0
    while True:
        if parser2._check(DefToken.END):
            nxt = parser2._peek()
            print(f'  CHECKING: END at pos {parser2._pos}, next="{nxt.value}" (type {nxt.type})')
            if nxt.value.upper() == 'ROWS':
                print('  END ROWS found! Breaking')
                break
        ct = parser2._current()
        if loop_count < 15:
            nxt_txt = parser2._peek().value if parser2._peek() else ''
            print(f'  loop {loop_count}: pos={parser2._pos} cur={ct.type}:{ct.value} next={nxt_txt}')
            loop_count += 1
        if ct.type == DefToken.ROW:
            parser2._consume()
            parser2._skip_to_semicolon()
        elif ct.type == DefToken.SEMICOLON:
            parser2._consume()
        elif ct.type == DefToken.EOF:
            print('  REACHED EOF!')
            break
        elif ct.type == DefToken.END:
            nxt = parser2._peek()
            if nxt.value.upper() != 'ROWS':
                print(f'  END (not ROWS), consuming...')
                parser2._consume()
                parser2._consume()
        else:
            parser2._consume()

    if parser2._check(DefToken.END):
        parser2._consume()
        parser2._consume()
        parser2._skip_to_semicolon()

    print(f'After ROWS loop: pos={parser2._pos}, token={parser2._current()} at line {parser2._current().line}')
    print(f'Next few tokens:')
    for i in range(10):
        if parser2._pos + i < len(parser2._tokens):
            tt = parser2._tokens[parser2._pos + i]
            print(f'  [{i}]: {tt.type:20s} {repr(tt.value):25s} line {tt.line}')
