from __future__ import annotations
from typing import List, Optional, Tuple, Dict
import os
import sys

from .def_lexer import DefLexer, DefTokenObj, DefToken
from ..core.models import Rect
from ..core.def_models import (
    DefData,
    Component,
    DefPin,
    Via,
    NetRoute,
    RouteSegment,
    SpecialNetRoute,
)


class DefParser:
    def __init__(self):
        self._tokens: List[DefTokenObj] = []
        self._pos: int = 0
        self._def = DefData()

    def _current(self) -> DefTokenObj:
        return self._tokens[self._pos]

    def _peek(self, offset: int = 1) -> DefTokenObj:
        idx = self._pos + offset
        if idx < len(self._tokens):
            return self._tokens[idx]
        return self._tokens[-1]

    def _consume(self) -> DefTokenObj:
        tok = self._tokens[self._pos]
        self._pos += 1
        return tok

    def _expect(self, token_type: str) -> DefTokenObj:
        tok = self._consume()
        if tok.type != token_type:
            raise SyntaxError(
                f"Expected {token_type}, got {tok.type} ('{tok.value}') "
                f"at line {tok.line}, col {tok.col}"
            )
        return tok

    def _check(self, token_type: str) -> bool:
        return self._current().type == token_type

    def _check_value(self, value: str) -> bool:
        return self._current().value.upper() == value.upper()

    def _skip_to_semicolon(self) -> None:
        depth = 0
        while self._pos < len(self._tokens):
            if self._check(DefToken.LPAREN):
                depth += 1
            elif self._check(DefToken.RPAREN):
                if depth == 0:
                    break
                depth -= 1
            elif self._check(DefToken.SEMICOLON) and depth == 0:
                self._consume()
                return
            self._consume()
        if self._pos < len(self._tokens) and self._check(DefToken.SEMICOLON):
            self._consume()

    def _parse_number(self) -> float:
        tok = self._expect(DefToken.NUMBER)
        try:
            return float(tok.value)
        except ValueError:
            return 0.0

    def _parse_identifier(self) -> str:
        if self._check(DefToken.IDENTIFIER):
            return self._consume().value
        elif self._check(DefToken.STRING):
            return self._consume().value
        else:
            return self._consume().value

    def _parse_point(self) -> Tuple[float, float]:
        self._expect(DefToken.LPAREN)
        x = self._parse_number()
        y = self._parse_number()
        self._expect(DefToken.RPAREN)
        return (x, y)

    def _parse_header(self) -> None:
        while self._pos < len(self._tokens):
            tok = self._current()
            if tok.type == DefToken.VERSION:
                self._consume()
                if self._check(DefToken.NUMBER) or self._check(DefToken.IDENTIFIER):
                    self._def.version = self._consume().value
                self._skip_to_semicolon()
            elif tok.type == DefToken.DIVIDERCHAR:
                self._consume()
                val = self._consume().value.strip('"')
                if val:
                    self._def.divider_char = val[0]
                self._skip_to_semicolon()
            elif tok.type == DefToken.BUSBITCHARS:
                self._consume()
                val = self._consume().value.strip('"')
                if val:
                    self._def.busbit_chars = val
                self._skip_to_semicolon()
            elif tok.type == DefToken.DESIGN:
                self._consume()
                self._def.design_name = self._parse_identifier()
                self._skip_to_semicolon()
            elif tok.type == DefToken.UNITS:
                self._consume()
                if self._check(DefToken.DISTANCE):
                    self._consume()
                    if self._check(DefToken.MICRONS):
                        self._consume()
                        self._def.units_dbu_per_micron = int(self._parse_number())
                self._skip_to_semicolon()
            elif tok.type == DefToken.DIEAREA:
                self._consume()
                p1 = self._parse_point()
                p2 = self._parse_point()
                self._def.die_area = (p1, p2)
                self._def.die_area_rect = Rect(
                    llx=min(p1[0], p2[0]),
                    lly=min(p1[1], p2[1]),
                    urx=max(p1[0], p2[0]),
                    ury=max(p1[1], p2[1]),
                )
                self._skip_to_semicolon()
            elif tok.type == DefToken.ROWS:
                self._consume()
                self._def.row_count = int(self._parse_number()) if self._check(DefToken.NUMBER) else 0
                self._skip_to_semicolon()
                while not (self._check(DefToken.END) and self._peek().value.upper() == "ROWS"):
                    if self._check(DefToken.ROW):
                        self._consume()
                        self._skip_to_semicolon()
                    elif self._check(DefToken.SEMICOLON):
                        self._consume()
                    elif self._check(DefToken.END):
                        break
                    elif self._check(DefToken.EOF):
                        break
                    else:
                        self._consume()
                if self._check(DefToken.END):
                    self._consume()
                    if self._check_value("ROWS"):
                        self._consume()
                    if self._check(DefToken.SEMICOLON):
                        self._consume()
            elif tok.type == DefToken.TRACKS:
                self._consume()
                self._def.track_count = int(self._parse_number()) if self._check(DefToken.NUMBER) else 0
                self._skip_to_semicolon()
                while not (self._check(DefToken.END) and self._peek().value.upper() == "TRACKS"):
                    if self._check(DefToken.SEMICOLON):
                        self._consume()
                    elif self._check(DefToken.END):
                        break
                    elif self._check(DefToken.EOF):
                        break
                    else:
                        self._consume()
                if self._check(DefToken.END):
                    self._consume()
                    if self._check_value("TRACKS"):
                        self._consume()
                    if self._check(DefToken.SEMICOLON):
                        self._consume()
            elif tok.type == DefToken.GCELLGRID:
                self._consume()
                self._def.gcell_count = int(self._parse_number()) if self._check(DefToken.NUMBER) else 0
                self._skip_to_semicolon()
                while not (self._check(DefToken.END) and self._peek().value.upper() == "GCELLGRID"):
                    if self._check(DefToken.SEMICOLON):
                        self._consume()
                    elif self._check(DefToken.END):
                        break
                    elif self._check(DefToken.EOF):
                        break
                    else:
                        self._consume()
                if self._check(DefToken.END):
                    self._consume()
                    if self._check_value("GCELLGRID"):
                        self._consume()
                    if self._check(DefToken.SEMICOLON):
                        self._consume()
            elif tok.type == DefToken.COMPONENTS:
                self._parse_components()
            elif tok.type == DefToken.PINS:
                self._parse_pins()
            elif tok.type == DefToken.VIAS:
                self._parse_vias()
            elif tok.type == DefToken.NETS:
                self._parse_nets()
            elif tok.type == DefToken.SPECIALNETS:
                self._parse_specialnets()
            elif tok.type == DefToken.EOF:
                break
            else:
                self._skip_to_semicolon()

    def _parse_component_placement(self, comp: Component) -> None:
        if self._check(DefToken.PLACED):
            comp.placement_status = "PLACED"
            self._consume()
        elif self._check(DefToken.FIXED):
            comp.placement_status = "FIXED"
            self._consume()
        elif self._check(DefToken.COVER):
            comp.placement_status = "COVER"
            self._consume()
        elif self._check(DefToken.FIRM):
            comp.placement_status = "FIRM"
            self._consume()
        elif self._check(DefToken.UNPLACED):
            comp.placement_status = "UNPLACED"
            self._consume()
            return

        pos = self._parse_point()
        comp.position = pos
        orient_tok = self._consume()
        comp.orientation = orient_tok.value.upper()

    def _parse_component(self) -> Component:
        name = self._parse_identifier()
        macro_name = self._parse_identifier()
        comp = Component(name=name, macro_name=macro_name)

        while not self._check(DefToken.SEMICOLON):
            if self._check(DefToken.PLUS):
                self._consume()
            elif self._check(DefToken.SOURCE):
                self._consume()
                if self._check(DefToken.NETLIST):
                    comp.source = "NETLIST"
                elif self._check(DefToken.DIST):
                    comp.source = "DIST"
                elif self._check(DefToken.USER):
                    comp.source = "USER"
                else:
                    comp.source = self._consume().value.upper()
            elif (
                self._check(DefToken.PLACED)
                or self._check(DefToken.FIXED)
                or self._check(DefToken.COVER)
                or self._check(DefToken.FIRM)
                or self._check(DefToken.UNPLACED)
            ):
                self._parse_component_placement(comp)
            elif self._check(DefToken.REGION if hasattr(DefToken, "REGION") else "REGION"):
                self._consume()
                self._consume()
            elif self._check(DefToken.PROPERTY):
                self._consume()
                while not self._check(DefToken.SEMICOLON) and not self._check(DefToken.PLUS):
                    self._consume()
            elif self._check(DefToken.IDENTIFIER):
                self._consume()
            elif self._check(DefToken.NUMBER):
                self._consume()
            elif self._check(DefToken.EOF):
                break
            else:
                self._consume()

        if self._check(DefToken.SEMICOLON):
            self._consume()
        return comp

    def _parse_components(self) -> None:
        self._expect(DefToken.COMPONENTS)
        count = 0
        if self._check(DefToken.NUMBER):
            count = int(self._parse_number())
        self._skip_to_semicolon()

        parsed = 0
        while not (self._check(DefToken.END) and self._peek().value.upper() == "COMPONENTS"):
            if self._check(DefToken.SEMICOLON):
                self._consume()
            elif self._check(DefToken.END):
                break
            elif self._check(DefToken.EOF):
                break
            elif self._check(DefToken.IDENTIFIER) or self._check(DefToken.STRING):
                comp = self._parse_component()
                self._def.components.append(comp)
                parsed += 1
                if parsed % 10000 == 0 and parsed > 0:
                    print(f"[DEF Parser] Parsed {parsed}/{count} components...", file=sys.stderr)
            else:
                self._consume()

        if self._check(DefToken.END):
            self._consume()
            if self._check_value("COMPONENTS"):
                self._consume()
            if self._check(DefToken.SEMICOLON):
                self._consume()

    def _parse_pin_shapes(self, pin: DefPin, layer_name: str) -> None:
        DEBUG = False
        while self._check(DefToken.LPAREN):
            if DEBUG: print(f'  [pin_shape] start loop pos={self._pos} cur={self._current()}', flush=True)
            p = self._parse_point()
            if DEBUG: print(f'  [pin_shape] p={p} after pos={self._pos} cur={self._current()}', flush=True)
            if not self._check(DefToken.LPAREN):
                if DEBUG: print(f'  [pin_shape] no 2nd LPAREN, breaking, cur={self._current()}', flush=True)
                break
            p2 = self._parse_point()
            if DEBUG: print(f'  [pin_shape] p2={p2} after pos={self._pos} cur={self._current()}', flush=True)
            rect = Rect(
                llx=min(p[0], p2[0]),
                lly=min(p[1], p2[1]),
                urx=max(p[0], p2[0]),
                ury=max(p[1], p2[1]),
            )
            pin.shapes.append(rect)
            if pin.bbox.llx == 0 and pin.bbox.lly == 0 and pin.bbox.urx == 0 and pin.bbox.ury == 0:
                pin.bbox = Rect(
                    llx=rect.llx,
                    lly=rect.lly,
                    urx=rect.urx,
                    ury=rect.ury,
                )
            else:
                pin.bbox.llx = min(pin.bbox.llx, rect.llx)
                pin.bbox.lly = min(pin.bbox.lly, rect.lly)
                pin.bbox.urx = max(pin.bbox.urx, rect.urx)
                pin.bbox.ury = max(pin.bbox.ury, rect.ury)

    def _parse_pin(self) -> DefPin:
        name = self._parse_identifier()
        pin = DefPin(name=name)

        while not self._check(DefToken.SEMICOLON):
            if self._check(DefToken.PLUS):
                self._consume()
            if self._check(DefToken.NETLIST) or self._check_value("NET"):
                self._consume()
                pin.net_name = self._parse_identifier()
            elif self._check(DefToken.DIRECTION):
                self._consume()
                if self._check(DefToken.INPUT):
                    pin.direction = "INPUT"
                elif self._check(DefToken.OUTPUT):
                    pin.direction = "OUTPUT"
                elif self._check(DefToken.INOUT):
                    pin.direction = "INOUT"
                elif self._check(DefToken.FEEDTHRU):
                    pin.direction = "FEEDTHRU"
                else:
                    pin.direction = self._consume().value.upper()
            elif self._check(DefToken.USE):
                self._consume()
                if self._check(DefToken.SIGNAL):
                    pin.use = "SIGNAL"
                elif self._check(DefToken.POWER):
                    pin.use = "POWER"
                elif self._check(DefToken.GROUND):
                    pin.use = "GROUND"
                elif self._check(DefToken.CLOCK):
                    pin.use = "CLOCK"
                else:
                    pin.use = self._consume().value.upper()
            elif self._check(DefToken.LAYER):
                self._consume()
                layer_name = self._parse_identifier()
                pin.layer_name = layer_name
                self._parse_pin_shapes(pin, layer_name)
            elif (
                self._check(DefToken.PLACED)
                or self._check(DefToken.FIXED)
                or self._check(DefToken.COVER)
            ):
                if self._check(DefToken.PLACED):
                    pin.placement_status = "PLACED"
                elif self._check(DefToken.FIXED):
                    pin.placement_status = "FIXED"
                else:
                    pin.placement_status = "COVER"
                self._consume()
                pos = self._parse_point()
                pin.position = pos
                if self._check(DefToken.IDENTIFIER):
                    pin.orientation = self._consume().value.upper()
            elif self._check(DefToken.PORT):
                self._consume()
            elif self._check(DefToken.IDENTIFIER):
                self._consume()
            elif self._check(DefToken.NUMBER):
                self._consume()
            elif self._check(DefToken.LPAREN):
                self._consume()
                while not self._check(DefToken.RPAREN):
                    self._consume()
                self._consume()
            else:
                self._consume()

        if self._check(DefToken.SEMICOLON):
            self._consume()
        return pin

    def _parse_pins(self) -> None:
        self._expect(DefToken.PINS)
        count = 0
        if self._check(DefToken.NUMBER):
            count = int(self._parse_number())
        self._skip_to_semicolon()

        parsed = 0
        while not (self._check(DefToken.END) and self._peek().value.upper() == "PINS"):
            if self._check(DefToken.SEMICOLON):
                self._consume()
            elif self._check(DefToken.END):
                break
            elif self._check(DefToken.EOF):
                break
            elif self._check(DefToken.IDENTIFIER) or self._check(DefToken.STRING):
                pin = self._parse_pin()
                self._def.pins.append(pin)
                parsed += 1
                if parsed % 10000 == 0 and parsed > 0:
                    print(f"[DEF Parser] Parsed {parsed}/{count} pins...", file=sys.stderr)
            else:
                self._consume()

        if self._check(DefToken.END):
            self._consume()
            if self._check_value("PINS"):
                self._consume()
            if self._check(DefToken.SEMICOLON):
                self._consume()

    def _parse_via(self) -> Via:
        name = self._parse_identifier()
        via = Via(name=name)

        while not self._check(DefToken.SEMICOLON):
            if self._check(DefToken.PLUS):
                self._consume()
            if self._check(DefToken.LAYER):
                self._consume()
                layer_name = self._parse_identifier()
                via.layers.append(layer_name)
                if layer_name not in via.shapes:
                    via.shapes[layer_name] = []
                while self._check(DefToken.LPAREN):
                    p = self._parse_point()
                    if self._check(DefToken.LPAREN):
                        p2 = self._parse_point()
                        rect = Rect(
                            llx=min(p[0], p2[0]),
                            lly=min(p[1], p2[1]),
                            urx=max(p[0], p2[0]),
                            ury=max(p[1], p2[1]),
                        )
                        via.shapes[layer_name].append(rect)
                    elif self._check(DefToken.NUMBER):
                        w = self._parse_number()
                        h = self._parse_number()
                        rect = Rect(
                            llx=p[0] - w / 2,
                            lly=p[1] - h / 2,
                            urx=p[0] + w / 2,
                            ury=p[1] + h / 2,
                        )
                        via.shapes[layer_name].append(rect)
            elif self._check(DefToken.IDENTIFIER):
                self._consume()
            elif self._check(DefToken.NUMBER):
                self._consume()
            else:
                self._consume()

        if self._check(DefToken.SEMICOLON):
            self._consume()
        return via

    def _parse_vias(self) -> None:
        self._expect(DefToken.VIAS)
        count = 0
        if self._check(DefToken.NUMBER):
            count = int(self._parse_number())
        self._skip_to_semicolon()

        parsed = 0
        while not (self._check(DefToken.END) and self._peek().value.upper() == "VIAS"):
            if self._check(DefToken.SEMICOLON):
                self._consume()
            elif self._check(DefToken.END):
                break
            elif self._check(DefToken.EOF):
                break
            elif self._check(DefToken.IDENTIFIER) or self._check(DefToken.STRING):
                via = self._parse_via()
                self._def.vias[via.name] = via
                parsed += 1
                if parsed % 1000 == 0 and parsed > 0:
                    print(f"[DEF Parser] Parsed {parsed}/{count} vias...", file=sys.stderr)
            else:
                self._consume()

        if self._check(DefToken.END):
            self._consume()
            if self._check_value("VIAS"):
                self._consume()
            if self._check(DefToken.SEMICOLON):
                self._consume()

    def _parse_route_segment(self, net_route: NetRoute | SpecialNetRoute, via_map: Dict[str, Via] | None = None, expect_layer_keyword: bool = True) -> None:
        if expect_layer_keyword and self._check(DefToken.LAYER):
            self._consume()
            layer_name = self._parse_identifier()
        elif not expect_layer_keyword:
            layer_name = self._parse_identifier()
        else:
            layer_name = ""
        seg = RouteSegment(layer_name=layer_name)
        if self._check(DefToken.NUMBER):
            seg.width = self._parse_number()

        points: List[Tuple[float, float]] = []
        while self._check(DefToken.LPAREN) or self._check(DefToken.NEW) or self._check(DefToken.VIA):
            if self._check(DefToken.LPAREN):
                pt = self._parse_point()
                points.append(pt)
            elif self._check(DefToken.VIA):
                self._consume()
                if not points:
                    points.append((0, 0))
                seg.points = list(points)
                net_route.segments.append(seg)
                via_name = self._parse_identifier() if not self._check(DefToken.LPAREN) else ""
                if via_name:
                    via_seg = RouteSegment(layer_name=layer_name, via_name=via_name)
                    via_seg.points = [points[-1] if points else (0, 0)]
                    if via_map and via_name in via_map:
                        via = via_map[via_name]
                        for vl in via.layers:
                            continue
                    net_route.segments.append(via_seg)
                new_seg = RouteSegment(layer_name=layer_name, width=seg.width)
                if points:
                    new_seg.points = [points[-1]]
                seg = new_seg
                points = seg.points
            elif self._check(DefToken.NEW):
                self._consume()
                if not points:
                    points.append((0, 0))
                seg.points = list(points)
                net_route.segments.append(seg)
                if self._check(DefToken.LAYER):
                    self._consume()
                    layer_name = self._parse_identifier()
                seg = RouteSegment(layer_name=layer_name)
                if self._check(DefToken.NUMBER):
                    seg.width = self._parse_number()
                points = []
            elif self._check(DefToken.MASK):
                self._consume()
                if self._check(DefToken.NUMBER):
                    seg.mask_color = int(self._parse_number())
            elif self._check(DefToken.TAPER):
                self._consume()
            elif self._check(DefToken.SHIELD):
                self._consume()
            elif self._check(DefToken.NOSHIELD):
                self._consume()
            else:
                break

        if points:
            seg.points = points
        if seg.points or seg.via_name:
            net_route.segments.append(seg)

    def _parse_net_connections(self) -> List[Tuple[str, str]]:
        connections: List[Tuple[str, str]] = []
        while self._check(DefToken.LPAREN):
            self._consume()
            inst_name = ""
            if self._check(DefToken.IDENTIFIER) or self._check(DefToken.STRING) or self._check(DefToken.ASTERISK):
                inst_name = self._consume().value
            pin_name = ""
            if self._check(DefToken.IDENTIFIER) or self._check(DefToken.STRING):
                pin_name = self._consume().value
            connections.append((inst_name, pin_name))
            self._expect(DefToken.RPAREN)
        return connections

    def _parse_net(self, via_map: Dict[str, Via] | None = None) -> NetRoute:
        net_name = self._parse_identifier()
        net_route = NetRoute(net_name=net_name)
        self._parse_net_connections()

        while not self._check(DefToken.SEMICOLON):
            if self._check(DefToken.PLUS):
                self._consume()
            if self._check(DefToken.ROUTED) or self._check(DefToken.ROUTE):
                self._consume()
                self._parse_route_segment(net_route, via_map, expect_layer_keyword=False)
            elif self._check(DefToken.LAYER):
                self._parse_route_segment(net_route, via_map)
            elif self._check(DefToken.VIA):
                self._parse_route_segment(net_route, via_map)
            elif self._check(DefToken.IDENTIFIER):
                self._consume()
            elif self._check(DefToken.NUMBER):
                self._consume()
            elif self._check(DefToken.LPAREN):
                self._consume()
                while not self._check(DefToken.RPAREN):
                    self._consume()
                self._consume()
            elif self._check(DefToken.EOF):
                break
            else:
                self._consume()

        if self._check(DefToken.SEMICOLON):
            self._consume()
        return net_route

    def _parse_nets(self) -> None:
        self._expect(DefToken.NETS)
        count = 0
        if self._check(DefToken.NUMBER):
            count = int(self._parse_number())
        self._skip_to_semicolon()

        via_map = self._def.vias
        parsed = 0
        while not (self._check(DefToken.END) and self._peek().value.upper() == "NETS"):
            if self._check(DefToken.SEMICOLON):
                self._consume()
            elif self._check(DefToken.END):
                break
            elif self._check(DefToken.EOF):
                break
            elif self._check(DefToken.IDENTIFIER) or self._check(DefToken.STRING):
                net = self._parse_net(via_map)
                self._def.nets.append(net)
                parsed += 1
                if parsed % 10000 == 0 and parsed > 0:
                    total_segs = sum(len(n.segments) for n in self._def.nets)
                    print(
                        f"[DEF Parser] Parsed {parsed}/{count} nets ({total_segs} segments)...",
                        file=sys.stderr,
                    )
            else:
                self._consume()

        if self._check(DefToken.END):
            self._consume()
            if self._check_value("NETS"):
                self._consume()
            if self._check(DefToken.SEMICOLON):
                self._consume()

    def _parse_specialnet(self, via_map: Dict[str, Via] | None = None) -> SpecialNetRoute:
        net_name = self._parse_identifier()
        net_route = SpecialNetRoute(net_name=net_name)
        self._parse_net_connections()

        while not self._check(DefToken.SEMICOLON):
            if self._check(DefToken.PLUS):
                self._consume()
            if self._check(DefToken.ROUTED) or self._check(DefToken.ROUTE):
                self._consume()
                self._parse_route_segment(net_route, via_map, expect_layer_keyword=False)
            elif self._check(DefToken.LAYER):
                self._parse_route_segment(net_route, via_map)
            elif self._check(DefToken.VIA):
                self._parse_route_segment(net_route, via_map)
            elif self._check(DefToken.IDENTIFIER):
                self._consume()
            elif self._check(DefToken.NUMBER):
                self._consume()
            elif self._check(DefToken.LPAREN):
                self._consume()
                while not self._check(DefToken.RPAREN):
                    self._consume()
                self._consume()
            elif self._check(DefToken.EOF):
                break
            else:
                self._consume()

        if self._check(DefToken.SEMICOLON):
            self._consume()
        return net_route

    def _parse_specialnets(self) -> None:
        self._expect(DefToken.SPECIALNETS)
        count = 0
        if self._check(DefToken.NUMBER):
            count = int(self._parse_number())
        self._skip_to_semicolon()

        via_map = self._def.vias
        parsed = 0
        while not (self._check(DefToken.END) and self._peek().value.upper() == "SPECIALNETS"):
            if self._check(DefToken.SEMICOLON):
                self._consume()
            elif self._check(DefToken.END):
                break
            elif self._check(DefToken.EOF):
                break
            elif self._check(DefToken.IDENTIFIER) or self._check(DefToken.STRING):
                net = self._parse_specialnet(via_map)
                self._def.specialnets.append(net)
                parsed += 1
                if parsed % 1000 == 0 and parsed > 0:
                    print(f"[DEF Parser] Parsed {parsed}/{count} specialnets...", file=sys.stderr)
            else:
                self._consume()

        if self._check(DefToken.END):
            self._consume()
            if self._check_value("SPECIALNETS"):
                self._consume()
            if self._check(DefToken.SEMICOLON):
                self._consume()

    @classmethod
    def parse_file(cls, filepath: str) -> DefData:
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"DEF file not found: {filepath}")
        print(f"[DEF Parser] Loading DEF file: {filepath}", file=sys.stderr)
        file_size = os.path.getsize(filepath)
        print(f"[DEF Parser] File size: {file_size / (1024*1024):.1f} MB", file=sys.stderr)

        lexer = DefLexer.from_file(filepath)
        print("[DEF Parser] Tokenizing...", file=sys.stderr)
        parser = cls()
        parser._tokens = lexer.tokenize()
        parser._pos = 0
        print(f"[DEF Parser] Tokenized {len(parser._tokens)} tokens", file=sys.stderr)
        print("[DEF Parser] Parsing...", file=sys.stderr)
        parser._parse_header()
        print(
            f"[DEF Parser] Done: {len(parser._def.components)} components, "
            f"{len(parser._def.pins)} pins, {len(parser._def.nets)} nets",
            file=sys.stderr,
        )
        return parser._def

    @classmethod
    def parse_string(cls, text: str) -> DefData:
        lexer = DefLexer(text)
        parser = cls()
        parser._tokens = lexer.tokenize()
        parser._pos = 0
        parser._parse_header()
        return parser._def
