# app_funcs/overlay_preview.py
from __future__ import annotations

from typing import Dict, Tuple, Any, Optional

import pygame
import customtkinter as ctk
from PIL import Image

import overlay


def build_preview_ctk_image(
    monitor_img: Optional[Image.Image],
    monitor_rect: Tuple[int, int, int, int],
    settings: Dict[str, Any],
    max_size: Tuple[int, int] = (560, 315),
) -> Optional[ctk.CTkImage]:
    """
    Returns a CTkImage showing:
    - current monitor screenshot (if provided)
    - controller skins placed in their corners using current settings
    This is only a preview (no input polling).
    """
    left, top, right, bottom = monitor_rect
    mon_w = max(1, right - left)
    mon_h = max(1, bottom - top)

    if monitor_img is None:
        monitor_img = Image.new("RGB", (mon_w, mon_h), (35, 35, 35))
    else:
        # Ensure size matches rect in case grab returns a different size
        if monitor_img.size != (mon_w, mon_h):
            monitor_img = monitor_img.resize((mon_w, mon_h), Image.Resampling.LANCZOS)

    # Make a pygame surface from the monitor image
    base_rgba = monitor_img.convert("RGBA")
    surf = pygame.image.fromstring(base_rgba.tobytes(), base_rgba.size, "RGBA").convert_alpha()

    scale = float(settings.get("scale", 1.0))
    margin = int(settings.get("margin", 24))
    overlays_cfg = settings.get("overlays", [])
    if not isinstance(overlays_cfg, list):
        overlays_cfg = []

    # Draw each skin once with dummy inputs
    for cfg in overlays_cfg:
        try:
            skin_name = str(cfg.get("skin_name", "default"))
            corner = str(cfg.get("corner", "ul")).lower().strip()

            skin = overlay.load_skin(skin_name)

            base_w = int(getattr(skin, "design_width", 400))
            base_h = int(getattr(skin, "design_height", 300))
            out_w = max(1, int(base_w * scale))
            out_h = max(1, int(base_h * scale))

            skin_surf = pygame.Surface((out_w, out_h), pygame.SRCALPHA)
            skin_surf.fill((0, 0, 0, 0))

            dummy = overlay.InputState(None, getattr(skin, "btn_map", {}), getattr(skin, "axis_map", {}))
            skin.draw(skin_surf, dummy, overlay.dz, overlay.norm_trigger, scale)

            px, py = overlay.compute_position_in_rect(
                corner, margin, out_w, out_h, (0, 0, mon_w, mon_h)
            )

            surf.blit(skin_surf, (px, py))
        except Exception:
            continue

    # Convert to PIL
    raw = pygame.image.tostring(surf, "RGBA")
    out_img = Image.frombytes("RGBA", (surf.get_width(), surf.get_height()), raw)

    # Fit preview into max_size
    max_w, max_h = max_size
    fit = min(max_w / out_img.size[0], max_h / out_img.size[1])
    out_w = max(1, int(out_img.size[0] * fit))
    out_h = max(1, int(out_img.size[1] * fit))
    out_img = out_img.resize((out_w, out_h), Image.Resampling.LANCZOS)

    return ctk.CTkImage(light_image=out_img, dark_image=out_img, size=(out_w, out_h))