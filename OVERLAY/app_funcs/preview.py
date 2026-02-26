import importlib

import pygame
import customtkinter as ctk
from PIL import Image

import overlay


def skin_preview_ctk_image(skin_name: str, preview_w: int = 240, preview_h: int = 150) -> ctk.CTkImage | None:
    try:
        skin_mod = importlib.import_module(f"skins.{skin_name}")
        skin = skin_mod.build()
    except Exception:
        return None

    base_w = int(getattr(skin, "design_width", 400))
    base_h = int(getattr(skin, "design_height", 300))
    if base_w <= 0 or base_h <= 0:
        return None

    pad = 18
    inner_w = max(1, preview_w - pad * 2)
    inner_h = max(1, preview_h - pad * 2)

    scale_fit = min(inner_w / base_w, inner_h / base_h)
    scale_fit *= 0.92

    out_w = max(1, int(base_w * scale_fit))
    out_h = max(1, int(base_h * scale_fit))

    try:
        if not pygame.get_init():
            pygame.init()

        surf = pygame.Surface((out_w, out_h), pygame.SRCALPHA)
        surf.fill((0, 0, 0, 0))

        inp = overlay.InputState(None, getattr(skin, "btn_map", {}), getattr(skin, "axis_map", {}))
        skin.draw(surf, inp, overlay.dz, overlay.norm_trigger, scale_fit)

        raw = pygame.image.tostring(surf, "RGBA")
        img = Image.frombytes("RGBA", (out_w, out_h), raw)

        return ctk.CTkImage(light_image=img, dark_image=img, size=(out_w, out_h))
    except Exception:
        return None