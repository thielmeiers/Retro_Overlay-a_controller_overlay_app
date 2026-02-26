# app_funcs/monitor_preview.py
from __future__ import annotations

from typing import Optional, Tuple

import customtkinter as ctk
from PIL import Image

try:
    from PIL import ImageGrab
except Exception:
    ImageGrab = None


def _virtual_screen_rect() -> Tuple[int, int, int, int]:
    """
    (left, top, right, bottom) for the Windows virtual desktop.
    """
    try:
        import ctypes

        user32 = ctypes.windll.user32
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass

        SM_XVIRTUALSCREEN = 76
        SM_YVIRTUALSCREEN = 77
        SM_CXVIRTUALSCREEN = 78
        SM_CYVIRTUALSCREEN = 79

        vx = int(user32.GetSystemMetrics(SM_XVIRTUALSCREEN))
        vy = int(user32.GetSystemMetrics(SM_YVIRTUALSCREEN))
        vw = int(user32.GetSystemMetrics(SM_CXVIRTUALSCREEN))
        vh = int(user32.GetSystemMetrics(SM_CYVIRTUALSCREEN))
        return (vx, vy, vx + vw, vy + vh)
    except Exception:
        return (0, 0, 1920, 1080)


def _grab_monitor_pil(monitor_rect: Tuple[int, int, int, int]) -> Image.Image:
    """
    Returns a PIL Image of the requested monitor rect (best-effort).
    Works for non-primary monitors by grabbing the full virtual desktop and cropping.
    """
    left, top, right, bottom = monitor_rect
    w = max(1, int(right - left))
    h = max(1, int(bottom - top))

    if ImageGrab is None:
        return Image.new("RGB", (w, h), (35, 35, 35))

    try:
        vleft, vtop, _vright, _vbottom = _virtual_screen_rect()

        # all_screens=True works on Windows for Pillow that supports it
        full = ImageGrab.grab(all_screens=True)

        crop_box = (
            int(left - vleft),
            int(top - vtop),
            int(right - vleft),
            int(bottom - vtop),
        )

        img = full.crop(crop_box)
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")
        return img
    except Exception:
        return Image.new("RGB", (w, h), (35, 35, 35))


def monitor_preview_ctk_image(
    monitor_rect: Tuple[int, int, int, int],
    max_size: Tuple[int, int] = (760, 340),
) -> ctk.CTkImage:
    """
    Returns a CTkImage preview of the specified monitor rect, scaled to fit max_size.
    """
    img = _grab_monitor_pil(monitor_rect)

    max_w, max_h = max_size
    scale = min(max_w / img.size[0], max_h / img.size[1])
    out_w = max(1, int(img.size[0] * scale))
    out_h = max(1, int(img.size[1] * scale))

    img = img.resize((out_w, out_h), Image.Resampling.LANCZOS)
    return ctk.CTkImage(light_image=img, dark_image=img, size=(out_w, out_h))