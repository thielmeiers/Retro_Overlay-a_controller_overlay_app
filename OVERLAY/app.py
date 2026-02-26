from __future__ import annotations

import os
import sys
import time
import subprocess
import importlib
from typing import Optional

import customtkinter as ctk
from PIL import Image

import overlay

from app_funcs import (
    list_skins,
    list_controllers,
    list_monitors,
    send_update,
    b64_encode_settings,
    run_as_overlay_mode,
    skin_preview_ctk_image,
    monitor_preview_ctk_image,
    draw_layout_on_preview,
    overlay_running,
    start_overlay_process,
    stop_overlay_process,
)

UDP_PORT = 29301

CORNER_LABELS = [
    ("ul", "Upper Left"),
    ("ur", "Upper Right"),
    ("ll", "Lower Left"),
    ("lr", "Lower Right"),
]

# shorthand for the corner tags
# e.g. "UL" = Upper Left corner
def _corner_short(code: str) -> str:
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


def _make_black_ctk(size: tuple[int, int]) -> ctk.CTkImage:
    img = Image.new("RGB", size, (0, 0, 0))
    return ctk.CTkImage(light_image=img, dark_image=img, size=size)


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.title("Retro Overlay")
        self.geometry("980x560")
        self.minsize(980, 560)
        self.after(50, self._maximize_window)

        self.skins = list_skins() or ["default"]
        self.controllers = list_controllers(max_n=4)
        self.monitors = list_monitors()

        self.monitor_index = 0
        self.scale = 1.0
        self.margin = 24
        self.transparency = 100

        # overlays: [{"controller_index": int, "skin_name": str, "corner": "ul|ur|ll|lr"}]
        self.overlays: list[dict] = []
        self.selected_controller = 0
        self.overlay_proc: Optional[subprocess.Popen] = None

        # Preview state
        self.preview_size = (760, 340)
        self._preview_black = _make_black_ctk(self.preview_size)
        self._preview_current: Optional[ctk.CTkImage] = None
        self._last_monitor_rect: Optional[tuple[int, int, int, int]] = None

        # Skin preview cache
        self.skin_previews: dict[str, ctk.CTkImage] = {}
        self._build_skin_previews()

        self._pending_assign_skin: Optional[str] = None

        self._build_ui()
        self._refresh_tiles()

        if self.monitors:
            self.monitor_dropdown.set(self.monitors[0])
            self._on_monitor_change(self.monitors[0])

        if self.controllers:
            self.ctrl_dropdown.set(self.controllers[0])
            self._on_controller_change(self.controllers[0])

        self._set_preview_black()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # =========================
    # Window behavior
    # =========================

    def _maximize_window(self):
        try:
            self.state("zoomed")
        except Exception:
            try:
                self.attributes("-zoomed", True)
            except Exception:
                pass

    # =========================
    # Overlay process
    # =========================

    def _overlay_running(self) -> bool:
        return overlay_running(self.overlay_proc)

    def _start_overlay_process(self, settings: dict):
        if self._overlay_running():
            return
        self.overlay_proc = start_overlay_process(settings, udp_port=UDP_PORT)

    def _stop_overlay_process(self):
        stop_overlay_process(self.overlay_proc)
        self.overlay_proc = None

    def _on_close(self):
        self._stop_overlay_process()
        self.destroy()

    def _on_close(self):
        stop_overlay_process(self.overlay_proc)
        self.overlay_proc = None
        self.destroy()

    # =========================
    # Live apply
    # =========================

    def _apply_live_if_running(self):
        if not self._overlay_running():
            return
        s = self._build_settings(allow_empty=True)
        if not s:
            return
        send_update(s)

    # =========================
    # Data helpers
    # =========================

    def _toast(self, msg: str):
        self.toast.configure(text=msg)

    def _used_corners(self) -> set[str]:
        used = set()
        for o in self.overlays:
            c = (o.get("corner") or "").lower().strip()
            if c:
                used.add(c)
        return used

    def _get_overlay_for_controller(self, controller_index: int) -> Optional[dict]:
        for o in self.overlays:
            if int(o.get("controller_index", -1)) == int(controller_index):
                return o
        return None

    def _upsert_overlay(self, controller_index: int, skin_name: str, corner: str):
        o = self._get_overlay_for_controller(controller_index)
        if o is None:
            self.overlays.append(
                {"controller_index": int(controller_index), "skin_name": str(skin_name), "corner": str(corner)}
            )
        else:
            o["skin_name"] = str(skin_name)
            o["corner"] = str(corner)

    def _remove_overlay(self, controller_index: int):
        self.overlays = [o for o in self.overlays if int(o.get("controller_index", -1)) != int(controller_index)]

    # =========================
    # Preview logic
    # =========================

    def _set_preview_black(self):
        self._preview_current = self._preview_black
        self.monitor_img_label.configure(image=self._preview_black, text="")

    def _get_skin_pil_rgba(self, skin_name: str) -> Optional[Image.Image]:
        ctk_img = self.skin_previews.get(skin_name)
        if ctk_img is None:
            ctk_img = skin_preview_ctk_image(skin_name, 190, 120)
        if ctk_img is None:
            return None

        pil_img = getattr(ctk_img, "_dark_image", None) or getattr(ctk_img, "_light_image", None)
        if pil_img is None:
            return None

        return pil_img.copy().convert("RGBA")

    def _update_preview_clicked(self):
        mons = overlay.list_active_monitors()
        if not mons:
            self._toast("No monitors found.")
            return

        mi = max(0, min(int(self.monitor_index), len(mons) - 1))
        self.monitor_index = mi
        mon = mons[mi]
        rect = mon["monitor_rect"]
        self._last_monitor_rect = rect

        try:
            base_ctk = monitor_preview_ctk_image(rect, max_size=self.preview_size)
        except TypeError:
            base_ctk = monitor_preview_ctk_image(rect)

        pil_base: Optional[Image.Image] = None
        try:
            pil_base = getattr(base_ctk, "_dark_image", None) or getattr(base_ctk, "_light_image", None)
            if pil_base is not None:
                pil_base = pil_base.copy().convert("RGBA")
        except Exception:
            pil_base = None

        settings = self._build_settings(allow_empty=True)
        if settings is None:
            self._toast("Invalid settings.")
            return

        if pil_base is None:
            self._preview_current = base_ctk
            self.monitor_img_label.configure(image=base_ctk, text="")
            self._toast("Preview updated.")
            return

        img = draw_layout_on_preview(
            pil_base,
            settings,
            self._get_skin_pil_rgba,

        )

        out = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
        self._preview_current = out
        self.monitor_img_label.configure(image=out, text="")
        self._toast("Preview updated.")

    # =========================
    # Settings
    # =========================

    def _build_settings(self, allow_empty: bool = False) -> Optional[dict]:
        try:
            self.scale = float(self.scale_entry.get().strip())
            self.margin = int(float(self.margin_entry.get().strip()))
            self.transparency = int(float(self.transp_entry.get().strip()))
        except Exception:
            self._toast("Invalid Scale/Margin/Transparency values.")
            return None

        if self.transparency < 0 or self.transparency > 100:
            self._toast("Transparency must be 0..100.")
            return None

        overlays_out = [
            {
                "controller_index": int(o.get("controller_index", 0)),
                "skin_name": str(o.get("skin_name", "default")),
                "corner": str(o.get("corner", "ul")).lower().strip(),
            }
            for o in self.overlays
        ]

        if (not overlays_out) and (not allow_empty):
            return None

        return {
            "monitor_index": int(self.monitor_index),
            "scale": float(self.scale),
            "margin": int(self.margin),
            "transparency": int(self.transparency),
            "overlays": overlays_out,
        }

    # =========================
    # UI build
    # =========================

    def _build_skin_previews(self):
        for s in self.skins:
            img = skin_preview_ctk_image(s, 190, 120)
            if img is not None:
                self.skin_previews[s] = img

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Top bar
        top = ctk.CTkFrame(self, corner_radius=0)
        top.grid(row=0, column=0, sticky="ew")
        top.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(top, text="Retro Overlay", font=ctk.CTkFont(size=16, weight="bold"))
        title.grid(row=0, column=0, padx=18, pady=14, sticky="w")

        self.quit_btn = ctk.CTkButton(
            top, text="QUIT", fg_color="#b02020", hover_color="#d03030", command=self._on_close
        )
        self.quit_btn.grid(row=0, column=1, padx=18, pady=14, sticky="e")

        # Main
        main = ctk.CTkFrame(self, corner_radius=14)
        main.grid(row=1, column=0, padx=18, pady=(0, 18), sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_columnconfigure(1, weight=1)
        main.grid_rowconfigure(0, weight=1)

        # Left panel
        left = ctk.CTkFrame(main, corner_radius=14)
        left.grid(row=0, column=0, padx=14, pady=14, sticky="nsew")
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(left, text="Display Preview", font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=0, column=0, padx=14, pady=(14, 10), sticky="w"
        )

        body = ctk.CTkFrame(left, corner_radius=12)
        body.grid(row=1, column=0, padx=14, pady=(0, 14), sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(body, text="Monitor", font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0, column=0, padx=14, pady=(14, 8), sticky="w"
        )

        self.monitor_dropdown = ctk.CTkOptionMenu(body, values=self.monitors, command=self._on_monitor_change)
        self.monitor_dropdown.grid(row=1, column=0, padx=14, sticky="ew")

        ctk.CTkButton(body, text="Update Preview", command=self._update_preview_clicked).grid(
            row=2, column=0, padx=14, pady=(10, 10), sticky="ew"
        )

        self.monitor_img_label = ctk.CTkLabel(body, text="")
        self.monitor_img_label.grid(row=3, column=0, padx=14, pady=(0, 14), sticky="n")

        # Modules row
        modules = ctk.CTkFrame(left, fg_color="transparent")
        modules.grid(row=2, column=0, padx=14, pady=(0, 14), sticky="ew")
        modules.grid_columnconfigure(0, weight=1)
        modules.grid_columnconfigure(1, weight=1)

        # Adjustments module
        adj = ctk.CTkFrame(modules, corner_radius=12)
        adj.grid(row=0, column=0, padx=(0, 10), sticky="nsew")
        adj.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(adj, text="Selected Settings Adjustments", font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0, column=0, padx=14, pady=(12, 8), sticky="w"
        )

        self.scale_entry = self._labeled_entry(adj, "Scale", "1.0", str(self.scale), row=1)
        self.margin_entry = self._labeled_entry(adj, "Margin", "24", str(self.margin), row=3)
        self.transp_entry = self._labeled_entry(adj, "Transparency", "100", str(self.transparency), row=5)

        

        # Help module
        helpf = ctk.CTkFrame(modules, corner_radius=12)
        helpf.grid(row=0, column=1, padx=(10, 0), sticky="nsew")
        helpf.grid_columnconfigure(0, weight=1)
        helpf.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(helpf, text="Settings Help Message", font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0, column=0, padx=14, pady=(12, 8), sticky="w"
        )

        self.help_text = ctk.CTkTextbox(helpf, corner_radius=10, height=120)
        self.help_text.grid(row=1, column=0, padx=14, pady=(0, 12), sticky="nsew")
        self.help_text.insert(
            "1.0",
            "• Scale: changes overlay size on the target monitor.\n"
            "• Margin: pixels from the chosen corner. (plans to make placement more configurable)\n"
            "• Transparency: overlay opacity (0..100).\n\n"
            "Preview is static until you press Update Preview.\n\n"
            "Settings placement, naming, function, and look\n"
            "are all likely to change during development.\n\n",
        )
        self.help_text.configure(state="disabled")

        # Start/Stop actions
        actions = ctk.CTkFrame(left, fg_color="transparent")
        actions.grid(row=4, column=0, padx=14, pady=(0, 14), sticky="ew")
        actions.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(actions, text="Start Overlay", command=self._start).grid(
            row=0, column=0, padx=(0, 8), sticky="ew"
        )
        ctk.CTkButton(actions, text="Stop", fg_color="#444444", hover_color="#555555", command=self._stop).grid(
            row=0, column=1, padx=(8, 0), sticky="ew"
        )

        # Right panel (skins)
        self._build_skins_panel(main)

        # Toast
        self.toast = ctk.CTkLabel(self, text="", text_color="#FFCC66")
        self.toast.grid(row=2, column=0, padx=18, pady=(0, 12), sticky="w")

    def _labeled_entry(self, parent, label: str, example: str, initial: str, row: int) -> ctk.CTkEntry:
        ctk.CTkLabel(parent, text=f"{label} (ex: {example})", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=row, column=0, padx=14, pady=(8, 6), sticky="w"
        )
        e = ctk.CTkEntry(parent)
        e.grid(row=row + 1, column=0, padx=14, sticky="ew")
        e.insert(0, initial)

        e.bind("<FocusOut>", lambda _ev: self._apply_live_if_running())
        e.bind("<Return>", lambda _ev: self._apply_live_if_running())
        return e

    # =========================
    # Monitor selection behavior
    # =========================

    def _on_monitor_change(self, value: str):
        try:
            self.monitor_index = int(value.split(":")[0].strip())
        except Exception:
            self.monitor_index = 0

        self._set_preview_black()
        self._apply_live_if_running()

    # =========================
    # Skins panel
    # =========================

    def _build_skins_panel(self, parent):
        right = ctk.CTkFrame(parent, corner_radius=14)
        right.grid(row=0, column=1, padx=14, pady=14, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(right, text="SKINS", font=ctk.CTkFont(size=28, weight="bold")).grid(
            row=0, column=0, padx=14, pady=(14, 6), sticky="w"
        )

        ctrl_row = ctk.CTkFrame(right, fg_color="transparent")
        ctrl_row.grid(row=1, column=0, padx=14, pady=(0, 10), sticky="ew")
        ctrl_row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(ctrl_row, text="Controller Select", font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0, column=0, padx=(0, 10), sticky="w"
        )

        self.ctrl_dropdown = ctk.CTkOptionMenu(ctrl_row, values=self.controllers, command=self._on_controller_change)
        self.ctrl_dropdown.grid(row=0, column=1, sticky="ew")

        self.tiles = ctk.CTkScrollableFrame(right, corner_radius=12)
        self.tiles.grid(row=3, column=0, padx=14, pady=(0, 10), sticky="nsew")
        self.tiles.grid_columnconfigure((0, 1), weight=1)

        bottom = ctk.CTkFrame(right, fg_color="transparent")
        bottom.grid(row=4, column=0, padx=14, pady=(0, 14), sticky="ew")
        bottom.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            bottom,
            text="Reset Position",
            fg_color="#444444",
            hover_color="#555555",
            command=self._show_reset_dropdown,
        ).grid(row=0, column=0, padx=(0, 8), sticky="ew")

        ctk.CTkButton(
            bottom,
            text="Clear Selected Controller",
            fg_color="#444444",
            hover_color="#555555",
            command=self._clear_selected_controller,
        ).grid(row=0, column=1, padx=(8, 0), sticky="ew")

        self.corner_dropdown = ctk.CTkOptionMenu(right, values=[""], command=self._on_corner_chosen)
        self.corner_dropdown.grid(row=5, column=0, padx=14, pady=(0, 14), sticky="ew")
        self.corner_dropdown.grid_remove()

    def _on_controller_change(self, value: str):
        try:
            self.selected_controller = int(value.split(":")[0].strip())
        except Exception:
            self.selected_controller = 0
        self._refresh_tiles()

    def _refresh_tiles(self):
        for w in self.tiles.winfo_children():
            w.destroy()

        assigned = self._get_overlay_for_controller(self.selected_controller)
        assigned_skin = (assigned or {}).get("skin_name", "")
        assigned_corner = (assigned or {}).get("corner", "")

        row = 0
        col = 0

        for skin_name in self.skins:
            tile = ctk.CTkFrame(self.tiles, corner_radius=14)
            tile.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

            img = self.skin_previews.get(skin_name)
            if img is not None:
                ctk.CTkLabel(tile, text="", image=img).pack(anchor="center", padx=10, pady=(14, 8))
            else:
                ctk.CTkLabel(tile, text=skin_name.upper(), font=ctk.CTkFont(size=18, weight="bold")).pack(
                    anchor="center", padx=10, pady=(22, 12)
                )

            sub = skin_name.upper()

            ctk.CTkLabel(tile, text=sub, text_color="#BBBBBB").pack(anchor="center", padx=10, pady=(0, 10))

            ctk.CTkButton(
                tile,
                text="Assign",
                fg_color="#1f6aa5",
                command=lambda s=skin_name: self._assign_skin(s),
            ).pack(fill="x", padx=14, pady=(0, 12))

            col += 1
            if col > 1:
                col = 0
                row += 1

        self._apply_live_if_running()

    def _assign_skin(self, skin_name: str):
        try:
            importlib.import_module(f"skins.{skin_name}")
        except Exception as e:
            self._toast(f"Skin import failed: skins.{skin_name} ({e})")
            return

        used = self._used_corners()

        cur = self._get_overlay_for_controller(self.selected_controller)
        cur_corner = str((cur or {}).get("corner", "")).lower().strip()
        if cur_corner in used:
            used.remove(cur_corner)

        available = [(c, lbl) for (c, lbl) in CORNER_LABELS if c not in used]
        if not available:
            self._toast("No corners left (max 4). Clear another controller.")
            return

        self._pending_assign_skin = skin_name

        self.corner_dropdown.configure(values=[f"{c}: {lbl}" for (c, lbl) in available])
        self.corner_dropdown.set(f"{available[0][0]}: {available[0][1]}")
        self.corner_dropdown.grid()

        self._toast("Pick a corner from the dropdown.")

    def _show_reset_dropdown(self):
        cur = self._get_overlay_for_controller(self.selected_controller)
        if cur is None:
            self._toast("No assignment to reset for this controller.")
            return

        used = self._used_corners()
        cur_corner = str(cur.get("corner", "")).lower().strip()
        if cur_corner in used:
            used.remove(cur_corner)

        available = [(c, lbl) for (c, lbl) in CORNER_LABELS if c not in used]
        if not available:
            self._toast("No available corners.")
            return

        self._pending_assign_skin = None

        self.corner_dropdown.configure(values=[f"{c}: {lbl}" for (c, lbl) in available])
        self.corner_dropdown.set(f"{available[0][0]}: {available[0][1]}")
        self.corner_dropdown.grid()

        self._toast("Pick a new corner from the dropdown.")

    def _on_corner_chosen(self, value: str):
        if not value:
            return
        corner = value.split(":")[0].strip().lower()
        if corner not in {"ul", "ur", "ll", "lr"}:
            return

        cur = self._get_overlay_for_controller(self.selected_controller)

        if self._pending_assign_skin:
            skin_name = self._pending_assign_skin
            self._upsert_overlay(self.selected_controller, skin_name, corner)
            self._toast(f"Controller {self.selected_controller}: {skin_name.upper()} | {_corner_short(corner)}")
        else:
            if cur is None:
                self.corner_dropdown.grid_remove()
                return
            cur["corner"] = corner
            self._toast(f"Controller {self.selected_controller}: corner -> {_corner_short(corner)}")

        self._pending_assign_skin = None
        self.corner_dropdown.grid_remove()
        self._refresh_tiles()

    def _clear_selected_controller(self):
        self._remove_overlay(self.selected_controller)
        self._toast(f"Cleared Controller {self.selected_controller}")
        self.corner_dropdown.grid_remove()
        self._refresh_tiles()

    # =========================
    # Start / Stop
    # =========================

    def _start(self):
        settings = self._build_settings(allow_empty=False)
        if not settings:
            self._toast("Assign at least one controller a skin before starting.")
            return

        self._set_preview_black()

        self._start_overlay_process(settings)
        time.sleep(0.15)
        send_update(settings)
        self._toast("Overlay running.")

    def _stop(self):
        self._stop_overlay_process()
        self._toast("Overlay stopped.")


if __name__ == "__main__":
    if "--overlay" in sys.argv:
        run_as_overlay_mode()
    else:
        App().mainloop()