from __future__ import annotations
import re
from typing import List, Iterator


class DefToken:
    VERSION = "VERSION"
    DIVIDERCHAR = "DIVIDERCHAR"
    BUSBITCHARS = "BUSBITCHARS"
    DESIGN = "DESIGN"
    UNITS = "UNITS"
    DISTANCE = "DISTANCE"
    MICRONS = "MICRONS"
    DIEAREA = "DIEAREA"
    COMPONENTS = "COMPONENTS"
    COMPONENT = "COMPONENT"
    PINS = "PINS"
    NETS = "NETS"
    SPECIALNETS = "SPECIALNETS"
    VIAS = "VIAS"
    ROWS = "ROWS"
    ROW = "ROW"
    TRACKS = "TRACKS"
    GCELLGRID = "GCELLGRID"
    END = "END"
    IDENTIFIER = "IDENTIFIER"
    NUMBER = "NUMBER"
    STRING = "STRING"
    PLUS = "PLUS"
    MINUS = "MINUS"
    LPAREN = "LPAREN"
    RPAREN = "RPAREN"
    LBRACKET = "LBRACKET"
    RBRACKET = "RBRACKET"
    LBRACE = "LBRACE"
    RBRACE = "RBRACE"
    SEMICOLON = "SEMICOLON"
    COLON = "COLON"
    COMMA = "COMMA"
    ASTERISK = "ASTERISK"
    TILDE = "TILDE"
    NEWLINE = "NEWLINE"
    EOF = "EOF"
    UNKNOWN = "UNKNOWN"

    FIXED = "FIXED"
    COVER = "COVER"
    PLACED = "PLACED"
    UNPLACED = "UNPLACED"
    FIRM = "FIRM"

    SOURCE = "SOURCE"
    NETLIST = "NETLIST"
    DIST = "DIST"
    USER = "USER"
    BLOCKAGE = "BLOCKAGE"
    CLOCK = "CLOCK"
    PIN = "PIN"
    VDD = "VDD"
    VSS = "VSS"

    INPUT = "INPUT"
    OUTPUT = "OUTPUT"
    INOUT = "INOUT"
    FEEDTHRU = "FEEDTHRU"
    SIGNAL = "SIGNAL"
    POWER = "POWER"
    GROUND = "GROUND"
    ANALOG = "ANALOG"
    SCAN = "SCAN"
    RESET = "RESET"
    TIEOFF = "TIEOFF"

    N = "N"
    S = "S"
    E = "E"
    W = "W"
    FN = "FN"
    FS = "FS"
    FE = "FE"
    FW = "FW"

    USE = "USE"
    DIRECTION = "DIRECTION"
    LAYER = "LAYER"
    VIA = "VIA"
    ROUTE = "ROUTE"
    ROUTED = "ROUTED"
    SHAPE = "SHAPE"
    RECT = "RECT"
    POLYGON = "POLYGON"
    PORT = "PORT"

    NEW = "NEW"
    MASK = "MASK"
    TAPER = "TAPER"
    TAPERRULE = "TAPERRULE"
    NOSHIELD = "NOSHIELD"
    SHIELD = "SHIELD"
    OFFSET = "OFFSET"
    PATTERN = "PATTERN"
    STRIPE = "STRIPE"
    FOLLOWPIN = "FOLLOWPIN"
    DO = "DO"
    STEP = "STEP"


DEF_KEYWORDS = {
    "VERSION": DefToken.VERSION,
    "DIVIDERCHAR": DefToken.DIVIDERCHAR,
    "BUSBITCHARS": DefToken.BUSBITCHARS,
    "DESIGN": DefToken.DESIGN,
    "UNITS": DefToken.UNITS,
    "DISTANCE": DefToken.DISTANCE,
    "MICRONS": DefToken.MICRONS,
    "DIEAREA": DefToken.DIEAREA,
    "COMPONENTS": DefToken.COMPONENTS,
    "COMPONENT": DefToken.COMPONENT,
    "PINS": DefToken.PINS,
    "NETS": DefToken.NETS,
    "SPECIALNETS": DefToken.SPECIALNETS,
    "VIAS": DefToken.VIAS,
    "ROWS": DefToken.ROWS,
    "ROW": DefToken.ROW,
    "TRACKS": DefToken.TRACKS,
    "GCELLGRID": DefToken.GCELLGRID,
    "END": DefToken.END,

    "FIXED": DefToken.FIXED,
    "COVER": DefToken.COVER,
    "PLACED": DefToken.PLACED,
    "UNPLACED": DefToken.UNPLACED,
    "FIRM": DefToken.FIRM,

    "SOURCE": DefToken.SOURCE,
    "NETLIST": DefToken.NETLIST,
    "DIST": DefToken.DIST,
    "USER": DefToken.USER,
    "BLOCKAGE": DefToken.BLOCKAGE,
    "CLOCK": DefToken.CLOCK,
    "PIN": DefToken.PIN,
    "VDD": DefToken.VDD,
    "VSS": DefToken.VSS,

    "INPUT": DefToken.INPUT,
    "OUTPUT": DefToken.OUTPUT,
    "INOUT": DefToken.INOUT,
    "FEEDTHRU": DefToken.FEEDTHRU,
    "SIGNAL": DefToken.SIGNAL,
    "POWER": DefToken.POWER,
    "GROUND": DefToken.GROUND,
    "ANALOG": DefToken.ANALOG,
    "SCAN": DefToken.SCAN,
    "RESET": DefToken.RESET,
    "TIEOFF": DefToken.TIEOFF,

    "USE": DefToken.USE,
    "DIRECTION": DefToken.DIRECTION,
    "LAYER": DefToken.LAYER,
    "VIA": DefToken.VIA,
    "ROUTE": DefToken.ROUTE,
    "ROUTED": DefToken.ROUTED,
    "SHAPE": DefToken.SHAPE,
    "RECT": DefToken.RECT,
    "POLYGON": DefToken.POLYGON,
    "PORT": DefToken.PORT,

    "N": DefToken.N,
    "S": DefToken.S,
    "E": DefToken.E,
    "W": DefToken.W,
    "FN": DefToken.FN,
    "FS": DefToken.FS,
    "FE": DefToken.FE,
    "FW": DefToken.FW,

    "NEW": DefToken.NEW,
    "MASK": DefToken.MASK,
    "TAPER": DefToken.TAPER,
    "TAPERRULE": DefToken.TAPERRULE,
    "NOSHIELD": DefToken.NOSHIELD,
    "SHIELD": DefToken.SHIELD,
    "OFFSET": DefToken.OFFSET,
    "PATTERN": DefToken.PATTERN,
    "STRIPE": DefToken.STRIPE,
    "FOLLOWPIN": DefToken.FOLLOWPIN,
    "DO": DefToken.DO,
    "STEP": DefToken.STEP,

    "BY": "BY",
    "FROM": "FROM",
    "TO": "TO",
    "ON": "ON",
    "IN": "IN",
    "AND": "AND",
    "OR": "OR",
    "NOT": "NOT",
    "XOR": "XOR",
    "NONDEFAULTRULE": "NONDEFAULTRULE",
    "PROPERTY": "PROPERTY",
    "PROPERTIES": "PROPERTIES",
    "WEIGHT": "WEIGHT",
    "PATTERNCHECK": "PATTERNCHECK",
    "ESTCAP": "ESTCAP",
    "DONOTTOUCH": "DONOTTOUCH",
    "DONOTUSE": "DONOTUSE",
    "FLAT": "FLAT",
    "GROUP": "GROUP",
    "REGION": DefToken.REGION if hasattr(DefToken, "REGION") else "REGION",
    "SUPPLY": "SUPPLY",
    "GROUND": DefToken.GROUND,
    "ANTENNA": "ANTENNA",
    "AREA": "AREA",
}


class DefTokenObj:
    __slots__ = ("type", "value", "line", "col")

    def __init__(self, type: str, value: str = "", line: int = 0, col: int = 0):
        self.type = type
        self.value = value
        self.line = line
        self.col = col

    def __repr__(self) -> str:
        return f"DefToken({self.type}, '{self.value}', line={self.line}, col={self.col})"


DEF_IDENT_RE = re.compile(r"[a-zA-Z_\\][a-zA-Z0-9_\[\]\\/.:<>\-]*")
DEF_QUOTED_RE = re.compile(r'"([^"\\]*(\\.[^"\\]*)*)"')
DEF_NUMBER_RE = re.compile(r"-?\d+\.?\d*([eE][+-]?\d+)?")


class DefLexer:
    def __init__(self, text: str):
        self._text = text
        self._pos = 0
        self._line = 1
        self._col = 1
        self._len = len(text)

    @classmethod
    def from_file(cls, filepath: str) -> "DefLexer":
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            return cls(f.read())

    def _skip_ws_comments(self) -> None:
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
            elif c == "\\" and self._pos + 1 < self._len and self._text[self._pos + 1] == "\n":
                self._pos += 2
                self._line += 1
                self._col = 1
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

    def next_token(self) -> DefTokenObj:
        self._skip_ws_comments()

        if self._pos >= self._len:
            return DefTokenObj(DefToken.EOF, "", self._line, self._col)

        start_line = self._line
        start_col = self._col
        c = self._text[self._pos]

        if c == ";":
            self._advance()
            return DefTokenObj(DefToken.SEMICOLON, ";", start_line, start_col)
        if c == "+":
            self._advance()
            return DefTokenObj(DefToken.PLUS, "+", start_line, start_col)
        if c == "-" and (self._pos + 1 >= self._len or not self._text[self._pos + 1].isdigit()):
            self._advance()
            return DefTokenObj(DefToken.MINUS, "-", start_line, start_col)
        if c == "(":
            self._advance()
            return DefTokenObj(DefToken.LPAREN, "(", start_line, start_col)
        if c == ")":
            self._advance()
            return DefTokenObj(DefToken.RPAREN, ")", start_line, start_col)
        if c == "[":
            self._advance()
            return DefTokenObj(DefToken.LBRACKET, "[", start_line, start_col)
        if c == "]":
            self._advance()
            return DefTokenObj(DefToken.RBRACKET, "]", start_line, start_col)
        if c == "{":
            self._advance()
            return DefTokenObj(DefToken.LBRACE, "{", start_line, start_col)
        if c == "}":
            self._advance()
            return DefTokenObj(DefToken.RBRACE, "}", start_line, start_col)
        if c == ":":
            self._advance()
            return DefTokenObj(DefToken.COLON, ":", start_line, start_col)
        if c == ",":
            self._advance()
            return DefTokenObj(DefToken.COMMA, ",", start_line, start_col)
        if c == "*":
            self._advance()
            return DefTokenObj(DefToken.ASTERISK, "*", start_line, start_col)
        if c == "~":
            self._advance()
            return DefTokenObj(DefToken.TILDE, "~", start_line, start_col)

        if c == '"':
            m = DEF_QUOTED_RE.match(self._text, self._pos)
            if m:
                val = m.group(1)
                self._advance(m.end() - self._pos)
                return DefTokenObj(DefToken.STRING, val, start_line, start_col)

        m = DEF_NUMBER_RE.match(self._text, self._pos)
        if m:
            num_str = m.group(0)
            self._advance(len(num_str))
            return DefTokenObj(DefToken.NUMBER, num_str, start_line, start_col)

        m = DEF_IDENT_RE.match(self._text, self._pos)
        if m:
            ident = m.group(0)
            self._advance(len(ident))
            upper_ident = ident.upper()
            if upper_ident in DEF_KEYWORDS:
                return DefTokenObj(DEF_KEYWORDS[upper_ident], ident, start_line, start_col)
            return DefTokenObj(DefToken.IDENTIFIER, ident, start_line, start_col)

        self._advance()
        return DefTokenObj(DefToken.UNKNOWN, c, start_line, start_col)

    def tokenize(self) -> List[DefTokenObj]:
        tokens: List[DefTokenObj] = []
        while True:
            t = self.next_token()
            tokens.append(t)
            if t.type == DefToken.EOF:
                break
        return tokens

    def __iter__(self) -> Iterator[DefTokenObj]:
        while True:
            t = self.next_token()
            yield t
            if t.type == DefToken.EOF:
                break
