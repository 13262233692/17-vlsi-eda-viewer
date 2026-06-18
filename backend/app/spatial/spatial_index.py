from __future__ import annotations
from typing import List, Dict, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
import sys
import math

from .quadtree import Quadtree, SpatialItem
from ..core.models import Rect, LefData, Layer
from ..core.def_models import (
    DefData,
    Component,
    DefPin,
    RouteSegment,
    NetRoute,
    SpecialNetRoute,
)


ORIENT_ROT = {
    "N": (1, 0, 0, 1),
    "S": (-1, 0, 0, -1),
    "E": (0, 1, -1, 0),
    "W": (0, -1, 1, 0),
    "FN": (-1, 0, 0, 1),
    "FS": (1, 0, 0, -1),
    "FE": (0, 1, 1, 0),
    "FW": (0, -1, -1, 0),
}


def transform_rect(
    rect: Rect,
    px: float,
    py: float,
    orient: str,
    macro_w: float,
    macro_h: float,
) -> Rect:
    a, b, c, d = ORIENT_ROT.get(orient, (1, 0, 0, 1))

    corners = [
        (rect.llx, rect.lly),
        (rect.urx, rect.lly),
        (rect.llx, rect.ury),
        (rect.urx, rect.ury),
    ]

    if orient in ("S", "W", "FN", "FW"):
        corners = [
            (macro_w - x if a != 0 or c != 0 else x,
             macro_h - y if b != 0 or d != 0 else y)
            for (x, y) in corners
        ]

    xs: List[float] = []
    ys: List[float] = []
    for (x, y) in corners:
        nx = a * x + b * y + px
        ny = c * x + d * y + py
        xs.append(nx)
        ys.append(ny)

    return Rect(
        llx=min(xs),
        lly=min(ys),
        urx=max(xs),
        ury=max(ys),
    )


@dataclass
class RenderShape:
    shape_type: str
    layer: str
    bbox: Rect
    vertices: List[Tuple[float, float]]
    net_name: str = ""
    instance_name: str = ""
    pin_name: str = ""
    is_via: bool = False


@dataclass
class SpatialIndexStats:
    component_count: int = 0
    pin_count: int = 0
    routing_segment_count: int = 0
    via_count: int = 0
    total_shapes: int = 0
    layer_shape_counts: Dict[str, int] = field(default_factory=dict)


def segment_to_rects(seg: RouteSegment, default_width: float = 0.1) -> List[Rect]:
    rects: List[Rect] = []
    points = seg.points
    width = seg.width if seg.width > 0 else default_width
    half_w = width / 2.0

    if len(points) < 2:
        if len(points) == 1:
            p = points[0]
            rects.append(Rect(
                llx=p[0] - half_w,
                lly=p[1] - half_w,
                urx=p[0] + half_w,
                ury=p[1] + half_w,
            ))
        return rects

    for i in range(len(points) - 1):
        p1 = points[i]
        p2 = points[i + 1]
        min_x = min(p1[0], p2[0]) - half_w
        min_y = min(p1[1], p2[1]) - half_w
        max_x = max(p1[0], p2[0]) + half_w
        max_y = max(p1[1], p2[1]) + half_w
        rects.append(Rect(llx=min_x, lly=min_y, urx=max_x, ury=max_y))

    return rects


def make_rect_vertices(r: Rect) -> List[Tuple[float, float]]:
    return [
        (r.llx, r.lly),
        (r.urx, r.lly),
        (r.urx, r.ury),
        (r.llx, r.ury),
    ]


LAYER_COLORS = {
    "M1": (0.3, 0.6, 0.9, 0.8),
    "M2": (0.9, 0.5, 0.3, 0.8),
    "M3": (0.3, 0.9, 0.5, 0.8),
    "M4": (0.9, 0.3, 0.7, 0.8),
    "M5": (0.7, 0.7, 0.2, 0.8),
    "M6": (0.5, 0.3, 0.9, 0.8),
    "M7": (0.2, 0.8, 0.8, 0.8),
    "M8": (0.8, 0.2, 0.2, 0.8),
    "M9": (0.2, 0.8, 0.2, 0.8),
    "M10": (0.8, 0.8, 0.2, 0.8),
    "METAL1": (0.3, 0.6, 0.9, 0.8),
    "METAL2": (0.9, 0.5, 0.3, 0.8),
    "METAL3": (0.3, 0.9, 0.5, 0.8),
    "METAL4": (0.9, 0.3, 0.7, 0.8),
    "METAL5": (0.7, 0.7, 0.2, 0.8),
    "POLY": (0.4, 0.4, 0.4, 0.8),
    "POL": (0.4, 0.4, 0.4, 0.8),
    "DIFF": (0.6, 0.4, 0.2, 0.8),
    "DIFFUSION": (0.6, 0.4, 0.2, 0.8),
    "NW": (0.7, 0.4, 0.8, 0.6),
    "NWELL": (0.7, 0.4, 0.8, 0.6),
    "PW": (0.4, 0.7, 0.8, 0.6),
    "PWELL": (0.4, 0.7, 0.8, 0.6),
    "CT": (0.9, 0.9, 0.3, 0.9),
    "CONT": (0.9, 0.9, 0.3, 0.9),
    "CONTACT": (0.9, 0.9, 0.3, 0.9),
    "V1": (0.95, 0.95, 0.3, 0.9),
    "VIA1": (0.95, 0.95, 0.3, 0.9),
    "V2": (0.3, 0.95, 0.95, 0.9),
    "VIA2": (0.3, 0.95, 0.95, 0.9),
    "V3": (0.95, 0.3, 0.95, 0.9),
    "VIA3": (0.95, 0.3, 0.95, 0.9),
    "V4": (0.5, 0.5, 0.5, 0.9),
    "VIA4": (0.5, 0.5, 0.5, 0.9),
    "V5": (0.7, 0.7, 0.7, 0.9),
    "VIA5": (0.7, 0.7, 0.7, 0.9),
    "OV": (0.8, 0.8, 0.2, 0.9),
    "OVERLAP": (0.8, 0.8, 0.2, 0.9),
    "VDD": (0.2, 0.2, 0.9, 0.9),
    "VSS": (0.9, 0.2, 0.2, 0.9),
    "NP": (0.6, 0.3, 0.3, 0.6),
    "NPLUS": (0.6, 0.3, 0.3, 0.6),
    "PP": (0.3, 0.3, 0.6, 0.6),
    "PPLUS": (0.3, 0.3, 0.6, 0.6),
}

LAYER_COLOR_LIST = [
    (0.30, 0.50, 0.80, 0.80),
    (0.85, 0.40, 0.30, 0.80),
    (0.30, 0.75, 0.40, 0.80),
    (0.80, 0.30, 0.65, 0.80),
    (0.65, 0.65, 0.20, 0.80),
    (0.45, 0.25, 0.85, 0.80),
    (0.20, 0.75, 0.75, 0.80),
    (0.75, 0.20, 0.20, 0.80),
    (0.20, 0.75, 0.20, 0.80),
    (0.75, 0.75, 0.20, 0.80),
    (0.70, 0.30, 0.50, 0.80),
    (0.30, 0.70, 0.50, 0.80),
    (0.50, 0.50, 0.50, 0.80),
    (0.90, 0.60, 0.20, 0.80),
    (0.60, 0.20, 0.90, 0.80),
]


def get_layer_color(layer_name: str) -> Tuple[float, float, float, float]:
    key = layer_name.upper()
    if key in LAYER_COLORS:
        return LAYER_COLORS[key]
    h = 0
    for c in layer_name:
        h = (h * 31 + ord(c)) % (len(LAYER_COLOR_LIST) * 1000)
    return LAYER_COLOR_LIST[h % len(LAYER_COLOR_LIST)]


class SpatialIndexManager:
    def __init__(self, bounds: Optional[Rect] = None):
        self._quadtree: Optional[Quadtree[RenderShape]] = None
        self._lef_data: Optional[LefData] = None
        self._def_data: Optional[DefData] = None
        self._stats = SpatialIndexStats()
        self._layer_colors: Dict[str, Tuple[float, float, float, float]] = {}
        self._layer_list: List[str] = []
        self._chip_bbox: Rect = bounds or Rect(llx=0, lly=0, urx=1000, ury=1000)

    @property
    def quadtree(self) -> Optional[Quadtree[RenderShape]]:
        return self._quadtree

    @property
    def chip_bbox(self) -> Rect:
        return self._chip_bbox

    @property
    def stats(self) -> SpatialIndexStats:
        return self._stats

    @property
    def layer_list(self) -> List[str]:
        return self._layer_list

    def get_layer_color(self, layer_name: str) -> Tuple[float, float, float, float]:
        if layer_name not in self._layer_colors:
            self._layer_colors[layer_name] = get_layer_color(layer_name)
        return self._layer_colors[layer_name]

    def _ensure_layer(self, layer_name: str) -> None:
        if layer_name and layer_name not in self._layer_colors:
            self._layer_colors[layer_name] = get_layer_color(layer_name)
            if layer_name not in self._layer_list:
                self._layer_list.append(layer_name)
        if layer_name:
            if layer_name not in self._stats.layer_shape_counts:
                self._stats.layer_shape_counts[layer_name] = 0

    def _inc_layer_count(self, layer_name: str, n: int = 1) -> None:
        if layer_name:
            self._stats.layer_shape_counts[layer_name] = (
                self._stats.layer_shape_counts.get(layer_name, 0) + n
            )
            self._stats.total_shapes += n

    def build(
        self,
        lef_data: LefData,
        def_data: DefData,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> None:
        self._lef_data = lef_data
        self._def_data = def_data

        if def_data.die_area_rect and def_data.die_area_rect.width > 0:
            self._chip_bbox = Rect(
                llx=def_data.die_area_rect.llx - 100,
                lly=def_data.die_area_rect.lly - 100,
                urx=def_data.die_area_rect.urx + 100,
                ury=def_data.die_area_rect.ury + 100,
            )

        for lname in lef_data.layer_order:
            self._ensure_layer(lname)
            if lname in lef_data.layers:
                self._layer_colors[lname] = lef_data.layers[lname].color

        bbox_w = self._chip_bbox.width
        bbox_h = self._chip_bbox.height
        max_dim = max(bbox_w, bbox_h)
        max_depth = max(8, min(16, int(math.log2(max(max_dim / 100, 1))) + 2))

        self._quadtree = Quadtree[RenderShape](
            bounds=self._chip_bbox,
            max_items=128,
            max_depth=max_depth,
        )

        if progress_callback:
            progress_callback("components", 0, len(def_data.components))
        self._index_components(def_data.components, lef_data, progress_callback)

        if progress_callback:
            progress_callback("pins", 0, len(def_data.pins))
        self._index_def_pins(def_data.pins)

        if progress_callback:
            progress_callback("vias", 0, len(def_data.vias))
        self._index_vias(def_data)

        total_nets = len(def_data.nets) + len(def_data.specialnets)
        if progress_callback:
            progress_callback("nets", 0, total_nets)
        self._index_nets(def_data, lef_data, progress_callback)

        print(
            f"[SpatialIndex] Built quadtree with {self._quadtree.total_items} items, "
            f"{self._quadtree.node_count} nodes",
            file=sys.stderr,
        )

    def _index_components(
        self,
        components: List[Component],
        lef_data: LefData,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> None:
        total = len(components)
        for idx, comp in enumerate(components):
            if progress_callback and idx % 10000 == 0:
                progress_callback("components", idx, total)

            macro = lef_data.macros.get(comp.macro_name)
            if not macro:
                continue

            px, py = comp.position
            orient = comp.orientation
            mw, mh = macro.size

            if mw == 0 and macro.bbox.width > 0:
                mw = macro.bbox.width
            if mh == 0 and macro.bbox.height > 0:
                mh = macro.bbox.height

            if mw > 0 and mh > 0:
                inst_bbox = transform_rect(
                    Rect(llx=0, lly=0, urx=mw, ury=mh),
                    px, py, orient, mw, mh
                )
                comp.bbox = inst_bbox

            default_layer = None
            for lname in lef_data.layer_order:
                ltype = lef_data.layers.get(lname)
                if ltype and ltype.layer_type in ("MASTERSLICE", "IMPLANT"):
                    default_layer = lname
                    break

            if comp.bbox.width > 0 and comp.bbox.height > 0:
                layer_name = default_layer or (lef_data.layer_order[0] if lef_data.layer_order else "BBOX")
                self._ensure_layer(layer_name)
                shape = RenderShape(
                    shape_type="instance",
                    layer=layer_name,
                    bbox=comp.bbox,
                    vertices=make_rect_vertices(comp.bbox),
                    instance_name=comp.name,
                )
                item = SpatialItem[RenderShape](
                    bbox=comp.bbox,
                    data=shape,
                    item_type="instance",
                    layer=layer_name,
                )
                self._quadtree.insert(item)
                self._stats.component_count += 1
                self._inc_layer_count(layer_name)

            for pin_name, pin in macro.pins.items():
                for port in pin.ports:
                    self._ensure_layer(port.layer_name)
                    for shape_rect in port.shapes:
                        transformed = transform_rect(shape_rect, px, py, orient, mw, mh)
                        rshape = RenderShape(
                            shape_type="cell_pin",
                            layer=port.layer_name,
                            bbox=transformed,
                            vertices=make_rect_vertices(transformed),
                            instance_name=comp.name,
                            pin_name=pin_name,
                        )
                        item = SpatialItem[RenderShape](
                            bbox=transformed,
                            data=rshape,
                            item_type="cell_pin",
                            layer=port.layer_name,
                        )
                        self._quadtree.insert(item)
                        self._inc_layer_count(port.layer_name)

            for obs in macro.obs:
                self._ensure_layer(obs.layer_name)
                for shape_rect in obs.shapes:
                    transformed = transform_rect(shape_rect, px, py, orient, mw, mh)
                    rshape = RenderShape(
                        shape_type="obstruction",
                        layer=obs.layer_name,
                        bbox=transformed,
                        vertices=make_rect_vertices(transformed),
                        instance_name=comp.name,
                    )
                    item = SpatialItem[RenderShape](
                        bbox=transformed,
                        data=rshape,
                        item_type="obstruction",
                        layer=obs.layer_name,
                    )
                    self._quadtree.insert(item)
                    self._inc_layer_count(obs.layer_name)

    def _index_def_pins(self, pins: List[DefPin]) -> None:
        for pin in pins:
            for shape in pin.shapes:
                self._ensure_layer(pin.layer_name)
                rshape = RenderShape(
                    shape_type="io_pin",
                    layer=pin.layer_name or "PIN",
                    bbox=shape,
                    vertices=make_rect_vertices(shape),
                    pin_name=pin.name,
                    net_name=pin.net_name,
                )
                item = SpatialItem[RenderShape](
                    bbox=shape,
                    data=rshape,
                    item_type="io_pin",
                    layer=pin.layer_name or "PIN",
                )
                self._quadtree.insert(item)
                self._stats.pin_count += 1
                self._inc_layer_count(pin.layer_name or "PIN")

    def _index_vias(self, def_data: DefData) -> None:
        for via_name, via in def_data.vias.items():
            for layer_name, shapes in via.shapes.items():
                self._ensure_layer(layer_name)
                self._stats.via_count += 1

    def _index_nets(
        self,
        def_data: DefData,
        lef_data: LefData,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> None:
        total_nets = len(def_data.nets) + len(def_data.specialnets)
        processed = 0

        for net in def_data.nets:
            if progress_callback and processed % 10000 == 0:
                progress_callback("nets", processed, total_nets)
            processed += 1
            self._index_net_route(net, lef_data, def_data)

        for net in def_data.specialnets:
            if progress_callback and processed % 1000 == 0:
                progress_callback("specialnets", processed, total_nets)
            processed += 1
            self._index_net_route(net, lef_data, def_data)

    def _index_net_route(
        self,
        net: NetRoute | SpecialNetRoute,
        lef_data: LefData,
        def_data: DefData,
    ) -> None:
        default_widths: Dict[str, float] = {}
        for lname, layer in lef_data.layers.items():
            if layer.width and layer.width > 0:
                default_widths[lname] = layer.width
            else:
                default_widths[lname] = 0.1

        for seg in net.segments:
            if seg.via_name:
                via = def_data.vias.get(seg.via_name)
                if via:
                    for layer_name, shapes in via.shapes.items():
                        self._ensure_layer(layer_name)
                        for via_shape in shapes:
                            if seg.points:
                                base_p = seg.points[0]
                            else:
                                base_p = (0, 0)
                            cx = (via_shape.llx + via_shape.urx) / 2.0
                            cy = (via_shape.lly + via_shape.ury) / 2.0
                            shifted = Rect(
                                llx=via_shape.llx - cx + base_p[0],
                                lly=via_shape.lly - cy + base_p[1],
                                urx=via_shape.urx - cx + base_p[0],
                                ury=via_shape.ury - cy + base_p[1],
                            )
                            rshape = RenderShape(
                                shape_type="via",
                                layer=layer_name,
                                bbox=shifted,
                                vertices=make_rect_vertices(shifted),
                                net_name=net.net_name,
                                is_via=True,
                            )
                            item = SpatialItem[RenderShape](
                                bbox=shifted,
                                data=rshape,
                                item_type="via",
                                layer=layer_name,
                            )
                            self._quadtree.insert(item)
                            self._stats.routing_segment_count += 1
                            self._inc_layer_count(layer_name)
            else:
                layer = seg.layer_name
                self._ensure_layer(layer)
                dw = default_widths.get(layer, 0.1)
                rects = segment_to_rects(seg, dw)
                for rect in rects:
                    rshape = RenderShape(
                        shape_type="wire",
                        layer=layer,
                        bbox=rect,
                        vertices=make_rect_vertices(rect),
                        net_name=net.net_name,
                    )
                    item = SpatialItem[RenderShape](
                        bbox=rect,
                        data=rshape,
                        item_type="wire",
                        layer=layer,
                    )
                    self._quadtree.insert(item)
                    self._stats.routing_segment_count += 1
                    self._inc_layer_count(layer)

    def query(
        self,
        rect: Rect,
        layers: Optional[List[str]] = None,
        item_types: Optional[List[str]] = None,
        max_results: Optional[int] = None,
    ) -> List[RenderShape]:
        if not self._quadtree:
            return []

        def _filter(item: SpatialItem[RenderShape]) -> bool:
            if layers and item.layer not in layers:
                return False
            if item_types and item.item_type not in item_types:
                return False
            return True

        items = self._quadtree.query(rect, _filter, max_results)
        return [it.data for it in items]

    def query_tile(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        layers: Optional[List[str]] = None,
        max_results: Optional[int] = None,
    ) -> Dict[str, List[Any]]:
        rect = Rect(llx=x, lly=y, urx=x + w, ury=y + h)
        shapes = self.query(rect, layers=layers, max_results=max_results)

        result: Dict[str, List[Any]] = {}
        for s in shapes:
            if s.layer not in result:
                result[s.layer] = []
            verts = s.vertices
            result[s.layer].append({
                "type": s.shape_type,
                "bbox": [s.bbox.llx, s.bbox.lly, s.bbox.urx, s.bbox.ury],
                "verts": [[v[0], v[1]] for v in verts],
                "net": s.net_name,
                "inst": s.instance_name,
                "pin": s.pin_name,
                "via": s.is_via,
            })
        return result

    def get_layer_info(self) -> List[Dict[str, Any]]:
        result = []
        for lname in self._layer_list:
            color = self.get_layer_color(lname)
            count = self._stats.layer_shape_counts.get(lname, 0)
            result.append({
                "name": lname,
                "color": list(color),
                "count": count,
                "visible": True,
            })
        return result
