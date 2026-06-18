from __future__ import annotations
from typing import Optional, Tuple, Any, Dict, List
from pathlib import Path
import asyncio
import os
import sys
import uuid
import shutil
import tempfile
import time

from ..core.models import LefData, Rect
from ..core.def_models import DefData, LayoutDatabase
from ..parsers.lef_parser import LefParser
from ..parsers.def_parser import DefParser
from ..spatial.spatial_index import SpatialIndexManager
from ..drc.drc_engine import DRCEngine, DRCResult


UPLOAD_DIR = Path(tempfile.gettempdir()) / "eda_viewer_uploads"
UPLOAD_DIR.mkdir(exist_ok=True, parents=True)


class DatabaseService:
    _instance: Optional["DatabaseService"] = None

    def __init__(self):
        self._db: LayoutDatabase = LayoutDatabase()
        self._spatial_index: Optional[SpatialIndexManager] = None
        self._lef_data: Optional[LefData] = None
        self._def_data: Optional[DefData] = None
        self._lef_path: Optional[str] = None
        self._def_path: Optional[str] = None
        self._parse_progress: dict = {}
        self._parse_task_id: Optional[str] = None
        self._parse_lock = asyncio.Lock()
        self._session_id: str = uuid.uuid4().hex
        self._drc_result: Optional[DRCResult] = None

    @classmethod
    def get_instance(cls) -> "DatabaseService":
        if cls._instance is None:
            cls._instance = DatabaseService()
        return cls._instance

    @property
    def is_loaded(self) -> bool:
        return self._db.is_loaded

    @property
    def db(self) -> LayoutDatabase:
        return self._db

    @property
    def spatial_index(self) -> Optional[SpatialIndexManager]:
        return self._spatial_index

    def get_upload_dir(self) -> Path:
        session_dir = UPLOAD_DIR / self._session_id
        session_dir.mkdir(exist_ok=True, parents=True)
        return session_dir

    def save_uploaded_file(self, filename: str, data: bytes) -> str:
        upload_dir = self.get_upload_dir()
        safe_name = os.path.basename(filename)
        dest = upload_dir / safe_name
        with open(dest, "wb") as f:
            f.write(data)
        return str(dest)

    def get_progress(self, task_id: str) -> dict:
        return self._parse_progress.get(task_id, {"status": "not_found"})

    async def parse_lef_def_async(
        self,
        lef_path: str,
        def_path: str,
        task_id: str,
    ) -> Tuple[bool, str]:
        async with self._parse_lock:
            self._parse_task_id = task_id
            self._parse_progress[task_id] = {
                "status": "starting",
                "step": "lef",
                "progress": 0,
                "message": "Starting LEF parsing...",
            }
            await asyncio.sleep(0.01)

            try:
                self._parse_progress[task_id]["status"] = "running"
                self._parse_progress[task_id]["step"] = "lef"
                self._parse_progress[task_id]["message"] = "Parsing LEF file..."

                lef_data = await asyncio.to_thread(LefParser.parse_file, lef_path)
                self._lef_path = lef_path

                self._parse_progress[task_id]["step"] = "def"
                self._parse_progress[task_id]["message"] = "Parsing DEF file..."
                self._parse_progress[task_id]["progress"] = 20

                def_data = await asyncio.to_thread(DefParser.parse_file, def_path)
                self._def_path = def_path
                self._parse_progress[task_id]["progress"] = 50

                self._parse_progress[task_id]["step"] = "index"
                self._parse_progress[task_id]["message"] = "Building spatial index..."

                spatial_idx = SpatialIndexManager()
                start_time = time.time()

                def _progress_cb(step: str, current: int, total: int) -> None:
                    elapsed = time.time() - start_time
                    base = 50
                    if step == "components":
                        pct = base + 15 * (current / max(total, 1))
                    elif step == "pins":
                        pct = base + 15 + 5 * (current / max(total, 1))
                    elif step == "vias":
                        pct = base + 20 + 5 * (current / max(total, 1))
                    elif step in ("nets", "specialnets"):
                        pct = base + 25 + 25 * (current / max(total, 1))
                    else:
                        pct = base + 45

                    self._parse_progress[task_id]["progress"] = int(min(99, pct))
                    self._parse_progress[task_id]["message"] = (
                        f"Indexing {step}: {current}/{total} "
                        f"({elapsed:.1f}s elapsed)"
                    )

                await asyncio.to_thread(
                    spatial_idx.build, lef_data, def_data, _progress_cb
                )

                self._spatial_index = spatial_idx
                self._db.lef_data = lef_data
                self._db.def_data = def_data
                self._lef_data = lef_data
                self._def_data = def_data
                self._db.is_loaded = True
                self._db.chip_bbox = spatial_idx.chip_bbox
                stats = spatial_idx.stats
                self._db.total_components = stats.component_count
                self._db.total_pins = stats.pin_count
                self._db.total_nets = len(def_data.nets)
                self._db.total_routing_segments = stats.routing_segment_count

                self._parse_progress[task_id]["status"] = "completed"
                self._parse_progress[task_id]["progress"] = 100
                self._parse_progress[task_id]["message"] = "Done!"
                self._parse_progress[task_id]["stats"] = {
                    "components": stats.component_count,
                    "pins": stats.pin_count,
                    "vias": stats.via_count,
                    "nets": len(def_data.nets),
                    "special_nets": len(def_data.specialnets),
                    "routing_segments": stats.routing_segment_count,
                    "total_shapes": stats.total_shapes,
                }
                await asyncio.sleep(0.01)
                return True, "Success"

            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                self._parse_progress[task_id]["status"] = "error"
                self._parse_progress[task_id]["error"] = str(e)
                self._parse_progress[task_id]["traceback"] = tb
                print(f"[DatabaseService] Parse error: {e}\n{tb}", file=sys.stderr)
                return False, str(e)

    def get_chip_bbox(self) -> Optional[dict]:
        if not self._spatial_index:
            return None
        b = self._spatial_index.chip_bbox
        return {
            "llx": b.llx,
            "lly": b.lly,
            "urx": b.urx,
            "ury": b.ury,
            "width": b.width,
            "height": b.height,
        }

    def get_layer_info(self) -> list:
        if not self._spatial_index:
            return []
        return self._spatial_index.get_layer_info()

    def get_tile(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        layers: Optional[list] = None,
        max_results: Optional[int] = None,
    ) -> dict:
        if not self._spatial_index:
            return {"error": "No data loaded"}
        return self._spatial_index.query_tile(x, y, w, h, layers, max_results)

    def get_tile_flattened(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        layers: Optional[list] = None,
        max_results_per_layer: int = 20000,
    ) -> dict:
        if not self._spatial_index:
            return {"error": "No data loaded"}

        rect = Rect(llx=x, lly=y, urx=x + w, ury=y + h)
        result: Dict[str, Any] = {}

        layer_colors = {}
        for li in self._spatial_index.get_layer_info():
            layer_colors[li["name"]] = li["color"]

        def _filter(item):
            if layers and item.layer not in layers:
                return False
            return True

        items = self._spatial_index._quadtree.query(rect, _filter)

        layer_groups: Dict[str, List[Any]] = {}
        for it in items:
            s = it.data
            if s.layer not in layer_groups:
                layer_groups[s.layer] = []
            layer_groups[s.layer].append(s)

        output_layers = []
        total_count = 0
        for lname, shapes in layer_groups.items():
            if max_results_per_layer and len(shapes) > max_results_per_layer:
                step = max(1, len(shapes) // max_results_per_layer)
                shapes_sampled = shapes[::step]
            else:
                shapes_sampled = shapes

            verts = []
            for s in shapes_sampled:
                vs = s.vertices
                if len(vs) >= 4:
                    verts.extend([
                        vs[0][0], vs[0][1],
                        vs[1][0], vs[1][1],
                        vs[2][0], vs[2][1],
                        vs[0][0], vs[0][1],
                        vs[2][0], vs[2][1],
                        vs[3][0], vs[3][1],
                    ])
            output_layers.append({
                "name": lname,
                "color": layer_colors.get(lname, [0.5, 0.5, 0.5, 0.8]),
                "vertices": verts,
                "count": len(shapes_sampled),
                "total_count": len(shapes),
            })
            total_count += len(shapes)

        return {
            "layers": output_layers,
            "total_shapes": total_count,
            "viewport": {"x": x, "y": y, "w": w, "h": h},
        }

    def run_drc(self) -> DRCResult:
        if not self.is_loaded or not self._lef_data or not self._def_data:
            raise ValueError("No design loaded")

        engine = DRCEngine()
        self._drc_result = engine.run(self._lef_data, self._def_data)
        return self._drc_result

    def get_drc_result(self) -> Optional[DRCResult]:
        return self._drc_result

    def get_drc_violations_tile(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        max_results: int = 5000,
    ) -> dict:
        if not self._drc_result:
            return {"violations": [], "total": 0}

        rect = Rect(llx=x, lly=y, urx=x + w, ury=y + h)
        result_violations = []

        for v in self._drc_result.violations:
            if v.bbox.intersects(rect):
                result_violations.append({
                    "rule_type": v.rule_type,
                    "layer": v.layer,
                    "bbox": [v.bbox.llx, v.bbox.lly, v.bbox.urx, v.bbox.ury],
                    "severity": v.severity,
                    "message": v.message,
                    "net1": v.net1,
                    "net2": v.net2,
                    "actual_distance": round(v.actual_distance, 6),
                    "required_distance": round(v.required_distance, 6),
                })
                if len(result_violations) >= max_results:
                    break

        return {
            "violations": result_violations,
            "total": len(self._drc_result.violations),
            "in_viewport": len(result_violations),
        }

    def clear(self) -> None:
        self._db = LayoutDatabase()
        self._spatial_index = None
        self._lef_path = None
        self._def_path = None
        self._drc_result = None
        try:
            shutil.rmtree(self.get_upload_dir(), ignore_errors=True)
        except Exception:
            pass
