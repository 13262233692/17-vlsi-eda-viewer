from __future__ import annotations
from typing import List, Tuple, Optional, Dict, Any
from pydantic import BaseModel, Field


class Rect(BaseModel):
    llx: float = 0.0
    lly: float = 0.0
    urx: float = 0.0
    ury: float = 0.0

    @property
    def width(self) -> float:
        return self.urx - self.llx

    @property
    def height(self) -> float:
        return self.ury - self.lly

    @property
    def cx(self) -> float:
        return (self.llx + self.urx) / 2.0

    @property
    def cy(self) -> float:
        return (self.lly + self.ury) / 2.0

    def intersects(self, other: "Rect") -> bool:
        return not (
            self.urx < other.llx
            or self.llx > other.urx
            or self.ury < other.lly
            or self.lly > other.ury
        )

    def contains_point(self, x: float, y: float) -> bool:
        return self.llx <= x <= self.urx and self.lly <= y <= self.ury

    def to_tuple(self) -> Tuple[float, float, float, float]:
        return (self.llx, self.lly, self.urx, self.ury)


class PortGeometry(BaseModel):
    layer_name: str
    shapes: List[Rect] = Field(default_factory=list)


class Pin(BaseModel):
    name: str
    direction: str = "INOUT"
    use: str = "SIGNAL"
    ports: List[PortGeometry] = Field(default_factory=list)
    bbox: Rect = Field(default_factory=Rect)


class Obstacle(BaseModel):
    layer_name: str
    shapes: List[Rect] = Field(default_factory=list)


class Macro(BaseModel):
    name: str
    class_name: str = ""
    origin: Tuple[float, float] = (0.0, 0.0)
    size: Tuple[float, float] = (0.0, 0.0)
    foreign_name: str = ""
    foreign_origin: Tuple[float, float] = (0.0, 0.0)
    foreign_orient: str = "N"
    pins: Dict[str, Pin] = Field(default_factory=dict)
    obs: List[Obstacle] = Field(default_factory=list)
    bbox: Rect = Field(default_factory=Rect)


class Layer(BaseModel):
    name: str
    layer_type: str = ""
    routing_direction: str = "HORIZONTAL"
    pitch: Optional[float] = None
    width: Optional[float] = None
    offset: Optional[float] = None
    color: Tuple[float, float, float, float] = (0.5, 0.5, 0.5, 0.8)


class Site(BaseModel):
    name: str
    class_name: str = ""
    size: Tuple[float, float] = (0.0, 0.0)


class LefData(BaseModel):
    version: str = "5.8"
    divider_char: str = "/"
    busbit_chars: str = "[]"
    manufacturing_grid: float = 0.001
    units_distance_microns: int = 2000
    layers: Dict[str, Layer] = Field(default_factory=dict)
    sites: Dict[str, Site] = Field(default_factory=dict)
    macros: Dict[str, Macro] = Field(default_factory=dict)
    layer_order: List[str] = Field(default_factory=list)
