from __future__ import annotations
from typing import List, Dict, Tuple, Optional, Callable
from dataclasses import dataclass, field
import sys
import time

from ..core.models import Rect, LefData
from ..core.def_models import DefData, NetRoute, SpecialNetRoute
from ..spatial.spatial_index import RenderShape, segment_to_rects, make_rect_vertices
from .drc_rules import DRCRuleSet


@dataclass
class DRCViolation:
    rule_type: str
    layer: str
    bbox: Rect
    severity: str = "error"
    message: str = ""
    net1: str = ""
    net2: str = ""
    shape1_type: str = ""
    shape2_type: str = ""
    actual_distance: float = 0.0
    required_distance: float = 0.0
    vertices: List[Tuple[float, float]] = field(default_factory=list)


@dataclass
class DRCResult:
    violations: List[DRCViolation] = field(default_factory=list)
    total_checked: int = 0
    elapsed_seconds: float = 0.0
    error_count: int = 0
    warning_count: int = 0

    def to_dict(self) -> dict:
        return {
            "total_violations": len(self.violations),
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "total_checked": self.total_checked,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "violations": [
                {
                    "rule_type": v.rule_type,
                    "layer": v.layer,
                    "bbox": [v.bbox.llx, v.bbox.lly, v.bbox.urx, v.bbox.ury],
                    "severity": v.severity,
                    "message": v.message,
                    "net1": v.net1,
                    "net2": v.net2,
                    "actual_distance": round(v.actual_distance, 6),
                    "required_distance": round(v.required_distance, 6),
                }
                for v in self.violations
            ],
        }


@dataclass
class _WireRect:
    llx: float
    lly: float
    urx: float
    ury: float
    net_name: str = ""
    layer: str = ""
    is_horizontal: bool = True

    @property
    def cx(self) -> float:
        return (self.llx + self.urx) / 2.0

    @property
    def cy(self) -> float:
        return (self.lly + self.ury) / 2.0


def _rect_distance_x(a: _WireRect, b: _WireRect) -> float:
    if a.urx <= b.llx:
        return b.llx - a.urx
    if b.urx <= a.llx:
        return a.llx - b.urx
    return 0.0


def _rect_distance_y(a: _WireRect, b: _WireRect) -> float:
    if a.ury <= b.lly:
        return b.lly - a.ury
    if b.ury <= a.lly:
        return a.lly - b.ury
    return 0.0


def _rect_min_distance(a: _WireRect, b: _WireRect) -> float:
    dx = _rect_distance_x(a, b)
    dy = _rect_distance_y(a, b)
    if dx > 0 and dy > 0:
        return (dx * dx + dy * dy) ** 0.5
    return max(dx, dy)


def _y_overlap(a: _WireRect, b: _WireRect) -> float:
    return max(0.0, min(a.ury, b.ury) - max(a.lly, b.lly))


def _x_overlap(a: _WireRect, b: _WireRect) -> float:
    return max(0.0, min(a.urx, b.urx) - max(a.llx, b.llx))


class DRCEngine:
    def __init__(self, rules: Optional[DRCRuleSet] = None):
        self.rules = rules or DRCRuleSet()
        self._result = DRCResult()

    def run(
        self,
        lef_data: LefData,
        def_data: DefData,
        progress_cb: Optional[Callable[[str, int, int], None]] = None,
    ) -> DRCResult:
        t0 = time.time()
        self._result = DRCResult()

        self.rules.update_from_lef(lef_data)

        wire_rects_by_layer: Dict[str, List[_WireRect]] = {}
        for net in def_data.nets:
            self._collect_wire_rects(net, wire_rects_by_layer)
        for net in def_data.specialnets:
            self._collect_wire_rects(net, wire_rects_by_layer)

        total_layers = len(wire_rects_by_layer)
        processed = 0

        for layer_name, rects in wire_rects_by_layer.items():
            if progress_cb:
                progress_cb("drc_same_layer", processed, total_layers)
            processed += 1

            min_spacing = self.rules.get_spacing(layer_name)
            self._check_same_layer_spacing(layer_name, rects, min_spacing)

        if progress_cb:
            progress_cb("drc_inter_layer", 0, 1)

        self._check_interlayer_spacing(wire_rects_by_layer, lef_data)

        self._result.total_checked = sum(len(r) for r in wire_rects_by_layer.values())
        self._result.elapsed_seconds = time.time() - t0
        self._result.error_count = sum(
            1 for v in self._result.violations if v.severity == "error"
        )
        self._result.warning_count = sum(
            1 for v in self._result.violations if v.severity == "warning"
        )

        print(
            f"[DRC] Found {len(self._result.violations)} violations "
            f"({self._result.error_count} errors, {self._result.warning_count} warnings) "
            f"in {self._result.elapsed_seconds:.2f}s, "
            f"checked {self._result.total_checked} shapes",
            file=sys.stderr,
        )

        return self._result

    def _collect_wire_rects(
        self,
        net: NetRoute | SpecialNetRoute,
        result: Dict[str, List[_WireRect]],
    ) -> None:
        for seg in net.segments:
            if seg.via_name:
                continue
            layer = seg.layer_name
            if not layer:
                continue
            if layer not in result:
                result[layer] = []
            dw = 0.1
            rects = segment_to_rects(seg, dw)
            for r in rects:
                is_h = r.width >= r.height
                result[layer].append(_WireRect(
                    llx=r.llx,
                    lly=r.lly,
                    urx=r.urx,
                    ury=r.ury,
                    net_name=net.net_name,
                    layer=layer,
                    is_horizontal=is_h,
                ))

    def _check_same_layer_spacing(
        self,
        layer_name: str,
        rects: List[_WireRect],
        min_spacing: float,
    ) -> None:
        if min_spacing <= 0 or len(rects) < 2:
            return

        sorted_rects = sorted(rects, key=lambda r: r.llx)
        n = len(sorted_rects)

        active: List[_WireRect] = []

        for i in range(n):
            current = sorted_rects[i]

            new_active = []
            for a in active:
                if a.urx + min_spacing >= current.llx:
                    new_active.append(a)
            active = new_active

            for a in active:
                if a.net_name and a.net_name == current.net_name:
                    continue

                dx = _rect_distance_x(a, current)
                if dx >= min_spacing:
                    continue

                if _y_overlap(a, current) <= 0:
                    continue

                if dx > 0:
                    dist = dx
                    if dist < min_spacing:
                        self._add_spacing_violation(
                            layer_name, a, current, dist, min_spacing
                        )
                else:
                    dy = _rect_distance_y(a, current)
                    if 0 < dy < min_spacing:
                        self._add_spacing_violation(
                            layer_name, a, current, dy, min_spacing
                        )

            active.append(current)

    def _add_spacing_violation(
        self,
        layer_name: str,
        a: _WireRect,
        b: _WireRect,
        actual: float,
        required: float,
    ) -> None:
        gap_llx = min(a.urx, b.urx) if _rect_distance_x(a, b) > 0 else min(a.llx, b.llx)
        gap_urx = max(a.llx, b.llx) if _rect_distance_x(a, b) > 0 else max(a.urx, b.urx)
        gap_lly = max(a.lly, b.lly)
        gap_ury = min(a.ury, b.ury)

        if gap_ury <= gap_lly:
            gap_llx = min(a.llx, b.llx)
            gap_urx = max(a.urx, b.urx)
            gap_lly = min(a.ury, b.ury) if a.ury <= b.lly else min(b.ury, a.lly)
            gap_ury = max(a.ury, b.ury) if a.ury <= b.lly else max(b.ury, a.lly)
            if gap_ury <= gap_lly:
                cx = (a.cx + b.cx) / 2
                cy = (a.cy + b.cy) / 2
                gap_llx = cx - required
                gap_lly = cy - required
                gap_urx = cx + required
                gap_ury = cy + required

        expand = required * 0.5
        gap_llx -= expand
        gap_lly -= expand
        gap_urx += expand
        gap_ury += expand

        bbox = Rect(llx=gap_llx, lly=gap_lly, urx=gap_urx, ury=gap_ury)

        is_same_net = a.net_name and a.net_name == b.net_name
        severity = "warning" if is_same_net else "error"

        self._result.violations.append(DRCViolation(
            rule_type="min_spacing",
            layer=layer_name,
            bbox=bbox,
            severity=severity,
            message=f"Min spacing violation on {layer_name}: {actual:.4f} < {required:.4f}",
            net1=a.net_name or "?",
            net2=b.net_name or "?",
            actual_distance=actual,
            required_distance=required,
            vertices=make_rect_vertices(bbox),
        ))

    def _check_interlayer_spacing(
        self,
        wire_rects_by_layer: Dict[str, List[_WireRect]],
        lef_data: LefData,
    ) -> None:
        layer_order = lef_data.layer_order
        for i in range(len(layer_order) - 1):
            l1 = layer_order[i]
            l2 = layer_order[i + 1]
            if l1 not in wire_rects_by_layer or l2 not in wire_rects_by_layer:
                continue

            inter_spacing = self.rules.get_interlayer_spacing(l1, l2)
            if inter_spacing <= 0:
                continue

            l1_type = lef_data.layers.get(l1)
            l2_type = lef_data.layers.get(l2)
            if not l1_type or not l2_type:
                continue

            if l1_type.routing_direction == l2_type.routing_direction:
                if l1_type.routing_direction == "HORIZONTAL":
                    self._check_perpendicular_layer_spacing(
                        l1, wire_rects_by_layer[l1],
                        l2, wire_rects_by_layer[l2],
                        inter_spacing,
                    )
                else:
                    self._check_perpendicular_layer_spacing(
                        l2, wire_rects_by_layer[l2],
                        l1, wire_rects_by_layer[l1],
                        inter_spacing,
                    )

    def _check_perpendicular_layer_spacing(
        self,
        horiz_layer: str,
        horiz_rects: List[_WireRect],
        vert_layer: str,
        vert_rects: List[_WireRect],
        min_spacing: float,
    ) -> None:
        if len(horiz_rects) > len(vert_rects):
            sorted_h = sorted(horiz_rects, key=lambda r: r.lly)
            sweep = vert_rects
        else:
            sorted_h = horiz_rects
            sweep = sorted(vert_rects, key=lambda r: r.lly)

        max_violations = 2000
        count = 0

        for vr in sweep:
            if count >= max_violations:
                break
            lo = vr.lly - min_spacing
            hi = vr.ury + min_spacing

            left = 0
            right = len(sorted_h)
            while left < right:
                mid = (left + right) // 2
                if sorted_h[mid].lly < lo:
                    left = mid + 1
                else:
                    right = mid

            for j in range(left, len(sorted_h)):
                hr = sorted_h[j]
                if hr.lly > hi:
                    break

                if hr.net_name and hr.net_name == vr.net_name:
                    continue

                dx = _rect_distance_x(hr, vr)
                dy = _rect_distance_y(hr, vr)
                if dx > 0 and dy > 0:
                    dist = (dx * dx + dy * dy) ** 0.5
                    if dist < min_spacing:
                        self._add_interlayer_violation(
                            horiz_layer, vert_layer, hr, vr, dist, min_spacing
                        )
                        count += 1

    def _add_interlayer_violation(
        self,
        l1: str,
        l2: str,
        a: _WireRect,
        b: _WireRect,
        actual: float,
        required: float,
    ) -> None:
        cx = (a.cx + b.cx) / 2
        cy = (a.cy + b.cy) / 2
        expand = required * 0.5
        bbox = Rect(
            llx=cx - expand,
            lly=cy - expand,
            urx=cx + expand,
            ury=cy + expand,
        )
        self._result.violations.append(DRCViolation(
            rule_type="interlayer_spacing",
            layer=f"{l1}/{l2}",
            bbox=bbox,
            severity="warning",
            message=f"Inter-layer spacing ({l1}/{l2}): {actual:.4f} < {required:.4f}",
            net1=a.net_name or "?",
            net2=b.net_name or "?",
            actual_distance=actual,
            required_distance=required,
            vertices=make_rect_vertices(bbox),
        ))
