from __future__ import annotations
from typing import List, Tuple, Optional, Dict, Any, Generic, TypeVar, Callable
from dataclasses import dataclass, field
import math

from ..core.models import Rect


T = TypeVar("T")


DEFAULT_MAX_ITEMS = 64
DEFAULT_MAX_DEPTH = 12


@dataclass
class SpatialItem(Generic[T]):
    bbox: Rect
    data: T
    item_type: str = ""
    layer: str = ""

    def intersects(self, query: Rect) -> bool:
        return self.bbox.intersects(query)


@dataclass
class QuadtreeNode(Generic[T]):
    bbox: Rect
    depth: int = 0
    items: List[SpatialItem[T]] = field(default_factory=list)
    children: Optional[List["QuadtreeNode[T]"]] = None
    is_leaf: bool = True

    def has_children(self) -> bool:
        return self.children is not None and len(self.children) > 0

    def is_overflow(self, max_items: int, max_depth: int) -> bool:
        return len(self.items) > max_items and self.depth < max_depth


class Quadtree(Generic[T]):
    def __init__(
        self,
        bounds: Rect,
        max_items: int = DEFAULT_MAX_ITEMS,
        max_depth: int = DEFAULT_MAX_DEPTH,
    ):
        self._root: QuadtreeNode[T] = QuadtreeNode(bbox=bounds, depth=0)
        self._max_items = max_items
        self._max_depth = max_depth
        self._total_items: int = 0
        self._node_count: int = 1

    @property
    def bounds(self) -> Rect:
        return self._root.bbox

    @property
    def total_items(self) -> int:
        return self._total_items

    @property
    def node_count(self) -> int:
        return self._node_count

    def _subdivide(self, node: QuadtreeNode[T]) -> None:
        if node.has_children():
            return

        b = node.bbox
        mid_x = (b.llx + b.urx) / 2.0
        mid_y = (b.lly + b.ury) / 2.0

        children_bboxes = [
            Rect(llx=mid_x, lly=mid_y, urx=b.urx, ury=b.ury),
            Rect(llx=b.llx, lly=mid_y, urx=mid_x, ury=b.ury),
            Rect(llx=b.llx, lly=b.lly, urx=mid_x, ury=mid_y),
            Rect(llx=mid_x, lly=b.lly, urx=b.urx, ury=mid_y),
        ]

        node.children = [
            QuadtreeNode(bbox=bbox, depth=node.depth + 1) for bbox in children_bboxes
        ]
        self._node_count += 4
        node.is_leaf = False

        old_items = node.items
        node.items = []
        for item in old_items:
            self._insert_into_children(node, item)

    def _insert_into_children(self, node: QuadtreeNode[T], item: SpatialItem[T]) -> bool:
        if not node.children:
            return False

        inserted = False
        for child in node.children:
            if child.bbox.intersects(item.bbox):
                self._insert_recursive(child, item)
                inserted = True
        return inserted

    def _insert_recursive(self, node: QuadtreeNode[T], item: SpatialItem[T]) -> None:
        if node.is_leaf:
            node.items.append(item)
            if node.is_overflow(self._max_items, self._max_depth):
                self._subdivide(node)
        else:
            if not self._insert_into_children(node, item):
                node.items.append(item)

    def insert(self, item: SpatialItem[T]) -> bool:
        if not self._root.bbox.intersects(item.bbox):
            expanded = Rect(
                llx=min(self._root.bbox.llx, item.bbox.llx),
                lly=min(self._root.bbox.lly, item.bbox.lly),
                urx=max(self._root.bbox.urx, item.bbox.urx),
                ury=max(self._root.bbox.ury, item.bbox.ury),
            )
            if expanded.width > self._root.bbox.width * 4 or expanded.height > self._root.bbox.height * 4:
                return False
            return False
        self._insert_recursive(self._root, item)
        self._total_items += 1
        return True

    def insert_bulk(self, items: List[SpatialItem[T]]) -> int:
        count = 0
        for item in items:
            if self.insert(item):
                count += 1
        return count

    def query(
        self,
        query_rect: Rect,
        filter_fn: Optional[Callable[[SpatialItem[T]], bool]] = None,
        max_results: Optional[int] = None,
    ) -> List[SpatialItem[T]]:
        results: List[SpatialItem[T]] = []
        self._query_recursive(self._root, query_rect, results, filter_fn, max_results)
        return results

    def _query_recursive(
        self,
        node: QuadtreeNode[T],
        query_rect: Rect,
        results: List[SpatialItem[T]],
        filter_fn: Optional[Callable[[SpatialItem[T]], bool]],
        max_results: Optional[int],
    ) -> None:
        if max_results is not None and len(results) >= max_results:
            return

        if not node.bbox.intersects(query_rect):
            return

        for item in node.items:
            if max_results is not None and len(results) >= max_results:
                return
            if item.intersects(query_rect):
                if filter_fn is None or filter_fn(item):
                    results.append(item)

        if node.children:
            for child in node.children:
                self._query_recursive(child, query_rect, results, filter_fn, max_results)

    def query_count(
        self,
        query_rect: Rect,
        filter_fn: Optional[Callable[[SpatialItem[T]], bool]] = None,
    ) -> int:
        return len(self.query(query_rect, filter_fn))

    def get_tile(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        filter_fn: Optional[Callable[[SpatialItem[T]], bool]] = None,
    ) -> List[SpatialItem[T]]:
        rect = Rect(llx=x, lly=y, urx=x + width, ury=y + height)
        return self.query(rect, filter_fn)

    def get_stats(self) -> Dict[str, Any]:
        counts = {"depth_counts": {}, "type": {}}

        def _walk(node: QuadtreeNode[T], depth: int) -> None:
            d = str(depth)
            if d not in counts["depth_counts"]:
                counts["depth_counts"][d] = {"nodes": 0, "items": 0, "leaves": 0}
            counts["depth_counts"][d]["nodes"] += 1
            counts["depth_counts"][d]["items"] += len(node.items)
            if node.is_leaf:
                counts["depth_counts"][d]["leaves"] += 1
            if node.children:
                for child in node.children:
                    _walk(child, depth + 1)

        _walk(self._root, 0)
        counts["total_items"] = self._total_items
        counts["total_nodes"] = self._node_count
        return counts

    def clear(self) -> None:
        self._root.items = []
        self._root.children = None
        self._root.is_leaf = True
        self._total_items = 0
        self._node_count = 1
