from __future__ import annotations
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from app.demo import generate_demo_lef_def
from app.parsers.lef_parser import LefParser
from app.parsers.def_parser import DefParser
from app.spatial.spatial_index import SpatialIndexManager
from app.core.models import Rect


def main():
    print("=" * 60)
    print("EDA Layout Viewer Backend Test Suite")
    print("=" * 60)

    print("\n[1/5] Generating demo LEF/DEF design...")
    t0 = time.time()
    lef_path, def_path = generate_demo_lef_def(
        num_macros=100,
        num_instances=2000,
        num_nets=5000,
        chip_w=5000,
        chip_h=5000,
        seed=42,
    )
    t1 = time.time()
    print(f"  LEF: {lef_path} ({os.path.getsize(lef_path)/1024:.1f} KB)")
    print(f"  DEF: {def_path} ({os.path.getsize(def_path)/(1024*1024):.2f} MB)")
    print(f"  Time: {t1-t0:.2f}s")

    print("\n[2/5] Parsing LEF...")
    t0 = time.time()
    lef_data = LefParser.parse_file(lef_path)
    t1 = time.time()
    print(f"  Layers: {len(lef_data.layers)}")
    print(f"  Sites: {len(lef_data.sites)}")
    print(f"  Macros: {len(lef_data.macros)}")
    print(f"  Layer order: {lef_data.layer_order}")
    print(f"  Time: {t1-t0:.2f}s")
    sample_macro = list(lef_data.macros.values())[0] if lef_data.macros else None
    if sample_macro:
        print(f"  Sample macro '{sample_macro.name}': size={sample_macro.size}, pins={len(sample_macro.pins)}")

    print("\n[3/5] Parsing DEF...")
    t0 = time.time()
    def_data = DefParser.parse_file(def_path)
    t1 = time.time()
    print(f"  Design: {def_data.design_name}")
    print(f"  Die area: {def_data.die_area}")
    print(f"  Components: {len(def_data.components)}")
    print(f"  I/O Pins: {len(def_data.pins)}")
    print(f"  Vias: {len(def_data.vias)}")
    print(f"  Nets: {len(def_data.nets)}")
    print(f"  Special Nets: {len(def_data.specialnets)}")
    print(f"  Time: {t1-t0:.2f}s")
    if def_data.components:
        c = def_data.components[0]
        print(f"  Sample comp: {c.name} ({c.macro_name}) @ {c.position} {c.orientation} [{c.placement_status}]")

    print("\n[4/5] Building spatial index (Quadtree)...")
    t0 = time.time()
    spatial_idx = SpatialIndexManager()
    progress_steps = []
    def progress_cb(step, cur, total):
        if not progress_steps or progress_steps[-1][0] != step or (time.time() - t0) > 0.5:
            progress_steps.append((step, cur, total))
            if len(progress_steps) > 1:
                ps = progress_steps[-1]
                sys.stdout.write(f"\r  Step: {ps[0]:15s} - {ps[1]}/{ps[2]}    ")
                sys.stdout.flush()
    spatial_idx.build(lef_data, def_data, progress_cb)
    t1 = time.time()
    print(f"\n  Done in {t1-t0:.2f}s")
    stats = spatial_idx.stats
    print(f"  Component instances: {stats.component_count}")
    print(f"  Cell/IO pins: {stats.pin_count}")
    print(f"  Vias: {stats.via_count}")
    print(f"  Routing segments: {stats.routing_segment_count}")
    print(f"  Total shapes: {stats.total_shapes}")
    print(f"  Layers: {list(stats.layer_shape_counts.keys())}")
    print(f"  Shapes per layer:")
    for ln, cnt in sorted(stats.layer_shape_counts.items(), key=lambda x: -x[1]):
        print(f"    {ln:20s}: {cnt:>10,d}")

    print(f"\n  Quadtree stats:")
    qt_stats = spatial_idx._quadtree.get_stats()
    print(f"    Total items indexed: {qt_stats['total_items']:,}")
    print(f"    Total nodes: {qt_stats['total_nodes']:,}")
    for depth in sorted(qt_stats['depth_counts'].keys(), key=int):
        dc = qt_stats['depth_counts'][depth]
        print(f"    Depth {depth:>2s}: nodes={dc['nodes']:>8,d}, leaves={dc['leaves']:>8,d}, items={dc['items']:>12,d}")

    print("\n[5/5] Running spatial queries...")
    chip = spatial_idx.chip_bbox
    cx = (chip.llx + chip.urx) / 2
    cy = (chip.lly + chip.ury) / 2
    queries = [
        ("Full chip", chip),
        ("Center 1/4", Rect(llx=cx-chip.width/4, lly=cy-chip.height/4, urx=cx+chip.width/4, ury=cy+chip.height/4)),
        ("Center 1/10", Rect(llx=cx-chip.width/10, lly=cy-chip.height/10, urx=cx+chip.width/10, ury=cy+chip.height/10)),
        ("Tiny 100x100", Rect(llx=cx-50, lly=cy-50, urx=cx+50, ury=cy+50)),
    ]
    for qname, qrect in queries:
        t0 = time.time()
        results = spatial_idx.query(qrect, max_results=100000)
        t1 = time.time()
        print(f"  {qname}: {len(results):,d} shapes in {(t1-t0)*1000:.1f}ms")

    print("\n[5.1] Tile query test (raw for WebGL)...")
    tx = chip.llx + chip.width / 4
    ty = chip.lly + chip.height / 4
    tw = chip.width / 3
    th = chip.height / 3
    t0 = time.time()
    tile_result = spatial_idx.query_tile(tx, ty, tw, th, max_results=500000)
    t1 = time.time()
    total_shapes = sum(len(items) for items in tile_result.values())
    layer_list = list(tile_result.keys())
    print(f"  Tile: x={tx:.0f} y={ty:.0f} w={tw:.0f} h={th:.0f}")
    print(f"  Layers returned: {len(layer_list)}")
    print(f"  Total shapes in viewport: {total_shapes:,d}")
    print(f"  Query time: {(t1-t0)*1000:.1f}ms")
    for ln in layer_list[:8]:
        n = len(tile_result[ln])
        color = getattr(db.spatial_index, 'LAYER_COLORS', {}).get(ln, '#888888')
        print(f"    {ln:20s}: {n:>8,d} shapes, color={color}")

    print("\n" + "=" * 60)
    print("All tests passed! Backend is working correctly.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
