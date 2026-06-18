import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
from app.parsers.def_parser import DefParser
from app.demo import generate_demo_lef_def

lef_path, def_path = generate_demo_lef_def(num_macros=2, num_instances=2, num_nets=5, chip_w=500, chip_h=500, seed=99)
print(f'DEF: {def_path}', file=sys.stderr, flush=True)
t0 = time.time()
def_data = DefParser.parse_file(def_path)
print(f'DEF parse DONE in {time.time()-t0:.1f}s', file=sys.stderr, flush=True)
print(f'  components={len(def_data.components)}', file=sys.stderr, flush=True)
print(f'  pins={len(def_data.pins)}', file=sys.stderr, flush=True)
print(f'  nets={len(def_data.nets)}', file=sys.stderr, flush=True)
print(f'  specialnets={len(def_data.specialnets)}', file=sys.stderr, flush=True)
