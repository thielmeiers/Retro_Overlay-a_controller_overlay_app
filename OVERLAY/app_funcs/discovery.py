# app_funcs/discovery.py
from __future__ import annotations

import os
import pygame

import overlay
from .paths import base_path


def list_skins() -> list[str]:
    skins_dir = os.path.join(base_path(), "skins")
    if not os.path.isdir(skins_dir):
        return []

    out = []
    for fn in os.listdir(skins_dir):
        if fn.endswith(".py") and not fn.startswith("_") and fn != "__init__.py":
            out.append(os.path.splitext(fn)[0])

    out.sort()
    return out


def list_controllers(max_n: int = 4) -> list[str]:
    pygame.init()
    pygame.joystick.init()

    out = []
    count = pygame.joystick.get_count()
    for i in range(min(count, max_n)):
        try:
            js = pygame.joystick.Joystick(i)
            js.init()
            out.append(f"{i}: {js.get_name()}")
        except pygame.error:
            out.append(f"{i}: Controller {i + 1}")

    if not out:
        out = ["0: (no controller found)"]

    return out


def list_monitors() -> list[str]:
    mons = overlay.list_active_monitors()
    if not mons:
        return ["0: (no monitor info)"]

    out = []
    for i, m in enumerate(mons):
        friendly = (m.get("friendly") or "").strip()
        device = (m.get("device") or "").strip()

        name = friendly or device or f"Monitor {i}"
        tag = " (Primary)" if m.get("primary") else ""

        r = m["monitor_rect"]
        w = r[2] - r[0]
        h = r[3] - r[1]

        out.append(f"{i}: {name}{tag}  [{w}x{h}]")

    return out