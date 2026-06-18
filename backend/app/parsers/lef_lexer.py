from __future__ import annotations
import re
from typing import List, Tuple, Optional, Iterator


class LefToken:
    VERSION = "VERSION"
    DIVIDERCHAR = "DIVIDERCHAR"
    BITRATCHARS = "BITRATCHARS"
    BUSBITCHARS = "BUSBITCHARS"
    MANUFACTURINGGRID = "MANUFACTURINGGRID"
    UNITS = "UNITS"
    DATABASE = "DATABASE"
    MICRONS = "MICRONS"
    END_UNITS = "END_UNITS"
    LAYER = "LAYER"
    END_LAYER = "END_LAYER"
    TYPE = "TYPE"
    ROUTING = "ROUTING"
    CUT = "CUT"
    MASTERSLICE = "MASTERSLICE"
    OVERLAP = "OVERLAP"
    IMPLANT = "IMPLANT"
    DIRECTION = "DIRECTION"
    HORIZONTAL = "HORIZONTAL"
    VERTICAL = "VERTICAL"
    PITCH = "PITCH"
    OFFSET = "OFFSET"
    WIDTH = "WIDTH"
    SITE = "SITE"
    END_SITE = "END_SITE"
    CLASS = "CLASS"
    CORE = "CORE"
    PAD = "PAD"
    ENDCAP = "ENDCAP"
    SIZE = "SIZE"
    MACRO = "MACRO"
    END_MACRO = "END_MACRO"
    FOREIGN = "FOREIGN"
    ORIGIN = "ORIGIN"
    PIN = "PIN"
    END_PIN = "END_PIN"
    DIRECTION_PIN = "DIRECTION_PIN"
    INPUT = "INPUT"
    OUTPUT = "OUTPUT"
    INOUT = "INOUT"
    FEEDTHRU = "FEEDTHRU"
    USE = "USE"
    SIGNAL = "SIGNAL"
    POWER = "POWER"
    GROUND = "GROUND"
    CLOCK = "CLOCK"
    TIEOFF = "TIEOFF"
    ANALOG = "ANALOG"
    SCAN = "SCAN"
    RESET = "RESET"
    PORT = "PORT"
    END_PORT = "END_PORT"
    LAYER_REF = "LAYER_REF"
    RECT = "RECT"
    POLYGON = "POLYGON"
    PATH = "PATH"
    OBS = "OBS"
    END_OBS = "END_OBS"
    PROPERTY = "PROPERTY"
    PROPERTIES = "PROPERTIES"
    END_PROPERTIES = "END_PROPERTIES"
    VIA = "VIA"
    VIARULE = "VIARULE"
    SYMMETRY = "SYMMETRY"
    ROW = "ROW"
    AREA = "AREA"
    STRING = "STRING"
    NUMBER = "NUMBER"
    IDENTIFIER = "IDENTIFIER"
    END = "END"
    SEMICOLON = "SEMICOLON"
    LBRACKET = "LBRACKET"
    RBRACKET = "RBRACKET"
    LPAREN = "LPAREN"
    RPAREN = "RPAREN"
    EOF = "EOF"
    UNKNOWN = "UNKNOWN"


KEYWORD_MAP = {
    "VERSION": LefToken.VERSION,
    "DIVIDERCHAR": LefToken.DIVIDERCHAR,
    "BITRATCHARS": LefToken.BITRATCHARS,
    "BUSBITCHARS": LefToken.BUSBITCHARS,
    "MANUFACTURINGGRID": LefToken.MANUFACTURINGGRID,
    "UNITS": LefToken.UNITS,
    "DATABASE": LefToken.DATABASE,
    "MICRONS": LefToken.MICRONS,
    "END": LefToken.END,
    "LAYER": LefToken.LAYER,
    "TYPE": LefToken.TYPE,
    "ROUTING": LefToken.ROUTING,
    "CUT": LefToken.CUT,
    "MASTERSLICE": LefToken.MASTERSLICE,
    "OVERLAP": LefToken.OVERLAP,
    "IMPLANT": LefToken.IMPLANT,
    "DIRECTION": LefToken.DIRECTION,
    "HORIZONTAL": LefToken.HORIZONTAL,
    "VERTICAL": LefToken.VERTICAL,
    "PITCH": LefToken.PITCH,
    "OFFSET": LefToken.OFFSET,
    "WIDTH": LefToken.WIDTH,
    "SITE": LefToken.SITE,
    "CLASS": LefToken.CLASS,
    "CORE": LefToken.CORE,
    "PAD": LefToken.PAD,
    "ENDCAP": LefToken.ENDCAP,
    "SIZE": LefToken.SIZE,
    "MACRO": LefToken.MACRO,
    "FOREIGN": LefToken.FOREIGN,
    "ORIGIN": LefToken.ORIGIN,
    "PIN": LefToken.PIN,
    "INPUT": LefToken.INPUT,
    "OUTPUT": LefToken.OUTPUT,
    "INOUT": LefToken.INOUT,
    "FEEDTHRU": LefToken.FEEDTHRU,
    "USE": LefToken.USE,
    "SIGNAL": LefToken.SIGNAL,
    "POWER": LefToken.POWER,
    "GROUND": LefToken.GROUND,
    "CLOCK": LefToken.CLOCK,
    "TIEOFF": LefToken.TIEOFF,
    "ANALOG": LefToken.ANALOG,
    "SCAN": LefToken.SCAN,
    "RESET": LefToken.RESET,
    "PORT": LefToken.PORT,
    "RECT": LefToken.RECT,
    "POLYGON": LefToken.POLYGON,
    "PATH": LefToken.PATH,
    "OBS": LefToken.OBS,
    "PROPERTY": LefToken.PROPERTY,
    "PROPERTIES": LefToken.PROPERTIES,
    "BY": "BY",
    "DO": "DO",
    "DESIGN": "DESIGN",
    "TECHNOLOGY": "TECHNOLOGY",
    "NODES": "NODES",
    "SYMMETRY": "SYMMETRY",
    "ROW": "ROW",
    "X": "X",
    "Y": "Y",
    "R90": "R90",
    "ANTENNAMODEL": "ANTENNAMODEL",
    "AREA": "AREA",
    "RESISTANCE": "RESISTANCE",
    "CAPACITANCE": "CAPACITANCE",
    "EDGECAPACITANCE": "EDGECAPACITANCE",
    "CURRENTDENSITY": "CURRENTDENSITY",
    "SPACING": "SPACING",
    "MINIMUMCUT": "MINIMUMCUT",
    "VIA": "VIA",
    "VIARULE": "VIARULE",
    "GENERATE": "GENERATE",
    "SHAPE": "SHAPE",
    "RING": "RING",
    "PADSTACK": "PADSTACK",
    "COVER": "COVER",
    "ABUTMENT": "ABUTMENT",
    "ARRAY": "ARRAY",
    "N": "N",
    "S": "S",
    "E": "E",
    "W": "W",
    "FN": "FN",
    "FS": "FS",
    "FE": "FE",
    "FW": "FW",
}


class Token:
    __slots__ = ("type", "value", "line", "col")

    def __init__(self, type: str, value: str = "", line: int = 0, col: int = 0):
        self.type = type
        self.value = value
        self.line = line
        self.col = col

    def __repr__(self) -> str:
        return f"Token({self.type}, '{self.value}', line={self.line}, col={self.col})"


IDENT_RE = re.compile(r"[a-zA-Z_][a-zA-Z0-9_\[\]\\/.]*")
QUOTED_RE = re.compile(r'"([^"\\]*(\\.[^"\\]*)*)"')
NUMBER_RE = re.compile(r"-?\d+\.?\d*([eE][+-]?\d+)?")


class LefLexer:
    def __init__(self, text: str):
        self._text = text
        self._pos = 0
        self._line = 1
        self._col = 1
        self._len = len(text)

    @classmethod
    def from_file(cls, filepath: str) -> "LefLexer":
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            return cls(f.read())

    def _skip_whitespace_and_comments(self) -> None:
        while self._pos < self._len:
            c = self._text[self._pos]
            if c in " \t\r":
                self._pos += 1
                self._col += 1
            elif c == "\n":
                self._pos += 1
                self._line += 1
                self._col = 1
            elif c == "#":
                while self._pos < self._len and self._text[self._pos] != "\n":
                    self._pos += 1
            elif c == "/" and self._pos + 1 < self._len and self._text[self._pos + 1] == "/":
                while self._pos < self._len and self._text[self._pos] != "\n":
                    self._pos += 1
            else:
                break

    def _advance(self, count: int = 1) -> None:
        for _ in range(count):
            if self._pos < self._len:
                if self._text[self._pos] == "\n":
                    self._line += 1
                    self._col = 1
                else:
                    self._col += 1
                self._pos += 1

    def next_token(self) -> Token:
        self._skip_whitespace_and_comments()

        if self._pos >= self._len:
            return Token(LefToken.EOF, "", self._line, self._col)

        start_line = self._line
        start_col = self._col
        c = self._text[self._pos]

        if c == ";":
            self._advance()
            return Token(LefToken.SEMICOLON, ";", start_line, start_col)

        if c == "[":
            self._advance()
            return Token(LefToken.LBRACKET, "[", start_line, start_col)

        if c == "]":
            self._advance()
            return Token(LefToken.RBRACKET, "]", start_line, start_col)

        if c == "(":
            self._advance()
            return Token(LefToken.LPAREN, "(", start_line, start_col)

        if c == ")":
            self._advance()
            return Token(LefToken.RPAREN, ")", start_line, start_col)

        if c == '"':
            m = QUOTED_RE.match(self._text, self._pos)
            if m:
                val = m.group(1)
                self._advance(m.end() - self._pos)
                return Token(LefToken.STRING, val, start_line, start_col)

        m = NUMBER_RE.match(self._text, self._pos)
        if m:
            num_str = m.group(0)
            self._advance(len(num_str))
            return Token(LefToken.NUMBER, num_str, start_line, start_col)

        m = IDENT_RE.match(self._text, self._pos)
        if m:
            ident = m.group(0)
            self._advance(len(ident))
            upper_ident = ident.upper()
            if upper_ident in KEYWORD_MAP:
                return Token(KEYWORD_MAP[upper_ident], ident, start_line, start_col)
            if upper_ident == "UNITS":
                return Token(LefToken.UNITS, ident, start_line, start_col)
            return Token(LefToken.IDENTIFIER, ident, start_line, start_col)

        self._advance()
        return Token(LefToken.UNKNOWN, c, start_line, start_col)

    def tokenize(self) -> List[Token]:
        tokens: List[Token] = []
        while True:
            t = self.next_token()
            tokens.append(t)
            if t.type == LefToken.EOF:
                break
        return tokens

    def __iter__(self) -> Iterator[Token]:
        while True:
            t = self.next_token()
            yield t
            if t.type == LefToken.EOF:
                break
