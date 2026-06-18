from __future__ import annotations
from typing import List, Optional, Tuple, Dict
import sys
import os

from .lef_lexer import LefLexer, Token, LefToken
from ..core.models import (
    LefData,
    Layer,
    Site,
    Macro,
    Pin,
    PortGeometry,
    Obstacle,
    Rect,
)


class LefParser:
    def __init__(self):
        self._tokens: List[Token] = []
        self._pos: int = 0
        self._lef = LefData()

    def _current(self) -> Token:
        return self._tokens[self._pos]

    def _peek(self, offset: int = 1) -> Token:
        idx = self._pos + offset
        if idx < len(self._tokens):
            return self._tokens[idx]
        return self._tokens[-1]

    def _consume(self) -> Token:
        tok = self._tokens[self._pos]
        self._pos += 1
        return tok

    def _expect(self, token_type: str) -> Token:
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
        while self._pos < len(self._tokens) and not self._check(LefToken.SEMICOLON):
            self._consume()
        if self._pos < len(self._tokens):
            self._consume()

    def _parse_number(self) -> float:
        tok = self._expect(LefToken.NUMBER)
        try:
            return float(tok.value)
        except ValueError:
            return 0.0

    def _parse_identifier(self) -> str:
        tok = self._consume()
        if tok.type == LefToken.IDENTIFIER or tok.type == LefToken.STRING:
            return tok.value
        if tok.value and len(tok.value) > 0:
            return tok.value
        raise SyntaxError(
            f"Expected IDENTIFIER, got {tok.type} ('{tok.value}') "
            f"at line {tok.line}, col {tok.col}"
        )

    def _parse_layer_properties(self, layer: Layer) -> None:
        while not self._check(LefToken.END):
            if self._check(LefToken.TYPE):
                self._consume()
                if self._check(LefToken.ROUTING):
                    layer.layer_type = "ROUTING"
                elif self._check(LefToken.CUT):
                    layer.layer_type = "CUT"
                elif self._check(LefToken.MASTERSLICE):
                    layer.layer_type = "MASTERSLICE"
                elif self._check(LefToken.OVERLAP):
                    layer.layer_type = "OVERLAP"
                elif self._check(LefToken.IMPLANT):
                    layer.layer_type = "IMPLANT"
                else:
                    layer.layer_type = self._consume().value
                self._skip_to_semicolon()
            elif self._check(LefToken.DIRECTION):
                self._consume()
                if self._check(LefToken.HORIZONTAL):
                    layer.routing_direction = "HORIZONTAL"
                elif self._check(LefToken.VERTICAL):
                    layer.routing_direction = "VERTICAL"
                else:
                    layer.routing_direction = self._consume().value.upper()
                self._skip_to_semicolon()
            elif self._check(LefToken.PITCH):
                self._consume()
                if self._check_value("X") or self._check_value("Y"):
                    self._consume()
                layer.pitch = self._parse_number()
                self._skip_to_semicolon()
            elif self._check(LefToken.WIDTH):
                self._consume()
                layer.width = self._parse_number()
                self._skip_to_semicolon()
            elif self._check(LefToken.OFFSET):
                self._consume()
                if self._check_value("X") or self._check_value("Y"):
                    self._consume()
                layer.offset = self._parse_number()
                self._skip_to_semicolon()
            elif self._check(LefToken.SEMICOLON):
                self._consume()
            else:
                self._skip_to_semicolon()

    def _parse_layer(self) -> Layer:
        self._expect(LefToken.LAYER)
        name = self._parse_identifier()
        layer = Layer(name=name)
        if self._check(LefToken.SEMICOLON):
            self._consume()
        while not self._check(LefToken.END):
            self._parse_layer_properties(layer)
        if self._check(LefToken.END):
            self._consume()
            if not self._check(LefToken.SEMICOLON):
                self._consume()
            if self._check(LefToken.SEMICOLON):
                self._consume()
        self._lef.layer_order.append(name)
        return layer

    def _parse_site(self) -> Site:
        self._expect(LefToken.SITE)
        name = self._parse_identifier()
        site = Site(name=name)
        self._skip_to_semicolon()
        while not self._check(LefToken.END):
            if self._check(LefToken.CLASS):
                self._consume()
                if self._check(LefToken.CORE):
                    site.class_name = "CORE"
                elif self._check(LefToken.PAD):
                    site.class_name = "PAD"
                elif self._check(LefToken.ENDCAP):
                    site.class_name = "ENDCAP"
                else:
                    site.class_name = self._consume().value
                self._skip_to_semicolon()
            elif self._check(LefToken.SIZE):
                self._consume()
                w = self._parse_number()
                while not self._check(LefToken.SEMICOLON) and not self._check(LefToken.NUMBER):
                    self._consume()
                if self._check(LefToken.NUMBER):
                    h = self._parse_number()
                    site.size = (w, h)
                self._skip_to_semicolon()
            elif self._check(LefToken.SYMMETRY):
                self._consume()
                self._skip_to_semicolon()
            elif self._check(LefToken.ROW):
                self._consume()
                self._skip_to_semicolon()
            elif self._check(LefToken.SEMICOLON):
                self._consume()
            else:
                self._skip_to_semicolon()
        if self._check(LefToken.END):
            self._consume()
            if not self._check(LefToken.SEMICOLON):
                self._consume()
            if self._check(LefToken.SEMICOLON):
                self._consume()
        return site

    def _parse_rect(self) -> Rect:
        self._expect(LefToken.RECT)
        llx = self._parse_number()
        lly = self._parse_number()
        urx = self._parse_number()
        ury = self._parse_number()
        rect = Rect(llx=llx, lly=lly, urx=urx, ury=ury)
        self._skip_to_semicolon()
        return rect

    def _parse_port(self, pin: Pin) -> None:
        self._expect(LefToken.PORT)
        self._skip_to_semicolon()
        current_layer: Optional[str] = None
        while not self._check(LefToken.END):
            if self._check(LefToken.LAYER):
                self._consume()
                current_layer = self._parse_identifier()
                port_geom = PortGeometry(layer_name=current_layer)
                pin.ports.append(port_geom)
                self._skip_to_semicolon()
            elif self._check(LefToken.RECT):
                rect = self._parse_rect()
                if pin.ports and current_layer:
                    pin.ports[-1].shapes.append(rect)
                self._update_pin_bbox(pin, rect)
            elif self._check(LefToken.POLYGON):
                self._consume()
                points: List[Tuple[float, float]] = []
                while self._check(LefToken.NUMBER):
                    x = self._parse_number()
                    y = self._parse_number()
                    points.append((x, y))
                if len(points) >= 3:
                    xs = [p[0] for p in points]
                    ys = [p[1] for p in points]
                    rect = Rect(
                        llx=min(xs),
                        lly=min(ys),
                        urx=max(xs),
                        ury=max(ys),
                    )
                    if pin.ports and current_layer:
                        pin.ports[-1].shapes.append(rect)
                    self._update_pin_bbox(pin, rect)
                self._skip_to_semicolon()
            elif self._check(LefToken.SEMICOLON):
                self._consume()
            else:
                self._skip_to_semicolon()
        if self._check(LefToken.END):
            self._consume()
            if not self._check(LefToken.SEMICOLON):
                self._consume()
            if self._check(LefToken.SEMICOLON):
                self._consume()

    def _update_pin_bbox(self, pin: Pin, rect: Rect) -> None:
        if pin.bbox.llx == 0 and pin.bbox.lly == 0 and pin.bbox.urx == 0 and pin.bbox.ury == 0:
            pin.bbox = Rect(llx=rect.llx, lly=rect.lly, urx=rect.urx, ury=rect.ury)
        else:
            pin.bbox.llx = min(pin.bbox.llx, rect.llx)
            pin.bbox.lly = min(pin.bbox.lly, rect.lly)
            pin.bbox.urx = max(pin.bbox.urx, rect.urx)
            pin.bbox.ury = max(pin.bbox.ury, rect.ury)

    def _parse_pin(self) -> Pin:
        self._expect(LefToken.PIN)
        name = self._parse_identifier()
        pin = Pin(name=name)
        self._skip_to_semicolon()
        while not self._check(LefToken.END):
            if self._check(LefToken.DIRECTION):
                self._consume()
                if self._check(LefToken.INPUT):
                    pin.direction = "INPUT"
                elif self._check(LefToken.OUTPUT):
                    pin.direction = "OUTPUT"
                elif self._check(LefToken.INOUT):
                    pin.direction = "INOUT"
                elif self._check(LefToken.FEEDTHRU):
                    pin.direction = "FEEDTHRU"
                else:
                    pin.direction = self._consume().value
                self._skip_to_semicolon()
            elif self._check(LefToken.USE):
                self._consume()
                if self._check(LefToken.SIGNAL):
                    pin.use = "SIGNAL"
                elif self._check(LefToken.POWER):
                    pin.use = "POWER"
                elif self._check(LefToken.GROUND):
                    pin.use = "GROUND"
                elif self._check(LefToken.CLOCK):
                    pin.use = "CLOCK"
                else:
                    pin.use = self._consume().value
                self._skip_to_semicolon()
            elif self._check(LefToken.PORT):
                self._parse_port(pin)
            elif self._check(LefToken.SEMICOLON):
                self._consume()
            else:
                self._skip_to_semicolon()
        if self._check(LefToken.END):
            self._consume()
            if not self._check(LefToken.SEMICOLON):
                self._consume()
            if self._check(LefToken.SEMICOLON):
                self._consume()
        return pin

    def _parse_obs(self, macro: Macro) -> None:
        self._expect(LefToken.OBS)
        self._skip_to_semicolon()
        current_layer: Optional[str] = None
        current_obs: Optional[Obstacle] = None
        while not self._check(LefToken.END):
            if self._check(LefToken.LAYER):
                self._consume()
                current_layer = self._parse_identifier()
                current_obs = Obstacle(layer_name=current_layer)
                macro.obs.append(current_obs)
                self._skip_to_semicolon()
            elif self._check(LefToken.RECT):
                rect = self._parse_rect()
                if current_obs:
                    current_obs.shapes.append(rect)
            elif self._check(LefToken.SEMICOLON):
                self._consume()
            else:
                self._skip_to_semicolon()
        if self._check(LefToken.END):
            self._consume()
            if not self._check(LefToken.SEMICOLON):
                self._consume()
            if self._check(LefToken.SEMICOLON):
                self._consume()

    def _parse_macro(self) -> Macro:
        self._expect(LefToken.MACRO)
        name = self._parse_identifier()
        macro = Macro(name=name)
        self._skip_to_semicolon()
        while not self._check(LefToken.END):
            if self._check(LefToken.CLASS):
                self._consume()
                macro.class_name = self._consume().value
                self._skip_to_semicolon()
            elif self._check(LefToken.FOREIGN):
                self._consume()
                if self._check(LefToken.IDENTIFIER) or self._check(LefToken.STRING):
                    macro.foreign_name = self._consume().value
                    if self._check(LefToken.NUMBER):
                        fx = self._parse_number()
                        fy = self._parse_number()
                        macro.foreign_origin = (fx, fy)
                    if self._check(LefToken.IDENTIFIER):
                        macro.foreign_orient = self._consume().value
                self._skip_to_semicolon()
            elif self._check(LefToken.ORIGIN):
                self._consume()
                ox = 0.0
                oy = 0.0
                if self._check(LefToken.NUMBER):
                    ox = self._parse_number()
                    oy = self._parse_number()
                macro.origin = (ox, oy)
                self._skip_to_semicolon()
            elif self._check(LefToken.SIZE):
                self._consume()
                if self._check(LefToken.NUMBER):
                    w = self._parse_number()
                    while not self._check(LefToken.SEMICOLON) and not self._check(LefToken.NUMBER):
                        self._consume()
                    if self._check(LefToken.NUMBER):
                        h = self._parse_number()
                        macro.size = (w, h)
                        macro.bbox = Rect(llx=0, lly=0, urx=w, ury=h)
                self._skip_to_semicolon()
            elif self._check(LefToken.SYMMETRY):
                self._consume()
                self._skip_to_semicolon()
            elif self._check(LefToken.SITE):
                self._consume()
                self._skip_to_semicolon()
            elif self._check(LefToken.PIN):
                pin = self._parse_pin()
                macro.pins[pin.name] = pin
            elif self._check(LefToken.OBS):
                self._parse_obs(macro)
            elif self._check(LefToken.PROPERTIES):
                self._consume()
                while not self._check(LefToken.END):
                    if self._check(LefToken.SEMICOLON):
                        self._consume()
                    else:
                        self._consume()
                if self._check(LefToken.END):
                    self._consume()
                    if not self._check(LefToken.SEMICOLON):
                        self._consume()
                    if self._check(LefToken.SEMICOLON):
                        self._consume()
            elif self._check(LefToken.SEMICOLON):
                self._consume()
            else:
                self._skip_to_semicolon()
        if self._check(LefToken.END):
            self._consume()
            if not self._check(LefToken.SEMICOLON):
                self._consume()
            if self._check(LefToken.SEMICOLON):
                self._consume()
        return macro

    def _parse_units(self) -> None:
        self._expect(LefToken.UNITS)
        self._skip_to_semicolon()
        while not self._check(LefToken.END):
            if self._check(LefToken.DATABASE):
                self._consume()
                if self._check_value("MICRONS"):
                    self._consume()
                    self._lef.units_distance_microns = int(self._parse_number())
                self._skip_to_semicolon()
            elif self._check(LefToken.MICRONS):
                self._consume()
                self._lef.units_distance_microns = int(self._parse_number())
                self._skip_to_semicolon()
            elif self._check(LefToken.SEMICOLON):
                self._consume()
            else:
                self._skip_to_semicolon()
        if self._check(LefToken.END):
            self._consume()
            if not self._check(LefToken.SEMICOLON):
                self._consume()
            if self._check(LefToken.SEMICOLON):
                self._consume()

    def _parse_header(self) -> None:
        while self._pos < len(self._tokens):
            tok = self._current()
            if tok.type == LefToken.VERSION:
                self._consume()
                if self._check(LefToken.NUMBER) or self._check(LefToken.IDENTIFIER):
                    self._lef.version = self._consume().value
                self._skip_to_semicolon()
            elif tok.type == LefToken.DIVIDERCHAR:
                self._consume()
                char_val = self._consume().value
                if len(char_val) >= 2 and char_val[0] == '"' and char_val[-1] == '"':
                    char_val = char_val[1:-1]
                if char_val:
                    self._lef.divider_char = char_val[0]
                self._skip_to_semicolon()
            elif tok.type == LefToken.BUSBITCHARS or tok.type == LefToken.BITRATCHARS:
                self._consume()
                chars_val = self._consume().value
                if len(chars_val) >= 2:
                    self._lef.busbit_chars = chars_val.strip('"')
                self._skip_to_semicolon()
            elif tok.type == LefToken.MANUFACTURINGGRID:
                self._consume()
                self._lef.manufacturing_grid = self._parse_number()
                self._skip_to_semicolon()
            elif tok.type == LefToken.UNITS:
                self._parse_units()
            elif tok.type == LefToken.LAYER:
                layer = self._parse_layer()
                self._lef.layers[layer.name] = layer
            elif tok.type == LefToken.SITE:
                site = self._parse_site()
                self._lef.sites[site.name] = site
            elif tok.type == LefToken.MACRO:
                macro = self._parse_macro()
                self._lef.macros[macro.name] = macro
            elif tok.type == LefToken.VIA:
                self._consume()
                self._skip_to_semicolon()
                while not self._check(LefToken.END):
                    if self._check(LefToken.SEMICOLON):
                        self._consume()
                    else:
                        self._consume()
                if self._check(LefToken.END):
                    self._consume()
                    self._consume()
                    self._skip_to_semicolon()
            elif tok.type == LefToken.EOF:
                break
            else:
                self._skip_to_semicolon()

    @classmethod
    def parse_file(cls, filepath: str) -> LefData:
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"LEF file not found: {filepath}")
        lexer = LefLexer.from_file(filepath)
        parser = cls()
        parser._tokens = lexer.tokenize()
        parser._pos = 0
        parser._parse_header()
        return parser._lef

    @classmethod
    def parse_string(cls, text: str) -> LefData:
        lexer = LefLexer(text)
        parser = cls()
        parser._tokens = lexer.tokenize()
        parser._pos = 0
        parser._parse_header()
        return parser._lef
