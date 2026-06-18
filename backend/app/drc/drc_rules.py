from __future__ import annotations
from typing import Dict, Optional, Tuple
from ..core.models import LefData


DEFAULT_SPACING_RULES: Dict[str, float] = {
    "M1": 0.14,
    "M2": 0.14,
    "M3": 0.14,
    "M4": 0.14,
    "M5": 0.28,
    "M6": 0.28,
    "M7": 0.28,
    "M8": 0.28,
    "M9": 0.40,
    "M10": 0.40,
    "METAL1": 0.14,
    "METAL2": 0.14,
    "METAL3": 0.14,
    "METAL4": 0.14,
    "METAL5": 0.28,
    "METAL6": 0.28,
    "METAL7": 0.28,
    "METAL8": 0.28,
    "METAL9": 0.40,
    "METAL10": 0.40,
    "POLY": 0.10,
    "POL": 0.10,
    "DIFF": 0.12,
    "DIFFUSION": 0.12,
    "NWELL": 0.30,
    "NW": 0.30,
    "PWELL": 0.30,
    "PW": 0.30,
    "NP": 0.10,
    "NPLUS": 0.10,
    "PP": 0.10,
    "PPLUS": 0.10,
}

DEFAULT_MIN_WIDTH_RULES: Dict[str, float] = {
    "M1": 0.07,
    "M2": 0.07,
    "M3": 0.07,
    "M4": 0.07,
    "M5": 0.14,
    "M6": 0.14,
    "M7": 0.14,
    "M8": 0.14,
    "M9": 0.20,
    "M10": 0.20,
}

DEFAULT_INTERLAYER_SPACING: Dict[Tuple[str, str], float] = {
    ("M1", "M2"): 0.06,
    ("M2", "M3"): 0.06,
    ("M3", "M4"): 0.06,
    ("M4", "M5"): 0.06,
    ("M5", "M6"): 0.06,
    ("M6", "M7"): 0.06,
    ("M7", "M8"): 0.06,
    ("M8", "M9"): 0.06,
    ("M9", "M10"): 0.06,
}


class DRCRuleSet:
    def __init__(self):
        self.min_spacing: Dict[str, float] = dict(DEFAULT_SPACING_RULES)
        self.min_width: Dict[str, float] = dict(DEFAULT_MIN_WIDTH_RULES)
        self.interlayer_spacing: Dict[Tuple[str, str], float] = dict(DEFAULT_INTERLAYER_SPACING)

    def update_from_lef(self, lef_data: LefData) -> None:
        for lname, layer in lef_data.layers.items():
            key = lname.upper()
            if layer.pitch and layer.pitch > 0 and layer.width and layer.width > 0:
                spacing = layer.pitch - layer.width
                if spacing > 0:
                    self.min_spacing[key] = spacing
            if layer.width and layer.width > 0:
                self.min_width[key] = layer.width

    def get_spacing(self, layer_name: str) -> float:
        return self.min_spacing.get(
            layer_name.upper(),
            self.min_spacing.get(layer_name, 0.10),
        )

    def get_min_width(self, layer_name: str) -> float:
        return self.min_width.get(
            layer_name.upper(),
            self.min_width.get(layer_name, 0.05),
        )

    def get_interlayer_spacing(self, layer1: str, layer2: str) -> float:
        k1 = (layer1.upper(), layer2.upper())
        k2 = (layer2.upper(), layer1.upper())
        if k1 in self.interlayer_spacing:
            return self.interlayer_spacing[k1]
        if k2 in self.interlayer_spacing:
            return self.interlayer_spacing[k2]
        return 0.06

    def get_layer_pairs(self, layer_order: list) -> list:
        pairs = []
        for i in range(len(layer_order) - 1):
            l1 = layer_order[i]
            l2 = layer_order[i + 1]
            if self.get_interlayer_spacing(l1, l2) > 0:
                pairs.append((l1, l2))
        return pairs
