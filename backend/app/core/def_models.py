from __future__ import annotations
from typing import List, Tuple, Optional, Dict, Any
from pydantic import BaseModel, Field
from .models import Rect


class Component(BaseModel):
    name: str
    macro_name: str
    source: str = "NETLIST"
    placement_status: str = "UNPLACED"
    position: Tuple[float, float] = (0.0, 0.0)
    orientation: str = "N"
    bbox: Rect = Field(default_factory=Rect)


class DefPin(BaseModel):
    name: str
    net_name: str = ""
    direction: str = "INOUT"
    use: str = "SIGNAL"
    layer_name: str = ""
    shapes: List[Rect] = Field(default_factory=list)
    placement_status: str = "UNPLACED"
    position: Tuple[float, float] = (0.0, 0.0)
    orientation: str = "N"
    bbox: Rect = Field(default_factory=Rect)


class Via(BaseModel):
    name: str
    layers: List[str] = Field(default_factory=list)
    shapes: Dict[str, List[Rect]] = Field(default_factory=dict)


class RouteSegment(BaseModel):
    layer_name: str
    points: List[Tuple[float, float]] = Field(default_factory=list)
    width: float = 0.0
    via_name: str = ""
    mask_color: int = 0


class NetRoute(BaseModel):
    net_name: str
    segments: List[RouteSegment] = Field(default_factory=list)


class SpecialNetRoute(BaseModel):
    net_name: str
    segments: List[RouteSegment] = Field(default_factory=list)


class DefData(BaseModel):
    version: str = "5.8"
    divider_char: str = "/"
    busbit_chars: str = "[]"
    design_name: str = ""
    units_dbu_per_micron: int = 2000
    die_area: Tuple[Tuple[float, float], Tuple[float, float]] = ((0.0, 0.0), (0.0, 0.0))
    die_area_rect: Rect = Field(default_factory=Rect)
    components: List[Component] = Field(default_factory=list)
    pins: List[DefPin] = Field(default_factory=list)
    vias: Dict[str, Via] = Field(default_factory=dict)
    nets: List[NetRoute] = Field(default_factory=list)
    specialnets: List[SpecialNetRoute] = Field(default_factory=list)
    row_count: int = 0
    track_count: int = 0
    gcell_count: int = 0


class LayoutDatabase(BaseModel):
    lef_data: Optional[Any] = None
    def_data: Optional[DefData] = None
    is_loaded: bool = False
    chip_bbox: Rect = Field(default_factory=Rect)
    total_components: int = 0
    total_pins: int = 0
    total_nets: int = 0
    total_routing_segments: int = 0
