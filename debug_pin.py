import sys, os, traceback
sys.path.insert(0, 'backend')
from app.parsers.def_lexer import DefLexer, DefToken
from app.parsers.def_parser import DefParser
from app.demo import generate_demo_lef_def

lef_path, def_path = generate_demo_lef_def(num_macros=3, num_instances=20, num_nets=50, chip_w=1000, chip_h=1000, seed=42)

lexer = DefLexer.from_file(def_path)
tokens = lexer.tokenize()

# Find PINS section start
pins_start = None
for i, t in enumerate(tokens):
    if t.type == DefToken.PINS:
        pins_start = i
        break

# Find first LAYER M5 after PINS
layer_pos = None
for i in range(pins_start + 3, min(pins_start + 50, len(tokens))):
    t = tokens[i]
    if t.type == DefToken.LAYER:
        layer_pos = i
        print(f'First LAYER at tokens[{i}]: {t.value}')
        for j in range(i, min(i+10, len(tokens))):
            tt = tokens[j]
            print(f'  [{j-i}]: {tt.type:15s} {repr(tt.value):20s} line {tt.line} col {tt.col}')
        break

# Now let's trace manually:
# After layer identifier M5, we are at LPAREN
print()
print('Manual trace:')
# Simulate what should happen
# After LAYER keyword, consume M5 (identifier)
# Now pos points to LPAREN
parser = DefParser()
parser._tokens = tokens
# Jump to after "LAYER M5" - first LAYER at position layer_pos + 2 (LAYER, then consume M5)
parser._pos = layer_pos + 2
print(f'At pos={parser._pos}: {parser._current().type}:{repr(parser._current().value)} line {parser._current().line}')
print('Calling _parse_pin_shapes...')
try:
    # Step 1: while self._check(LPAREN) -> True
    print(f'check LPAREN? {parser._check(DefToken.LPAREN)}')
    p = parser._parse_point()
    print(f'After 1st _parse_point: p={p}, pos={parser._pos}, cur={parser._current().type}:{repr(parser._current().value)}')
    print(f'check LPAREN before expect? {parser._check(DefToken.LPAREN)}')
except Exception as e:
    print(f'Error: {e}')
    traceback.print_exc()
