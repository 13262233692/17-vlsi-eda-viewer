from __future__ import annotations
import os
import random
import math
import tempfile
from pathlib import Path
from typing import Tuple


def generate_demo_lef_def(
    num_macros: int = 200,
    num_instances: int = 8000,
    num_nets: int = 15000,
    chip_w: float = 10000.0,
    chip_h: float = 10000.0,
    seed: int = 42,
) -> Tuple[str, str]:
    random.seed(seed)

    tmp_dir = Path(tempfile.gettempdir()) / "eda_demo_design"
    tmp_dir.mkdir(exist_ok=True, parents=True)

    lef_path = str(tmp_dir / "demo_design.lef")
    def_path = str(tmp_dir / "demo_design.def")

    layers = [
        ("NWELL", "MASTERSLICE", None, 0.12),
        ("DIFF", "MASTERSLICE", None, 0.08),
        ("POLY", "MASTERSLICE", "HORIZONTAL", 0.06),
        ("CONT", "CUT", None, 0.06),
        ("M1", "ROUTING", "HORIZONTAL", 0.10),
        ("V1", "CUT", None, 0.08),
        ("M2", "ROUTING", "VERTICAL", 0.10),
        ("V2", "CUT", None, 0.08),
        ("M3", "ROUTING", "HORIZONTAL", 0.12),
        ("V3", "CUT", None, 0.10),
        ("M4", "ROUTING", "VERTICAL", 0.12),
        ("V4", "CUT", None, 0.10),
        ("M5", "ROUTING", "HORIZONTAL", 0.14),
    ]

    with open(lef_path, "w") as f:
        f.write("VERSION 5.8 ;\n")
        f.write('DIVIDERCHAR "/" ;\n')
        f.write('BUSBITCHARS "[]" ;\n')
        f.write("MANUFACTURINGGRID 0.001 ;\n")
        f.write("UNITS\n")
        f.write("  DATABASE MICRONS 2000 ;\n")
        f.write("END UNITS\n\n")

        for lname, ltype, direction, width in layers:
            f.write(f"LAYER {lname}\n")
            f.write(f"  TYPE {ltype} ;\n")
            if direction:
                f.write(f"  DIRECTION {direction} ;\n")
                pitch = width * 5
                f.write(f"  PITCH {pitch:.3f} ;\n")
                offset = pitch / 2
                f.write(f"  OFFSET {offset:.3f} ;\n")
            f.write(f"  WIDTH {width:.3f} ;\n")
            f.write(f"END {lname}\n\n")

        f.write("SITE core\n")
        f.write("  CLASS CORE ;\n")
        f.write("  SIZE 0.260 BY 1.400 ;\n")
        f.write("  SYMMETRY Y ;\n")
        f.write("END core\n\n")

        macro_sizes = [
            ("INV", (1.2, 3.5), 3),
            ("NAND2", (1.8, 3.5), 4),
            ("NOR2", (1.8, 3.5), 4),
            ("AND2", (2.4, 3.5), 5),
            ("OR2", (2.4, 3.5), 5),
            ("DFF", (4.2, 7.0), 8),
            ("BUFX2", (1.5, 3.5), 4),
            ("AOI21", (2.0, 3.5), 5),
            ("OAI21", (2.0, 3.5), 5),
            ("MUX2", (2.8, 3.5), 6),
            ("ADD1", (5.0, 3.5), 8),
            ("SRAM", (50.0, 80.0), 64),
            ("DEC", (30.0, 40.0), 32),
        ]

        orients = ["N", "S", "E", "W", "FN", "FS", "FE", "FW"]
        pin_directions = ["INPUT", "OUTPUT", "INOUT"]
        pin_uses = ["SIGNAL", "POWER", "GROUND", "CLOCK"]

        for macro_idx in range(num_macros):
            base = macro_sizes[macro_idx % len(macro_sizes)]
            base_name, base_size, num_pins = base
            w, h = base_size
            w = w * (0.8 + random.random() * 0.4)
            h = h * (0.8 + random.random() * 0.4)
            mname = f"{base_name}_{macro_idx:04d}"

            f.write(f"MACRO {mname}\n")
            f.write(f"  CLASS CORE ;\n")
            f.write(f"  FOREIGN {mname} 0.000 0.000 ;\n")
            f.write(f"  ORIGIN 0.000 0.000 ;\n")
            f.write(f"  SIZE {w:.3f} BY {h:.3f} ;\n")
            f.write(f"  SYMMETRY X Y ;\n\n")

            for pidx in range(num_pins):
                pname = f"PIN{pidx}"
                if pidx == 0:
                    pdir = "OUTPUT"
                    puse = "SIGNAL"
                elif pidx == num_pins - 1:
                    pdir = "INOUT"
                    puse = random.choice(["POWER", "GROUND"])
                elif pidx == num_pins - 2:
                    pdir = "INPUT"
                    puse = random.choice(["CLOCK", "SIGNAL"])
                else:
                    pdir = random.choice(["INPUT", "INPUT", "INPUT", "OUTPUT"])
                    puse = "SIGNAL"

                px = random.uniform(0.05 * w, 0.95 * w)
                py = random.uniform(0.05 * h, 0.95 * h)
                pw = random.uniform(0.1, 0.4)
                ph = random.uniform(0.1, 0.4)

                pin_layer = random.choice(["M1", "M2", "POLY", "DIFF"])

                f.write(f"  PIN {pname}\n")
                f.write(f"    DIRECTION {pdir} ;\n")
                f.write(f"    USE {puse} ;\n")
                f.write(f"    PORT\n")
                f.write(f"      LAYER {pin_layer} ;\n")
                f.write(f"        RECT {px - pw/2:.3f} {py - ph/2:.3f} {px + pw/2:.3f} {py + ph/2:.3f} ;\n")
                f.write(f"    END PORT\n")
                f.write(f"  END {pname}\n\n")

            if h > 10:
                f.write(f"  OBS\n")
                obs_layer = random.choice(["M3", "M4", "M5"])
                f.write(f"    LAYER {obs_layer} ;\n")
                n_obs = random.randint(3, 10)
                for _ in range(n_obs):
                    ox = random.uniform(0, w)
                    oy = random.uniform(0, h)
                    ow = random.uniform(0.5, min(5.0, w * 0.3))
                    oh = random.uniform(0.5, min(5.0, h * 0.3))
                    f.write(f"      RECT {ox:.3f} {oy:.3f} {ox + ow:.3f} {oy + oh:.3f} ;\n")
                f.write(f"  END OBS\n\n")

            f.write(f"END {mname}\n\n")

        f.write("END LIBRARY\n")

    macro_names_all = []
    with open(lef_path, "r") as f:
        for line in f:
            if line.startswith("MACRO "):
                parts = line.strip().split()
                macro_names_all.append(parts[1])

    print(f"[Demo Generator] Generated {len(macro_names_all)} macros in LEF")

    with open(def_path, "w") as f:
        f.write("VERSION 5.8 ;\n")
        f.write('DIVIDERCHAR "/" ;\n')
        f.write('BUSBITCHARS "[]" ;\n')
        f.write(f'DESIGN "demo_design" ;\n')
        f.write("UNITS DISTANCE MICRONS 2000 ;\n\n")

        die_llx = 0.0
        die_lly = 0.0
        die_urx = chip_w
        die_ury = chip_h
        f.write(f"DIEAREA ( {die_llx:.1f} {die_lly:.1f} ) ( {die_urx:.1f} {die_ury:.1f} ) ;\n\n")

        site_w = 0.26
        site_h = 1.4
        row_step = site_h * 2
        rows_per_col = int(chip_h / row_step)
        num_rows = rows_per_col
        f.write(f"ROWS {num_rows} ;\n")
        for ri in range(num_rows):
            orient = "N" if ri % 2 == 0 else "FS"
            fy = ri * row_step
            f.write(f"ROW ROW{ri} core {die_llx + site_w:.1f} {die_lly + fy:.1f} "
                    f"{orient} DO {int(chip_w / site_w) - 2} BY 1 "
                    f"STEP {site_w:.3f} 0 ;\n")
        f.write("END ROWS\n\n")

        num_io_pins = 128
        f.write(f"PINS {num_io_pins} ;\n")
        for pi in range(num_io_pins):
            edge = pi % 4
            if edge == 0:
                px = die_llx + 2
                py = die_lly + (pi // 4) * (chip_h / 32) + 100
            elif edge == 1:
                px = die_urx - 2
                py = die_lly + (pi // 4) * (chip_h / 32) + 100
            elif edge == 2:
                px = die_llx + (pi // 4) * (chip_w / 32) + 100
                py = die_lly + 2
            else:
                px = die_llx + (pi // 4) * (chip_w / 32) + 100
                py = die_ury - 2

            pname = f"IO_{pi:04d}"
            net_name = f"NET_{pi % 1000:05d}"
            pdir = random.choice(["INPUT", "INPUT", "OUTPUT", "INOUT"])
            puse = random.choice(["SIGNAL", "SIGNAL", "CLOCK", "POWER", "GROUND"])
            pw = random.uniform(0.5, 2.0)
            ph = random.uniform(0.5, 2.0)
            player = random.choice(["M3", "M4", "M5"])
            f.write(f"- {pname} + NET {net_name} + DIRECTION {pdir} + USE {puse}\n")
            f.write(f"  + LAYER {player} ( {px - pw/2:.1f} {py - ph/2:.1f} ) ( {px + pw/2:.1f} {py + ph/2:.1f} )\n")
            f.write(f"  + FIXED ( {px:.1f} {py:.1f} ) N ;\n")
        f.write("END PINS\n\n")

        f.write(f"COMPONENTS {num_instances} ;\n")
        instance_names = []
        for ii in range(num_instances):
            macro_name = random.choice(macro_names_all)
            inst_name = f"inst_{ii:06d}"
            instance_names.append(inst_name)

            grid_x = (ii * 137) % int(chip_w / 10)
            grid_y = (ii * 239) % int(chip_h / 10)
            px = die_llx + 50 + grid_x * 10 + random.uniform(-5, 5)
            py = die_lly + 50 + grid_y * 10 + random.uniform(-5, 5)

            orient = random.choice(["N", "N", "N", "FS", "FN", "S"])
            status = random.choice(["PLACED", "PLACED", "FIXED"])

            f.write(f"- {inst_name} {macro_name}\n")
            f.write(f"    + {status} ( {px:.1f} {py:.1f} ) {orient} ;\n")

            if ii % 10000 == 0 and ii > 0:
                print(f"[Demo Generator] Written {ii}/{num_instances} instances to DEF")
        f.write("END COMPONENTS\n\n")

        print(f"[Demo Generator] Generating {num_nets} nets with routing...")
        f.write(f"NETS {num_nets} ;\n")

        metal_layers = ["M1", "M2", "M3", "M4", "M5"]
        metal_widths = {
            "M1": 0.10, "M2": 0.10, "M3": 0.12, "M4": 0.12, "M5": 0.14,
        }
        via_names = ["VIA1", "VIA2", "VIA3", "VIA4"]

        routing_segment_count = 0
        for ni in range(num_nets):
            net_name = f"NET_{ni:05d}"
            num_connections = random.randint(2, min(10, 2 + ni // 1000))
            connections = []
            inst_choices = random.sample(range(num_instances), min(num_connections, num_instances))
            for ic in inst_choices:
                pin_idx = random.randint(0, 10)
                connections.append(f"( inst_{ic:06d} PIN{pin_idx} )")

            f.write(f"- {net_name} {' '.join(connections)}\n")
            f.write(f"  + ROUTED ")

            num_segs = random.randint(1, 6)
            start_x = random.uniform(die_llx + 100, die_urx - 100)
            start_y = random.uniform(die_lly + 100, die_ury - 100)
            cur_layer_idx = random.randint(0, len(metal_layers) - 1)
            cur_x = start_x
            cur_y = start_y

            first_seg = True
            for si in range(num_segs):
                layer = metal_layers[cur_layer_idx]
                w = metal_widths[layer]

                horizontal = (cur_layer_idx % 2 == 0)
                if horizontal:
                    seg_len = random.uniform(20, 300)
                    if random.random() < 0.5:
                        seg_len = -seg_len
                    new_x = cur_x + seg_len
                    new_y = cur_y
                    new_x = max(die_llx + 10, min(die_urx - 10, new_x))
                else:
                    seg_len = random.uniform(20, 300)
                    if random.random() < 0.5:
                        seg_len = -seg_len
                    new_x = cur_x
                    new_y = cur_y + seg_len
                    new_y = max(die_lly + 10, min(die_ury - 10, new_y))

                if first_seg:
                    f.write(f"{layer} {w:.2f} ( {cur_x:.1f} {cur_y:.1f} ) ( {new_x:.1f} {new_y:.1f} )")
                    first_seg = False
                else:
                    f.write(f" NEW {layer} {w:.2f} ( {cur_x:.1f} {cur_y:.1f} ) ( {new_x:.1f} {new_y:.1f} )")
                routing_segment_count += 1

                cur_x = new_x
                cur_y = new_y

                if si < num_segs - 1 and cur_layer_idx < len(metal_layers) - 1 and random.random() < 0.4:
                    via_idx = cur_layer_idx
                    via_name = via_names[via_idx] if via_idx < len(via_names) else via_names[-1]
                    f.write(f" VIA {via_name}")
                    cur_layer_idx += 1
                    if cur_layer_idx >= len(metal_layers):
                        cur_layer_idx = len(metal_layers) - 1

            f.write(f" ;\n")

            if ni % 5000 == 0 and ni > 0:
                print(f"[Demo Generator] Written {ni}/{num_nets} nets ({routing_segment_count} segments)")
        f.write("END NETS\n\n")

        print(f"[Demo Generator] Generating special nets (power grid)...")
        num_special = 50
        f.write(f"SPECIALNETS {num_special} ;\n")

        for pni in range(num_special):
            is_vdd = pni < num_special // 2
            pname = f"VDD_{pni}" if is_vdd else f"VSS_{pni - num_special//2}"
            layer = "M5" if is_vdd else "M4"
            w = metal_widths[layer] * 8

            f.write(f"- {pname} ( * PIN{9 if is_vdd else 8} )\n")
            f.write(f"  + ROUTED ")

            first = True
            num_stripes = random.randint(5, 20)
            for si in range(num_stripes):
                if (pni % 2) == 0:
                    sx = die_llx + 100 + (si * (chip_w - 200) / max(1, num_stripes - 1))
                    p1 = (sx, die_lly + 100)
                    p2 = (sx, die_ury - 100)
                else:
                    sy = die_lly + 100 + (si * (chip_h - 200) / max(1, num_stripes - 1))
                    p1 = (die_llx + 100, sy)
                    p2 = (die_urx - 100, sy)

                if first:
                    f.write(f"{layer} {w:.2f} ( {p1[0]:.1f} {p1[1]:.1f} ) ( {p2[0]:.1f} {p2[1]:.1f} )")
                    first = False
                else:
                    f.write(f" NEW {layer} {w:.2f} ( {p1[0]:.1f} {p1[1]:.1f} ) ( {p2[0]:.1f} {p2[1]:.1f} )")
                routing_segment_count += 1
            f.write(f" ;\n")
        f.write("END SPECIALNETS\n\n")

        f.write("END DESIGN\n")

    total_lines = 0
    with open(def_path, "r") as f:
        for _ in f:
            total_lines += 1

    lef_size = os.path.getsize(lef_path)
    def_size = os.path.getsize(def_path)
    print(f"[Demo Generator] LEF: {lef_size/1024:.1f} KB")
    print(f"[Demo Generator] DEF: {def_size/(1024*1024):.1f} MB, {total_lines} lines")
    print(f"[Demo Generator] Routing segments: {routing_segment_count}")

    return lef_path, def_path
