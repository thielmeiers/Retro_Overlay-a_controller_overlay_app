# app_funcs/draw_layout_on_preview.py
from __future__ import annotations

from typing import Callable, Optional
from PIL import Image, ImageDraw # type: ignore


def corner_short(code: str) -> str:
    c = (code or "").lower().strip()
    if c == "ul":
        return "UL"
    if c == "ur":
        return "UR"
    if c == "ll":
        return "LL"
    if c == "lr":
        return "LR"
    return ""


def draw_layout_on_preview(
    base_rgba: Image.Image,
    settings: dict,
    get_skin_rgba: Callable[[str], Optional[Image.Image]],
    *,
    # Toggle lables
    # True = ON
    # False = OFF
    draw_labels: bool = False,
) -> Image.Image:
    """
    Composites static controller overlays onto a monitor screenshot.

    Applies:
      - base_rgba: Image.Imgae → SCALE (settings["scale"])
      - settings: dict → TRANSPARENCY (settings["transparency"] 0..100)
      - get_skin_rgba: Callable[[str], Optional[Image.Image]] → MARGIN (settings["margin"])
      - draw_labels: bool = False → CORNER placement (settings["overlays"][i]["corner"])
    """
    img = base_rgba.convert("RGBA").copy()
    draw = ImageDraw.Draw(img)

    overlays_cfg = settings.get("overlays", [])
    if not isinstance(overlays_cfg, list):
        return img

    mw, mh = img.size
    margin = int(settings.get("margin", 24))

    scale = float(settings.get("scale", 1.0))
    if scale <= 0:
        scale = 1.0

    transp_pct = int(settings.get("transparency", 100))
    transp_pct = max(0, min(100, transp_pct))
    alpha_mul = transp_pct / 100.0  # 0..1

    for cfg in overlays_cfg:
        try:
            skin_name = str(cfg.get("skin_name", "default"))
            corner = str(cfg.get("corner", "ul")).lower().strip()

            pil_skin = get_skin_rgba(skin_name)
            if pil_skin is None:
                continue

            pil_skin = pil_skin.copy().convert("RGBA")

            # Apply scale
            sw, sh = pil_skin.size
            new_w = max(1, int(sw * scale))
            new_h = max(1, int(sh * scale))
            if (new_w, new_h) != (sw, sh):
                pil_skin = pil_skin.resize((new_w, new_h), Image.Resampling.LANCZOS)
                sw, sh = pil_skin.size

            # Apply transparency
            if alpha_mul < 1.0:
                r, g, b, a = pil_skin.split()
                a = a.point(lambda px: int(px * alpha_mul))
                pil_skin = Image.merge("RGBA", (r, g, b, a))

            # Corner placement
            if corner == "ul":
                x, y = margin, margin
            elif corner == "ur":
                x, y = mw - sw - margin, margin
            elif corner == "ll":
                x, y = margin, mh - sh - margin
            else:
                x, y = mw - sw - margin, mh - sh - margin

            img.alpha_composite(pil_skin, (int(x), int(y)))

            
            if draw_labels:
                tag = f"{skin_name.upper()} {corner_short(corner)}".strip()
                draw.text((int(x) + 6, int(y) + 6), tag, fill=(255, 255, 255, 255))
            

        except Exception:
            continue

    return img