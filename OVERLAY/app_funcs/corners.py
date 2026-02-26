# app_funcs/corners.py
from __future__ import annotations

CORNER_LABELS = [
    ("ul", "Upper Left"),
    ("ur", "Upper Right"),
    ("ll", "Lower Left"),
    ("lr", "Lower Right"),
]


def used_corners(overlays: list[dict], ignore_controller: int | None = None) -> set[str]:
    out = set()
    for o in overlays:
        ci = int(o.get("controller_index", -1))
        if ignore_controller is not None and ci == ignore_controller:
            continue
        c = str(o.get("corner", "")).strip().lower()
        if c:
            out.add(c)
    return out


def available_corners(overlays: list[dict], controller_index: int) -> list[tuple[str, str]]:
    used = used_corners(overlays, ignore_controller=controller_index)
    return [(c, lbl) for (c, lbl) in CORNER_LABELS if c not in used]